###
# Copyright (c) 2006,2007 Dennis Kaarsemaker
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
###
# Based on the standard supybot logging plugin, which has the following
# copyright:
#
# Copyright (c) 2002-2004, Jeremiah Fincher
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

from supybot.commands import *
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.ircmsgs as ircmsgs
import supybot.conf as conf
import supybot.ircdb as ircdb
import sqlite
import pytz
import cPickle
import datetime
import time
import random
import md5
import threading

tz = 'UTC'

def now():
    return cPickle.dumps(datetime.datetime.now(pytz.timezone(tz)))

def fromTime(x):
    return cPickle.dumps(datetime.datetime(*time.gmtime(x)[:6], **{'tzinfo': pytz.timezone("UTC")}))

def capab(user, capability):
    capability = capability.lower()
    capabilities = list(user.capabilities)
    # Capability hierarchy #
    if capability == "bantracker":
        if capab(user, "admin"):
            return True
    if capability == "admin":
        if capab(user, "owner"):
            return True
    # End #
    if capability in capabilities:
        return True
    else:
        return False

def hostmaskPatternEqual(pattern, hostmask):
    if pattern.count('!') not in (1, 2) or pattern.count('@') != 1:
        return False
    if pattern.count('!') == 2:
        pattern = "!".join(pattern.split('!')[:-1])
    if pattern[0] == '%':
        pattern = pattern[1:]
    return ircutils.hostmaskPatternEqual(pattern, hostmask)

def dequeue(parent, irc):
    global queue
    queue.dequeue(parent, irc)

class MsgQueue(object):
    def __init__(self):
        self.msgcache = []
    def queue(self, msg):
        if msg not in self.msgcache:
            self.msgcache.append(msg)
    def clear(self):
        self.msgcache = []
    def dequeue(self, parent, irc):
        parent.thread_timer.cancel()
        parent.thread_timer = threading.Timer(10.0, dequeue, args=(parent, irc))
        if len(self.msgcache):
            msg = self.msgcache.pop(0)
            irc.queueMsg(msg)
        parent.thread_timer.start()

queue = MsgQueue()

class Ban(object):
    """Hold my bans"""
    def __init__(self, args=None, **kwargs):
        object.__init__(self)
        if args:
            self.mask = args[2]
            self.who = args[3]
            self.when = float(args[4])
        else:
            self.mask = kwargs['mask']
            self.who = kwargs['who']
            self.when = float(kwargs['when'])
        self.ascwhen = time.asctime(time.gmtime(self.when))

    def __tuple__(self):
        return (self.mask, self.who, self.ascwhen)

    def __iter__(self):
        return self.__tuple__().__iter__()

    def __str__(self):
        return "%s by %s on %s" % tuple(self)

    def __repr__(self):
        return '<%s object "%s" at 0x%x>' % (self.__class__.__name__, self, id(self))

    def op(self):
        return self.mask.split('!')[0]

    def time(self):
        return datetime.datetime.fromtimestamp(self.when)

class Bantracker(callbacks.Plugin):
    """Plugin to manage bans.
       See '@list Bantracker' and '@help <command>' for commands"""
    noIgnore = True
    threaded = True
    
    def __init__(self, irc):
        self.__parent = super(Bantracker, self)
        self.__parent.__init__(irc)
        self.default_irc = irc
        self.lastMsgs = {}
        self.lastStates = {}
        self.replies = {}
        self.logs = {}
        self.nicks = {}
        self.hosts = {}
        self.bans = {}

        self.thread_timer = threading.Timer(10.0, dequeue, args=(self,irc))
        self.thread_timer.start()

        db = self.registryValue('database')
        if db:
            self.db = sqlite.connect(db)
        else:
            self.db = None
        self.get_bans(irc)
        self.get_nicks(irc)

    def get_nicks(self, irc):
        self.hosts.clear()
        for (channel, c) in irc.state.channels.iteritems():
            for nick in list(c.users):
                nick = nick.lower()
                if not nick in self.nicks:
                    host = self.nick_to_host(irc, nick, False).lower()
                    self.nicks[nick] = host
                    host = host.split('@', 1)[1]
                    if '*' not in host:
                        if host not in self.hosts:
                            self.hosts[host] = []
                        self.hosts[host].append(nick)

    def get_bans(self, irc):
        global queue
        for channel in irc.state.channels.keys():
            if channel not in self.bans:
                self.bans[channel] = []
            queue.queue(ircmsgs.mode(channel, 'b'))

    def sendWhois(self, irc, nick, do_reply=False, *args):
        nick = nick.lower()
        irc.queueMsg(ircmsgs.whois(nick, nick))
        if do_reply:
            self.replies[nick] = [args[0], args[1:]]

    def do311(self, irc, msg):
        """/whois"""
        nick = msg.args[1].lower()
        mask = "%s!%s@%s" % (nick, msg.args[2].lower(), msg.args[3].lower())
        self.nicks[nick] = mask
        if nick in self.replies:
            f = getattr(self, "real_%s" % self.replies[nick][0])
            args = self.replies[nick][1]
            del self.replies[nick]
            kwargs={'from_reply': True, 'reply': "%s!%s@%s" % (msg.args[1], msg.args[2], msg.args[3])}
            f(*args, **kwargs)

    def do314(self, irc, msg):
        """/whowas"""
        nick = msg.args[1].lower()
        mask = "%s!%s@%s" % (nick, msg.args[2].lower(), msg.args[3].lower())
        if not nick in self.nicks:
            self.nicks[nick] = mask
        if nick in self.replies:
            f = getattr(self, "real_%s" % self.replies[nick][0])
            args = self.replies[nick][1]
            del self.replies[nick]
            kwargs={'from_reply': True, 'reply': "%s!%s@%s" % (msg.args[1], msg.args[2], msg.args[3])}
            f(*args, **kwargs)

    def do401(self, irc, msg):
        """/whois faild"""
        irc.queueMsg(ircmsgs.IrcMsg(prefix="", command='WHOWAS', args=(msg.args[1],), msg=msg))

    def do406(self, irc, msg):
        """/whowas faild"""
        nick = msg.args[1].lower()
        if nick in self.replies:
            f = getattr(self, "real_%s" % self.replies[nick][0])
            args = self.replies[nick][1]
            del self.replies[nick]
            kwargs = {'from_reply': True, 'reply': None}
            f(*args, **kwargs)

    def do367(self, irc, msg):
        """Got ban"""
        if msg.args[1] not in self.bans.keys():
            self.bans[msg.args[1]] = []
        self.bans[msg.args[1]].append(Ban(msg.args))

    def nick_to_host(self, irc=None, target='', with_nick=True, reply_now=True):
        target = target.lower()
        if ircutils.isUserHostmask(target):
            return target
        elif target in self.nicks:
            return self.nicks[target]
        elif irc:
            try:
                return irc.state.nickToHostmask(target)
            except:
                if reply_now:
                    if with_nick:
                        return "%s!*@*" % target
                    return "*@*"
        return

        if target in self.nicks:
            return self.nicks[target]
        else:
            return "%s!*@*" % target

    def die(self):
        global queue
        if self.db:
            try:
                self.db.close()
            except:
                pass
        try:
            self.thread_timer.cancel()
        except:
            pass
        queue.clear()

    def reset(self):
        global queue
        if self.db:
            try:
                self.db.close()
            except:
                pass
        queue.clear()
#        self.logs.clear()
        self.lastMsgs.clear()
        self.lastStates.clear()
#        self.nicks.clear()

    def __call__(self, irc, msg):
        try:
            super(self.__class__, self).__call__(irc, msg)
            if irc in self.lastMsgs:
                if irc not in self.lastStates:
                    self.lastStates[irc] = irc.state.copy()
                self.lastStates[irc].addMsg(irc, self.lastMsgs[irc])
        finally:
            self.lastMsgs[irc] = msg

    def db_run(self, query, parms, expect_result = False, expect_id = False):
        if not self.db:
            self.log.error("Bantracker database not open")
            return
        n_tries = 0
        try:
            cur = self.db.cursor()
            cur.execute(query, parms)
        except:
            cur = None
            if n_tries > 5:
                print "Tried more than 5 times, aborting"
                raise
            n_tries += 1
            time.sleep(1)
        data = None
        if expect_result and cur: data = cur.fetchall()
        if expect_id: data = self.db.insert_id()
        self.db.commit()
        return data

    def doLog(self, irc, channel, s):
        if not self.registryValue('enabled', channel):
            return
        channel = ircutils.toLower(channel) 
        if channel not in self.logs.keys():
            self.logs[channel] = []
        format = conf.supybot.log.timestampFormat()
        if format:
            s = time.strftime(format, time.gmtime()) + " " + ircutils.stripFormatting(s)
        self.logs[channel] = self.logs[channel][-199:] + [s.strip()]

    def doKickban(self, irc, channel, nick, target, kickmsg = None, use_time = None, extra_comment = None):
        if not self.registryValue('enabled', channel):
            return
        n = now()
        if use_time:
            n = fromTime(use_time)
        id = self.db_run("INSERT INTO bans (channel, mask, operator, time, log) values(%s, %s, %s, %s, %s)", 
                          (channel, target, nick, n, '\n'.join(self.logs[channel])), expect_id=True)
        if kickmsg and id and not (kickmsg == nick):
            self.db_run("INSERT INTO comments (ban_id, who, comment, time) values(%s,%s,%s,%s)", (id, nick, kickmsg, n))
        if extra_comment:
            self.db_run("INSERT INTO comments (ban_id, who, comment, time) values(%s,%s,%s,%s)", (id, nick, extra_comment, n))
        if channel not in self.bans:
            self.bans[channel] = []
        self.bans[channel].append(Ban(mask=target, who=nick, when=time.mktime(time.gmtime())))
        return id

    def doUnban(self, irc, channel, nick, mask):
        if not self.registryValue('enabled', channel):
            return
        data = self.db_run("SELECT MAX(id) FROM bans where channel=%s and mask=%s", (channel, mask), expect_result=True)
        if len(data) and not (data[0][0] == None):
            self.db_run("UPDATE bans SET removal=%s , removal_op=%s WHERE id=%s", (now(), nick, int(data[0][0])))
        if not channel in self.bans:
            self.bans[channel] = []
        idx = None
        for ban in self.bans[channel]:
            if ban.mask == mask:
                idx = self.bans[channel].index(ban)
                break
        if idx != None:
            del self.bans[channel][idx]

    def doPrivmsg(self, irc, msg):
        (recipients, text) = msg.args
        for channel in recipients.split(','):
            if irc.isChannel(channel):
                nick = msg.nick or irc.nick
                if ircmsgs.isAction(msg):
                    self.doLog(irc, channel,
                               '* %s %s\n' % (nick, ircmsgs.unAction(msg)))
                else:
                    self.doLog(irc, channel, '<%s> %s\n' % (nick, text))

    def doNotice(self, irc, msg):
        (recipients, text) = msg.args
        for channel in recipients.split(','):
            if irc.isChannel(channel):
                self.doLog(irc, channel, '-%s- %s\n' % (msg.nick, text))

    def doNick(self, irc, msg):
        oldNick = msg.nick
        newNick = msg.args[0]
        for (channel, c) in irc.state.channels.iteritems():
            if newNick in c.users:
                self.doLog(irc, channel,
                           '*** %s is now known as %s\n' % (oldNick, newNick))
        if oldNick.lower() in self.nicks:
            del self.nicks[oldNick.lower()]
        nick = newNick.lower()
        hostmask = nick + "!".join(msg.prefix.lower().split('!')[1:])
        self.nicks[nick] = hostmask

    def doJoin(self, irc, msg):
        global queue
        for channel in msg.args[0].split(','):
            if msg.nick:
                self.doLog(irc, channel,
                       '*** %s (%s) has joined %s\n' % (msg.nick, msg.prefix.split('!', 1)[1], channel))
            else:
                self.doLog(irc, channel,
                       '*** %s has joined %s\n' % (msg.prefix, channel))
            if not channel in self.bans.keys():
                self.bans[channel] = []
            if msg.prefix.split('!', 1)[0] == irc.nick:
                queue.queue(ircmsgs.mode(channel, 'b'))
        nick = msg.nick.lower() or msg.prefix.lower().split('!', 1)[0]
        self.nicks[nick] = msg.prefix.lower()

    def doKick(self, irc, msg):
        if len(msg.args) == 3:
            (channel, target, kickmsg) = msg.args
        else:
            (channel, target) = msg.args
            kickmsg = ''
        host = self.nick_to_host(irc, target, True)
        if host == "%s!*@*" % host:
            host = None
        if kickmsg:
            self.doLog(irc, channel,
                       '*** %s was kicked by %s (%s)\n' % (target, msg.nick, kickmsg))
        else:
            self.doLog(irc, channel,
                       '*** %s was kicked by %s\n' % (target, msg.nick))
        self.doKickban(irc, channel, msg.nick, target, kickmsg, extra_comment=host)

    def doPart(self, irc, msg):
        for channel in msg.args[0].split(','):
            self.doLog(irc, channel, '*** %s (%s) has left %s (%s)\n' % (msg.nick, msg.prefix, channel, msg.args[1]))
            if msg.args[1].startswith('requested by'):
                args = msg.args[1].split()
                self.doKickban(irc, channel, args[2].replace(':',''), msg.nick, ' '.join(args[3:])[1:-1].strip(), extra_comment=msg.prefix)

    def doMode(self, irc, msg):
        channel = msg.args[0]
        if irc.isChannel(channel) and msg.args[1:]:
            self.doLog(irc, channel,
                       '*** %s sets mode: %s %s\n' %
                       (msg.nick or msg.prefix, msg.args[1],
                        ' '.join(msg.args[2:])))
            if 'b' in msg.args[1] or 'd' in msg.args[1]:
                i = 2
                plusmin = False
                for c in msg.args[1]:
                    if   c == '-': plusmin = False
                    elif c == '+': plusmin = True
                    else:
                        if c == 'b':
                            if plusmin:
                                comment = self.getHostFromBan(irc, msg, msg.args[i])
                                self.doKickban(irc, channel, msg.nick, msg.args[i], extra_comment=comment)
                            else: self.doUnban(irc,channel, msg.nick, msg.args[i])
                            i += 1
                        if c == 'd':
                            if plusmin: self.doKickban(irc, channel, msg.nick, msg.args[i] + ' (realname)')
                            else: self.doUnban(irc,channel, msg.nick, msg.args[i] + ' (realname)')
                            i += 1

    def getHostFromBan(self, irc, msg, mask):
        if irc not in self.lastStates:
            self.lastStates[irc] = irc.state.copy()
        if mask[0] == '%':
            mask = mask[1:]
        (nick, ident, host) = ircutils.splitHostmask(mask)
        channel = None
        chan = None
        if mask[0] not in ('*', '?'): # Nick ban
            if nick in self.nicks:
                return self.nicks[nick]
        else: # Host/ident ban
            for (inick, ihost) in self.nicks.iteritems():
                if ircutils.hostmaskPatternEqual(mask, ihost):
                    return ihost
        return None

    def doTopic(self, irc, msg):
        if len(msg.args) == 1:
            return # It's an empty TOPIC just to get the current topic.
        channel = msg.args[0]
        self.doLog(irc, channel,
                   '*** %s changes topic to "%s"\n' % (msg.nick, msg.args[1]))

    def doQuit(self, irc, msg):
        if irc not in self.lastStates:
            self.lastStates[irc] = irc.state.copy()
        for (channel, chan) in self.lastStates[irc].channels.iteritems():
            if msg.nick in chan.users:
                self.doLog(irc, channel, '*** %s (%s) has quit IRC (%s)\n' % (msg.nick, msg.prefix, msg.args[0]))
#            if msg.nick in self.user:
#                del self.user[msg.nick]

    def outFilter(self, irc, msg):
        # Gotta catch my own messages *somehow* :)
        # Let's try this little trick...
        if msg.command in ('PRIVMSG', 'NOTICE'):
            # Other messages should be sent back to us.
            m = ircmsgs.IrcMsg(msg=msg, prefix=irc.prefix)
            self(irc, m)
        return msg
        
#    def callPrecedence(self, irc):
#        before = []
#        for cb in irc.callbacks:
#            if cb.name() == 'IRCLogin':
#                return (['IRCLogin'], [])
#        return ([], [])

    def check_auth(self, irc, msg, args, cap='bantracker'):
        hasIRCLogin = False
        for cb in self.callPrecedence(irc)[0]:
            if cb.name() == "IRCLogin":
                hasIRCLogin = True
        if hasIRCLogin and not msg.tagged('identified'):
            irc.error(conf.supybot.replies.incorrectAuthentication())
            return False
        try:
            user = ircdb.users.getUser(msg.prefix[:msg.prefix.find('!')].lower())
        except:
            irc.error(conf.supybot.replies.incorrectAuthentication())
            return False

        if not capab(user, cap):
            irc.error(conf.supybot.replies.noCapability() % cap)
            return False
        return user

    def btlogin(self, irc, msg, args):
        """Takes no arguments

        Sends you a message with a link to login to the bantracker.
        """
        user = self.check_auth(irc, msg, args)
        if not user:
            return
        user.addAuth(msg.prefix)
        try:
            ircdb.users.setUser(user, flush=False)
        except:
            pass

        if not capab(user, 'bantracker'):
            irc.error(conf.supybot.replies.noCapability() % 'bantracker')
            return
        if not self.registryValue('bansite'):
            irc.error("No bansite set, please set supybot.plugins.Bantracker.bansite")
            return
        sessid = md5.new('%s%s%d' % (msg.prefix, time.time(), random.randint(1,100000))).hexdigest()
        self.db_run("INSERT INTO sessions (session_id, user, time) VALUES (%s, %s, %d);",
            ( sessid, msg.nick, int(time.mktime(time.gmtime())) ) )
        irc.reply('Log in at %s/bans.cgi?sess=%s' % (self.registryValue('bansite'), sessid), private=True)

    btlogin = wrap(btlogin)

    def mark(self, irc, msg, args, channel, target, kickmsg):
        """[<channel>] <nick|hostmask> [<comment>]

        Creates an entry in the Bantracker as if <nick|hostmask> was kicked from <channel> with the comment <comment>,
        if <comment> is given it will be uses as the comment on the Bantracker, <channel> is only needed when send in /msg
        """
        user = self.check_auth(irc, msg, args)
        if not user:
            return

        if target == '*' or target[0] == '*':
            irc.error("Can not create a mark for '%s'" % target)
            return

        if not channel:
            irc.error('<channel> must be given if not in a channel')
            return
        channel = channel.lower()
        channels = []
        for chan in irc.state.channels.keys():
            channels.append(chan.lower())

        if not channel in channels:
            irc.error('Not in that channel')
            return

        if not kickmsg:
            kickmsg = '**MARK**'
        else:
            kickmsg = "**MARK** - %s" % kickmsg
        hostmask = self.nick_to_host(irc, target)

        self.doLog(irc, channel.lower(), '*** %s requested a mark for %s\n' % (msg.nick, target))
        self.doKickban(irc, channel.lower(), msg.nick, hostmask, kickmsg)
        irc.replySuccess()

    mark = wrap(mark, [optional('channel'), 'something', additional('text')])

    def sort_bans(self, channel=None):
        data = self.db_run("SELECT mask, removal, channel, id FROM bans", (), expect_result=True)
        if channel:
            data = [i for i in data if i[2] == channel]
        bans  = [(i[0], i[3]) for i in data if i[1] == None and '%' not in i[0]]
        mutes = [(i[0], i[3]) for i in data if i[1] == None and '%' in i[0]]
        return mutes + bans

    def get_banId(self, mask, channel):
        data = self.db_run("SELECT MAX(id) FROM bans WHERE mask=%s AND channel=%s", (mask, channel), True)[0]
        if not data[0]:
            return
        return int(data[0])

    def getBans(self, hostmask, channel):
        match = []
        if channel:
            if channel in self.bans and self.bans[channel]:
                for b in self.bans[channel]:
                    if hostmaskPatternEqual(b.mask, hostmask):
                        match.append((b.mask, self.get_banId(b.mask,channel)))
                data = self.sort_bans(channel)
                for e in data:
                    if hostmaskPatternEqual(e[0], hostmask):
                        if (e[0], e[1]) not in match:
                            match.append((e[0], e[1]))
        else:
            for c in self.bans:
                for b in self.bans[c]:
                    if hostmaskPatternEqual(b.mask, hostmask):
                        match.append((b.mask, self.get_banId(b.mask,c)))
            data = self.sort_bans()
            for e in data:
                    if hostmaskPatternEqual(e[0], hostmask):
                        if (e[0], e[1]) not in match:
                            match.append((e[0], e[1]))
        return match

    def bansearch_real(self, irc, msg, args, target, channel, from_reply=False, reply=None):
        """<nick|hostmask> [<channel>]

        Search bans database for a ban on <nick|hostmask>,
        if <channel> is not given search all channel bans.
        """
        def format_entry(entry):
            ret = list(entry[:-1])
            t = cPickle.loads(entry[-1]).astimezone(pytz.timezone('UTC')).strftime("%b %d %Y %H:%M:%S")
            ret.append(t)
            return tuple(ret)

        user = self.check_auth(irc, msg, args)
        if not user:
            return

        if from_reply:
            if not reply:
                if capab(user, 'admin'):
                    if len(queue.msgcache) > 0:
                            irc.reply("Warning: still syncing (%i)" % len(queue.msgcache))
                irc.reply("No matches found for %s in %s" % (hostmask, True and channel or "any channel"))
            hostmask = reply
        else:
            hostmask = self.nick_to_host(irc, target, reply_now=False)
        if not hostmask:
            self.sendWhois(irc, target, True, 'bansearch', irc, msg, args, target, channel)
            return
        match = self.getBans(hostmask, channel)

        if capab(user, 'owner'):
            if len(queue.msgcache) > 0:
                irc.reply("Warning: still syncing (%i)" % len(queue.msgcache))

        if channel:
            if not ircutils.isChannel(channel):
                channel = None

        if '*' in target or '?' in target:
            irc.error("Can only search for a complete hostmask")
            return
        hostmask = target
        if '!' not in target or '@' not in target:
            hostmask = self.nick_to_host(irc, target)
        if '!' not in hostmask:
            if "n=" in hostmask:
                hostmask = hostmask.replace("n=", "!n=", 1)
            elif "i=" in hostmask:
                hostmask = hostmask.replace("i=", "!i=", 1)
        match = self.getBans(hostmask, channel)

        if not match:
            irc.reply("No matches found for %s in %s" % (hostmask, True and channel or "any channel"))
            return
        ret = []
        replies = []
        for m in match:
            if m[1]:
                ret.append((format_entry(self.db_run("SELECT mask, operator, channel, time FROM bans WHERE id=%d", m[1], expect_result=True)[0]), m[1]))
        if not ret:
            done = []
            for c in self.bans:
                for b in self.bans[c]:
                    for m in match:
                        if m[0] == b.mask:
                            if not c in done:
                                irc.reply("Match %s in %s" % (b, c))
                                done.append(c)
            return
        for i in ret:
            if '*' in i[0][0] or '?' in i[0][0]:
                banstr = "Match: %s by %s in %s on %s (ID: %s)" % (i[0] + (i[1],))
            else:
                banstr = "Mark: by %s in %s on %s (ID: %s)" % (i[0][1:] + (i[1],))
            if (banstr, False) not in replies:
                replies.append((banstr, False))

        if replies:
            for r in replies:
                irc.reply(r[0], private=r[1])
            return
        irc.error("Something not so good happened, please tell stdin about it")

    bansearch = wrap(bansearch_real, ['something', optional('something', default=None)])

    def banlog(self, irc, msg, args, target, channel):
        """<nick|hostmask> [<channel>]

        Prints the last 5 messages from the nick/host logged before a ban/mute,
        the nick/host has to have an active ban/mute against it.
        If channel is not given search all channel bans.
        """
        user = self.check_auth(irc, msg, args)
        if not user:
            return

        if capab(user, 'owner') and len(queue.msgcache) > 0:
            irc.reply("Warning: still syncing (%i)" % len(queue.msgcache))

        hostmask = self.nick_to_host(irc, target)
        target = target.split('!', 1)[0]
        match = self.getBans(hostmask, channel)

        if not match:
            irc.reply("No matches found for %s (%s) in %s" % (target, hostmask, True and channel or "any channel"))
            return

        ret = []
        for m in match:
            if m[1]:
                ret.append((self.db_run("SELECT log, channel FROM bans WHERE id=%d", m[1], expect_result=True), m[1]))

        sent = []
        if not ret:
            irc.reply("No matches in tracker")
        for logs in ret:
            log = logs[0]
            id = logs[1]
            lines = ["%s: %s" % (log[0][1], i) for i in log[0][0].split('\n') if "<%s>" % target.lower() in i.lower() and i[21:21+len(target)].lower() == target.lower()]
            show_sep = False
            if not lines:
                show_sep = False
                irc.error("No log for ID %s available" % id)
            else:
                for l in lines[:5]:
                    if l not in sent:
                        show_sep = True
                        irc.reply(l)
                        sent.append(l)
            if show_sep:
                irc.reply('--')

    banlog = wrap(banlog, ['something', optional('anything', default=None)])

    def updatebt(self, irc, msg, args, channel):
        """[<channel>]

        Update bans in the tracker from the channel ban list,
        if channel is not given then run in all channels
        """

        def getBans(chan):
            data = self.db_run("SELECT mask, removal FROM bans WHERE channel=%s", chan, expect_result=True)
            return [i[0] for i in data if i[1] == None and "!" in i[0]]

        def remBans(chan):
            bans = getBans(chan)
            old_bans = bans[:]
            new_bans = [i.mask for i in self.bans[chan]]
            remove_bans = []
            for ban in old_bans:
                if ban not in new_bans:
                    remove_bans.append(ban)
                    bans.remove(ban)

            for ban in remove_bans:
                self.log.info("Removing ban %s from %s" % (ban.replace('%', '%%'), chan))
                self.doUnban(irc, channel, "Automated-Removal", ban)

            return len(remove_bans)

        def addBans(chan):
            bans = self.bans[chan]
            old_bans = getBans(chan)
            add_bans = []
            for ban in bans:
                if ban.mask not in old_bans and ban not in add_bans:
                    add_bans.append(ban)

            for ban in add_bans:
                nick = ban.who
                if nick.endswith('.freenode.net'):
                    nick = "Automated-Addition"
                self.log.info("Adding ban %s to %s (%s)" % (str(ban).replace('%', '%%'), chan, nick))
                self.doLog(irc, channel.lower(), '*** Ban sync from channel: %s\n' % str(ban).replace('%', '%%'))
                self.doKickban(irc, chan, nick, ban.mask, use_time = ban.when)
            return len(add_bans)

        if not self.check_auth(irc, msg, args, 'owner'):
            return

        add_res = 0
        rem_res = 0

        if len(queue.msgcache) > 0:
            irc.reply("Error: still syncing (%i)" % len(queue.msgcache))
            return

        try:
            if channel:
                rem_res += remBans(channel)
                add_res += addBans(channel)
            else:
                for channel in irc.state.channels.keys():
                    if channel not in  self.bans:
                        self.bans[channel] = []
                    rem_res += remBans(channel)
                    add_res += addBans(channel)
        except KeyError, e:
            irc.error("%s, Please wait longer" % e)
            return

        irc.reply("Cleared %i obsolete bans, Added %i new bans" % (rem_res, add_res))

    updatebt = wrap(updatebt, [optional('anything', default=None)])

    def comment(self, irc, msg, args, id, kickmsg):
        """<id> [<comment>]

        Reads or adds the <comment> for the ban with <id>,
        use @bansearch to find the id of a ban
        """
        def addComment(id, nick, msg):
            n = now()
            self.db_run("INSERT INTO comments (ban_id, who, comment, time) values(%s,%s,%s,%s)", (id, nick, msg, n))
        def readComment(id):
            return self.db_run("SELECT who, comment, time FROM comments WHERE ban_id=%i", (id,), True)

        nick = msg.nick
        if kickmsg:
            addComment(id, nick, kickmsg)
            irc.replySuccess()
        else:
            data = readComment(id)
            if data:
                for c in data:
                    irc.reply("%s %s: %s" % (cPickle.loads(c[2]).astimezone(pytz.timezone('UTC')).strftime("%b %d %Y %H:%M:%S"), c[0], c[1].strip()) )
            else:
                irc.error("No comments recorded for ban %i" % id)
    comment = wrap(comment, ['id', optional('text')])

    def banlink(self, irc, msg, args, id, highlight):
        """<id> [<highlight>]

        Returns a link to the log of the ban/kick with id <id>.
        If <highlight> is given, lines containing that term will be highlighted
        """
        if not self.check_auth(irc, msg, args):
            return
        if not highlight:
            irc.reply("%s/bans.cgi?log=%s" % (self.registryValue('bansite'), id), private=True)
        else:
            irc.reply("%s/bans.cgi?log=%s&mark=%s" % (self.registryValue('bansite'), id, highlight), private=True)
    banlink = wrap(banlink, ['id', optional('somethingWithoutSpaces')])

Class = Bantracker

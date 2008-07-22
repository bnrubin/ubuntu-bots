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
import sqlite, pytz, cPickle, datetime, time, random, md5

tz = 'UTC'

def now():
    return cPickle.dumps(datetime.datetime.now(pytz.timezone(tz)))

def capab(user, capability):
    try:
        if capability in user.capabilities:
            return True
        else:
            return False
    except:
        return False

class Bantracker(callbacks.Plugin):
    """Use @mark to add a bantracker entry manually and
       @btlogin to log into the bantracker"""
    noIgnore = True
    
    def __init__(self, irc):
        self.__parent = super(Bantracker, self)
        self.__parent.__init__(irc)
        self.lastMsgs = {}
        self.lastStates = {}
        self.logs = {}

        db = self.registryValue('database')
        if db:
            self.db = sqlite.connect(db)
        else:
            self.db = None

    def die(self):
        self.db.close()

    def reset(self):
        self.db.close()

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
        n_tries = 0
        try:
            cur = self.db.cursor()
            cur.execute(query, parms)
        except:
            if n_tries > 5:
                print "Tried more than 5 times, aborting"
                raise
            n_tries += 1
            time.sleep(1)
        data = None
        if expect_result: data = cur.fetchall()
        if expect_id: data = self.db.insert_id()
        self.db.commit()
        return data

    def reset(self):
        self.logs.clear()
        self.lastMsgs.clear()
        self.lastStates.clear()

    def doLog(self, irc, channel, s):
        if not self.registryValue('enabled', channel):
            return
        channel = ircutils.toLower(channel) 
        if channel not in self.logs.keys():
            self.logs[channel] = []
        format = conf.supybot.log.timestampFormat()
        if format:
            s = time.strftime(format) + " " + ircutils.stripFormatting(s)
        self.logs[channel] = self.logs[channel][-199:] + [s.strip()]

    def doKickban(self, irc, channel, nick, target, kickmsg = None):
        if not self.registryValue('enabled', channel):
            return
        n = now()
        id = self.db_run("INSERT INTO bans (channel, mask, operator, time, log) values(%s, %s, %s, %s, %s)", 
                          (channel, target, nick, n, '\n'.join(self.logs[channel])), expect_id=True)
        if kickmsg and id and not (kickmsg == nick):
            self.db_run("INSERT INTO comments (ban_id, who, comment, time) values(%s,%s,%s,%s)", (id, nick, kickmsg, n))

    def doUnban(self, irc, channel, nick, mask):
        if not self.registryValue('enabled', channel):
            return
        data = self.db_run("SELECT MAX(id) FROM bans where channel=%s and mask=%s", (channel, mask), expect_result=True)
        if len(data) and not (data[0][0] == None):
            self.db_run("UPDATE bans SET removal=%s , removal_op=%s WHERE id=%s", (now(), nick, int(data[0][0])))

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
    def doJoin(self, irc, msg):
        for channel in msg.args[0].split(','):
            self.doLog(irc, channel,
                       '*** %s has joined %s\n' % (msg.nick or msg.prefix, channel))

    def doKick(self, irc, msg):
        if len(msg.args) == 3:
            (channel, target, kickmsg) = msg.args
        else:
            (channel, target) = msg.args
            kickmsg = ''
        if kickmsg:
            self.doLog(irc, channel,
                       '*** %s was kicked by %s (%s)\n' % (target, msg.nick, kickmsg))
        else:
            self.doLog(irc, channel,
                       '*** %s was kicked by %s\n' % (target, msg.nick))
        self.doKickban(irc, channel, msg.nick, target, kickmsg)

    def doPart(self, irc, msg):
        for channel in msg.args[0].split(','):
            self.doLog(irc, channel, '*** %s (%s) has left %s (%s)\n' % (msg.nick, msg.prefix, channel, msg.args[1]))
            if msg.args[1].startswith('requested by'):
                args = msg.args[1].split()
                self.doKickban(irc, channel, args[2].replace(':',''), msg.nick, ' '.join(args[3:])[1:-1].strip())

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
                            if plusmin: self.doKickban(irc, channel, msg.nick, msg.args[i])
                            else: self.doUnban(irc,channel, msg.nick, msg.args[i])
                            i += 1
                        if c == 'd':
                            if plusmin: self.doKickban(irc, channel, msg.nick, msg.args[i] + ' (realname)')
                            else: self.doUnban(irc,channel, msg.nick, msg.args[i] + ' (realname)')
                            i += 1

    def doTopic(self, irc, msg):
        if len(msg.args) == 1:
            return # It's an empty TOPIC just to get the current topic.
        channel = msg.args[0]
        self.doLog(irc, channel,
                   '*** %s changes topic to "%s"\n' % (msg.nick, msg.args[1]))

    def doQuit(self, irc, msg):
        for (channel, chan) in self.lastStates[irc].channels.iteritems():
            if msg.nick in chan.users:
                self.doLog(irc, channel, '*** %s has quit IRC (%s)\n' % (msg.nick, msg.args[0]))

    def outFilter(self, irc, msg):
        # Gotta catch my own messages *somehow* :)
        # Let's try this little trick...
        if msg.command in ('PRIVMSG', 'NOTICE'):
            # Other messages should be sent back to us.
            m = ircmsgs.IrcMsg(msg=msg, prefix=irc.prefix)
            self(irc, m)
        return msg
        
    def check_auth(self, irc, msg, args):
        if not msg.tagged('identified'):
            irc.error(conf.supybot.replies.incorrectAuthentication())
            return False
        try:
            user = ircdb.users.getUser(msg.prefix[:msg.prefix.find('!')].lower())
        except:
            irc.error(conf.supybot.replies.incorrectAuthentication())
            return False

        if not capab(user, 'bantracker'):
            irc.error(conf.supybot.replies.noCapability() % 'bantracker')
            return False
        return user

    def btlogin(self, irc, msg, args):
        """takes no arguments

        Sends you a message with a link to login to the bantracker.
        """
        user = self.check_auth(irc, msg, args)
        if not user:
            return
        user.addAuth(msg.prefix)
        ircdb.users.setUser(user, flush=False)

        if not capab(user, 'bantracker'):
            irc.error(conf.supybot.replies.noCapability() % 'bantracker')
            return
        if not self.registryValue('bansite'):
            irc.error("No bansite set, please set supybot.plugins.Bantracker.bansite")
            return
        sessid = md5.new('%s%s%d' % (msg.prefix, time.time(), random.randint(1,100000))).hexdigest()
        self.db_run("INSERT INTO sessions (session_id, user, time) VALUES (%s, %s, %d);", 
               (sessid, msg.prefix[:msg.prefix.find('!')], int(time.time())))
        irc.reply('Log in at %s/bans/cgi?sess=%s' % (self.registryValue('bansite'), sessid), private=True)

    btlogin = wrap(btlogin)

    def mark(self, irc, msg, args, channel, target, kickmsg):
        """<nick|hostmask> [<channel>] [<comment>]

        Creates an entry in the Bantracker as if <nick|hostmask> was kicked from <channel> with the comment <comment>,
        if <comment> is given it will be uses as the comment on the Bantracker, <channel> is only needed when send in /msg
        """
        user = self.check_auth(irc, msg, args)
        if not user:
            return
        user.addAuth(msg.prefix)
        ircdb.users.setUser(user, flush=False)

        if not channel:
            irc.error('<channel> must be given if not in a channel')
            return
        channels = []
        for (chan, c) in irc.state.channels.iteritems():
            channels.append(chan)

        if not channel in channels:
            irc.error('Not in that channel')
            return

        if not kickmsg:
            kickmsg = '**MARK**'
        else:
            kickmsg = "**MARK** - %s" % kickmsg
        if ircutils.isUserHostmask(target):
            hostmask = target
        else:
            try:
                hostmask = irc.state.nickToHostmask(target)
            except:
                irc.reply('Could not get hostmask, using nick instead')
                hostmask = target

        self.doLog(irc, channel.lower(), '*** %s requested a mark for %s\n' % (msg.nick, target))
        self.doKickban(irc, channel.lower(), msg.nick, hostmask, kickmsg)
        irc.replySuccess()

    mark = wrap(mark, [optional('channel'), 'something', additional('text')])

    def nick_to_host(irc, target):
        if ircutils.isUserHostmask(target):
            return target
        else:
            try:
                return irc.state.nickToHostmask(target)
            except:
                return "%s!*@*" % target
    nick_to_host = staticmethod(nick_to_host)

    def sort_bans(self, channel=None):
        data = self.db_run("SELECT mask, removal, channel, id FROM bans", (), expect_result=True)
        if channel:
            data = [i for i in data if i[2] == channel]
        data = [i for i in data if i[1] == None]
        mutes = [(i[0][1:], i[3]) for i in data if i[0][0] == '%']
        bans = [(i[0], i[3]) for i in data if i[0][0] != '%']
        return mutes + bans

    def bansearch(self, irc, msg, args, target, channel):
        """<nick|hostmask> [<channel>]

        Search bans database for a ban on nick/host,
        if channel is not given search all channel bans.
        """
        def format_entry(entry):
            ret = list(entry[:-1])
            t = cPickle.loads(entry[-1]).astimezone(pytz.timezone('UTC')).strftime("%b %d %Y %H:%M:%S")
            ret.append(t)
            return tuple(ret)

        if not self.check_auth(irc, msg, args):
            return

        hostmask = self.nick_to_host(irc, target)
        data = self.sort_bans(channel)

        match = []
        for e in data:
            if ircutils.hostmaskPatternEqual(e[0], hostmask):
                match.append((e[0], e[1]))

        if not match:
            irc.reply("No matches found for %s in %s" % (hostmask, True and channel or "any channel"))
            return
        ret = []
        for m in match:
            ret.append(format_entry(self.db_run("SELECT mask, operator, channel, time FROM bans WHERE id=%d", m[1], expect_result=True)[0]))
        for i in ret:
            irc.reply("Match: %s by %s in %s on %s" % i)

    bansearch = wrap(bansearch, ['something', optional('anything', default=None)])

    def banlog(self, irc, msg, args, target, channel):
        """<nick|hostmask> [<channel>]

        Prints the last 5 messages from the nick/host logged before a ban/mute,
        the nick/host has to have an active ban/mute against it.
        If channel is not given search all channel bans.
        """
        if not self.check_auth(irc, msg, args):
            return

        hostmask = self.nick_to_host(irc, target)
        target = hostmask.split('!')[0]
        data = self.sort_bans(channel)

        match = []
        for e in data:
            if ircutils.hostmaskPatternEqual(e[0], hostmask):
                match.append((e[0], e[1]))

        sent = []

        if not match:
            irc.reply("No matches found for %s (%s) in %s" % (target, hostmask, True and channel or "any channel"))
            return
        ret = []
        for m in match:
            ret.append(self.db_run("SELECT log FROM bans WHERE id=%d", m[1], expect_result=True))

        for log in ret:
            lines = [i for i in log[0][0].split('\n') if "<%s>" % target.lower() in i.lower() and i[21:21+len(target)].lower() == target.low$
            if not lines:
                irc.error("No log for %s available" % target)
            for l in lines[:5]:
                if l not in sent:
                    irc.reply(l)
                    sent.append(l)
            irc.reply('--')

    banlog = wrap(banlog, ['something', optional('anything', default=None)])

Class = Bantracker

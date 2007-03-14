###
# Copyright (c) 2006-2007 Dennis Kaarsemaker
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

from supybot.commands import *
import supybot.ircmsgs as ircmsgs
import supybot.callbacks as callbacks
import sqlite, datetime, time
import supybot.registry as registry
import supybot.ircdb as ircdb
import supybot.conf as conf
import re, os, time
import packages
reload(packages)

# Simple wrapper class for factoids
class Factoid:
    def __init__(self, name, value, author, added, popularity):
        self.name = name;     self.value = value
        self.author = author; self.added = added
        self.popularity = popularity

class FactoidSet:
    def __init__(self):
        self.global_primary = self.global_secondary = \
        self.channel_primary = self.channel_secondary = None

# Repeat filtering message queue
msgcache = {}
def queue(irc, to, msg):
    now = time.time()
    for m in msgcache.keys():
        if msgcache[m] < now - 30:
            msgcache.pop(m)
    for m in msgcache:
        if m[0] == irc and m[1] == to:
            oldmsg = m[2]
            if msg == oldmsg or oldmsg.endswith(msg):
                break
            if msg.endswith(oldmsg):
                msg = msg[:-len(oldmsg)] + 'please see above'
    else:
        msgcache[(irc, to, msg)] = now
        irc.queueMsg(ircmsgs.privmsg(to, msg))

def capab(prefix, capability):
    try:
        ircdb.users.getUser(prefix)
        return ircdb.checkCapability(prefix, capability)
    except:
        return False

class Encyclopedia(callbacks.Plugin):
    """!factoid: show factoid"""
    threaded = True

    def __init__(self, irc):
        callbacks.Plugin.__init__(self, irc)
        self.databases = {}
        self.times = {}
        self.seens = {}
        self.distros = []
        self.Apt = packages.Apt(self)
        self.edits = {}

    def addeditor(self, irc, msg, args, name):
        if not capab(msg.prefix, 'addeditors'):
            return
        try:
            u = ircdb.users.getUser(name)
            u.addCapability('editfactoids')
            irc.replySuccess()
        except:
            irc.error('User %s is not registered' % name)
    addeditor = wrap(addeditor, ['text'])

    def removeeditor(self, irc, msg, args, name):
        if not capab(msg.prefix, 'addeditors'):
            return
        try:
            u = ircdb.users.getUser(name)
            u.removeCapability('editfactoids')
            irc.replySuccess()
        except:
            irc.error('User %s is not registered or not an editor' % name)
    removeeditor = wrap(removeeditor, ['text'])

    def editors(self, irc, msg, args):
        irc.reply(', '.join([ircdb.users.getUser(u).name for u in ircdb.users.users \
                             if 'editfactoids' in ircdb.users.getUser(u).capabilities]))
    editors = wrap(editors)

    def moderators(self, irc, msg, args):
        irc.reply(', '.join([ircdb.users.getUser(u).name for u in ircdb.users.users \
                             if 'addeditors' in ircdb.users.getUser(u).capabilities]))
    moderators = wrap(moderators)

    def get_target(self, nick, text, orig_target):
        target = orig_target
        retmsg = ''
        
        if text.startswith('tell '):
            text = ' ' + text

        if '>' in text:
            target = text[text.rfind('>')+1:].strip().split()[0]
            text = text[:text.rfind('>')].strip()
            retmsg = "%s wants you to know: " % nick

        elif ' tell ' in text and ' about ' in text:
            target = text[text.find(' tell ')+6:].strip().split(None,1)[0]
            text = text[text.find(' about ')+7:].strip()
            retmsg = "%s wants you to know: " % nick
            
        if '|' in text:
            if not retmsg:
                retmsg = text[text.find('|')+1:].strip() + ': '
            text = text[:text.find('|')].strip()

        if target == 'me':
            target = nick
        if target.lower() != orig_target.lower() and target.startswith('#'):
            target = orig_target
            retmsg = ''

        if (target.lower() == nick.lower() or retmsg[:-2].lower() == nick.lower()) and nick.lower() != orig_target.lower():
            target = nick
            retmsg = '(In the future, please use a private message to investigate) '

        return (text, target, retmsg)

    def get_db(self, channel):
        db = self.registryValue('database',channel)
        if channel in self.databases:
            if self.databases[channel].time < time.time - 3600:
                self.databases[channel].close()
                self.databases.pop(channel)
        if channel not in self.databases:
            self.databases[channel] = sqlite.connect(os.path.join(self.registryValue('datadir'), '%s.db' % db))
            self.databases[channel].name = db
            self.databases[channel].time = time.time()
        return self.databases[channel]

    def addressed(self, recipients, text, irc):
        if recipients[0] == '#':
            text = text.strip()
            if text.lower() == self.registryValue('prefixchar', channel=recipients) + irc.nick.lower():
                return irc.nick.lower()
            if len(text) and text[0] ==
            self.registryValue('prefixchar',channel=recipients):
                text = text[1:]
                if text.lower().startswith(irc.nick.lower()) and (len(text) < 5 or not text[5].isalnum()):
                    t2 = text[5:].strip()
                    if t2 and t2.find('>') != 0 and t2.find('|') != 0:
                        text = text[5:].strip()
                return text
            if text.lower().startswith(irc.nick) and not text[5].isalnum():
                return text[5:]
            return False
        else: # Private
            if text.strip()[0] in str(conf.supybot.reply.whenAddressedBy.chars):
                return False
            for c in irc.callbacks:
                comm = text.split()[0]
                if c.isCommandMethod(comm) and not c.isDisabled(comm):
                    return False
            if text[0] == self.registryValue('prefixchar',channel=recipients):
                return text[1:]
            return text
            
    def get_factoids(self, name, channel, resolve = True, info = False):
        factoids = FactoidSet()
        factoids.global_primary    = self.get_single_factoid(channel, name)
        factoids.global_secondary  = self.get_single_factoid(channel, name + '-also')
        factoids.channel_primary   = self.get_single_factoid(channel, name + '-' + channel)
        factoids.channel_secondary = self.get_single_factoid(channel, name + '-' + channel + '-also')
        if resolve:
            factoids.global_primary    = self.resolve_alias(channel, factoids.global_primary)
            factoids.global_secondary  = self.resolve_alias(channel, factoids.global_secondary)
            factoids.channel_primary   = self.resolve_alias(channel, factoids.channel_primary)
            factoids.channel_secondary = self.resolve_alias(channel, factoids.channel_secondary)
        if info:
        # Get aliases for factoids
            factoids.global_primary    = self.factoid_info(channel, factoids.global_primary)
            factoids.global_secondary  = self.factoid_info(channel, factoids.global_secondary)
            factoids.channel_primary   = self.factoid_info(channel, factoids.channel_primary)
            factoids.channel_secondary = self.factoid_info(channel, factoids.channel_secondary)
        return factoids
        
    def get_single_factoid(self, channel, name, deleted=False):
        db = self.get_db(channel)
        cur = db.cursor()
        if deleted:
            cur.execute("SELECT name, value, author, added, popularity FROM facts WHERE name = %s", name)
        else:
            cur.execute("SELECT name, value, author, added, popularity FROM facts WHERE name = %s AND value NOT like '<deleted>%%'", name)
        factoids = cur.fetchall()
        if len(factoids):
            f = factoids[0]
            return Factoid(f[0],f[1],f[2],f[3],f[4])

    def resolve_alias(self, channel, factoid, loop=0):
        if loop >= 10:
            return Factoid('','<reply> Error: infinite <alias> loop detected','','',0)
        if factoid and factoid.value.lower().startswith('<alias>'):
            new_factoids = self.get_factoids(factoid.value[7:].lower().strip(), channel, False)
            for x in ['channel_primary', 'global_primary']:
                if getattr(new_factoids, x):
                    return self.resolve_alias(channel, getattr(new_factoids, x), loop+1)
            return Factoid('','<reply> Error: unresolvable <alias> to %s' % factoid.value[7:].lower().strip(),'','',0)
        else:
            return factoid

    def factoid_info(self, channel, factoid):
        if not factoid:
            return
        if not factoid.value.startswith('<alias>'):
            # Try and find aliases
            db = self.get_db(channel)
            cur = db.cursor()
            cur.execute("SELECT name FROM facts WHERE value = %s", '<alias> ' + factoid.name)
            data = cur.fetchall()
            if data:
                factoid.value = "<reply> %s aliases: %s" % (factoid.name, ', '.join([x[0] for x in data]))
            else:
                factoid.value = "<reply> %s has no aliases" % (factoid.name)
        # Author info
        factoid.value += " - added by %s on %s" % (factoid.author[:factoid.author.find('!')], factoid.added[:factoid.added.find('.')])
        return factoid

    def check_aliases(self, channel, factoid):
        now = time.time()
        for e in self.edits.keys():
            if self.edits[e] + 10 < now:
                self.edits.pop(e)
        if not factoid.value.startswith('<alias>'):
            return
        # Was the old value an alias?
        oldf = self.get_single_factoid(channel, factoid.name)
        if oldf and oldf.value.startswith('<alias>'):
            if factoid.name not in self.edits:
                self.edits[factoid.name] = now
                return "You are editing an alias. Please repeat the edit command within the next 10 seconds to confirm"
        # Do some alias resolving
        if factoid.value.startswith('<alias>'):
            aliasname = factoid.value[7:].strip()
            alias = self.get_single_factoid(channel, aliasname)
            if not alias:
                return "Factoid '%s' does not exist" % aliasname
            alias = self.resolve_alias(channel, factoid)
            if alias.value.lower().startswith('error'):
                return alias.value.lower
            factoid.value = '<alias> ' + alias.name

    def doPrivmsg(self, irc, msg):
        # Filter CTCP
        if chr(1) in msg.args[1]:
            return

        # Are we being queried?
        recipient, text = msg.args
        text = self.addressed(recipient, text, irc)
        if not text:
            return
        display_info = False
        target = msg.args[0]
        if target[0] != '#':
            target = msg.nick
        channel = msg.args[0]

        # Strip leading nonalnums
        while text and not text[0].isalnum():
            if text[0] == '-':
                display_info = True
            text = text[1:]
        if not text:
            return
            
        # Now switch between actions
        orig_text = text
        lower_text = text.lower()
        ret = ''
        retmsg = ''
        if lower_text[:4] not in ('info','find'):
            # Lookup, search or edit?
            if lower_text.startswith('search '):
                ret = self.search_factoid(lower_text[7:].strip(), channel)
            elif (' is ' in lower_text and text[:3] in ('no ', 'no,')) or '<sed>' in lower_text or '=~' in lower_text \
                or lower_text.startswith('forget') or lower_text.startswith('unforget'):
                if not capab(msg.prefix, 'editfactoids'):
                    irc.reply("Your edit request has been forwarded to %s.  Thank you for your attention to detail" %
                              self.registryValue('relaychannel'),private=True)
                    irc.queueMsg(ircmsgs.privmsg(self.registryValue('relaychannel'), "In %s, %s said: %s" %
                                                 (msg.args[0], msg.nick, msg.args[1])))
                    return
                ret = self.factoid_edit(text, channel, msg.prefix)
            elif ' is ' in text and '|' not in text:
                if not capab(msg.prefix, 'editfactoids'):
                    if len(text[:text.find('is')]) > 15:
                        irc.error("I am only a bot, please don't think I'm intelligent :)")
                    else:
                        irc.reply("Your edit request has been forwarded to %s.  Thank you for your attention to detail" %
                                  self.registryValue('relaychannel'),private=True)
                        irc.queueMsg(ircmsgs.privmsg(self.registryValue('relaychannel'), "In %s, %s said: %s" %
                                                     (msg.args[0], msg.nick, msg.args[1])))
                    return
                ret = self.factoid_add(text, channel, msg.prefix)
            else:
                text, target, retmsg = self.get_target(msg.nick, orig_text, target)
                ret = self.factoid_lookup(text, channel, display_info)

        # Fall through to package lookup
        if self.registryValue('packagelookup') and (not ret or not len(ret)):
            text, target, retmsg = self.get_target(msg.nick, orig_text.lower(), target)
            if text.startswith('info '):
                ret = self.Apt.info(text[5:].strip(),self.registryValue('searchorder', channel).split())
            elif text.startswith('find '):
                ret = self.Apt.find(text[5:].strip(),self.registryValue('searchorder', channel).split())
            else:
                ret = self.Apt.info(text.strip(),self.registryValue('searchorder', channel).split())
                if ret.startswith('Package'):
                    ret = None

        if not ret:
            if len(text) > 15:
                irc.error("I am only a bot, please don't think I'm intelligent :)")
                return
            retmsg = ''
            ret = self.registryValue('notfoundmsg')
            if ret.count('%') == ret.count('%s') == 1:
                ret = ret % text
        if type(ret) != list:
            queue(irc, target, retmsg + ret)
        else:
            queue(irc, target, retmsg + ret[0])
            for r in ret[1:]:
                queue(irc, target, r)

    def factoid_edit(self, text, channel, editor):
        db = self.get_db(channel)
        cs = db.cursor()
        factoid = retmsg = None

        def log_change(factoid):
            cs.execute('''insert into log (author, name, added, oldvalue) values (%s, %s, %s, %s)''',
                     (editor, factoid.name, str(datetime.datetime.now()), factoid.value))
            db.commit()
    
        if text.lower().startswith('forget '):
            factoid = self.get_single_factoid(channel, text[7:])
            if not factoid:
                return "I know nothing about %s yet, %s" % (text[7:], editor[:editor.find('!')])
            else:
                log_change(factoid)
                factoid.value = '<deleted>' + factoid.value
                retmsg = "I'll forget that, %s" % editor[:editor.find('!')]
                
        if text.lower().startswith('unforget '):
            factoid = self.get_single_factoid(channel, text[9:], deleted=True)
            if not factoid:
                return "I knew nothing about %s at all, %s" % (text[9:], editor[:editor.find('!')])
            else:
                if not factoid.value.startswith('<deleted>'):
                    return "Factoid %s wasn't deleted yet, %s" % (factoid.name, editor[:editor.find('!')])
                log_change(factoid)
                factoid.value = factoid.value[9:]
                retmsg = "I suddenly remember %s again, %s" % (factoid.name, editor[:editor.find('!')])

        if text.lower()[:3] in ('no ', 'no,'):
            text = text[3:].strip()
            p = text.lower().find(' is ')
            name, value = text[:p].strip(), text[p+4:].strip()
            if not name or not value:
                return
            name = name.lower()
            factoid = self.get_single_factoid(channel, name)
            if not factoid:
                return "I know nothing about %s yet, %s" % (name, editor[:editor.find('!')])
            log_change(factoid)
            factoid.value = value
            retmsg = "I'll remember that %s" % editor[:editor.find('!')]
        
        if not retmsg:
            if ' is<sed>' in text:
                text = text.replace('is<sed>','=~',1)
            if ' is <sed>' in text:
                text = text.replace('is <sed>','=~',1)
            # Split into name and regex
            name = text[:text.find('=~')].strip()
            regex = text[text.find('=~')+2:].strip()
            # Edit factoid
            factoid = self.get_single_factoid(channel, name)
            if not factoid:
                return "I know nothing about %s yet, %s" % (name, editor[:editor.find('!')])
            # Grab the regex
            if regex.startswith('s'):
                regex = regex[1:]
            if regex[-1] != regex[0]:
                return "Missing end delimiter"
            if regex.count(regex[0]) != 3:
                return "Too many (or not enough) delimiters"
            regex, replace = regex[1:-1].split(regex[0])
            try:
                regex = re.compile(regex)
            except:
                return "Malformed regex"
            newval = regex.sub(replace, factoid.value, 1)
            if newval == factoid.value:
                return "Nothing changed there"
            log_change(factoid)
            factoid.value = newval
            retmsg = "I'll remember that %s" % editor[:editor.find('!')]

        ret = self.check_aliases(channel, factoid)
        if ret:
            return ret
        print("UPDATE facts SET value=%s where name=%s", (factoid.value,factoid.name))
        cs.execute("UPDATE facts SET value=%s where name=%s", (factoid.value,factoid.name))
        db.commit()
        return retmsg

    def factoid_add(self, text, channel, editor):
        db = self.get_db(channel)
        cs = db.cursor()

        p = text.lower().find(' is ')
        name, value = text[:p].strip(), text[p+4:].strip()
        if not name or not value:
            return
        name = name.lower()
        if value.startswith('also '):
            name += '-also'
            value = value[5:].strip()
            if not value:
                return
        if self.get_single_factoid(channel, name, deleted=True):
            return "But %s already means something else!" % name
        factoid = Factoid(name,value,None,None,None)
        ret = self.check_aliases(channel, factoid)
        if ret:
            return ret
        cs.execute("""INSERT INTO facts (name, value, author, added) VALUES (%s, %s, %s, %s)""",
                    (name, value, editor, str(datetime.datetime.now())))
        db.commit()
        return "I'll remember that, %s" % editor[:editor.find('!')]

    def factoid_lookup(self, text, channel, display_info):
        db = self.get_db(channel)
        factoids = self.get_factoids(text.lower(), channel, resolve = not display_info, info = display_info)
        ret = []
        for order in ('primary', 'secondary'):
            for loc in ('channel', 'global'):
                key = '%s_%s' % (loc, order)
                if getattr(factoids, key):
                    factoid = getattr(factoids,key)
                    if not display_info:
                        cur = db.cursor()
                        cur.execute("UPDATE FACTS SET popularity = %d WHERE name = %s", factoid.popularity+1, factoid.name)
                        db.commit()
                    if factoid.value.startswith('<reply>'):
                        ret.append(factoid.value[7:].strip().replace('$chan',channel))
                    elif order == 'secondary':
                        ret.append(factoid.value.strip().replace('$chan',channel))
                    else:
                        n = factoid.name
                        if '-#' in n:
                            n = n[:n.find('-#')]
                        ret.append('%s is %s' % (n, factoid.value.replace('$chan',channel)))
                    if not display_info:
                        break
        return ret

    def search_factoid(self, factoid, channel):
        keys = factoid.split()[:5]
        db = self.get_db(channel)
        cur = db.cursor()
        ret = {}
        for k in keys:
            k = k.replace("'","\'")
            cur.execute("SELECT name,value FROM facts WHERE name LIKE '%%%s%%' OR VAlUE LIKE '%%%s%%'" % (k, k))
            res = cur.fetchall()
            for r in res:
                d = r[1].startswith('<deleted>')
                r = r[0]
                if d:
                    r += '*'
                try:
                    ret[r] += 1
                except:
                    ret[r] = 1
        return 'Found: %s' % ', '.join(sorted(ret.keys(), lambda x, y: cmp(ret[x], ret[y]))[:10])

Class = Encyclopedia

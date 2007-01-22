###
# Copyright (c) 2006, Dennis Kaarsemaker
# All rights reserved.
#
#
###

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.ircmsgs as ircmsgs
import supybot.callbacks as callbacks
import sqlite, datetime, time, apt_pkg, commands
import supybot.registry as registry
import supybot.ircdb as ircdb
from email import FeedParser
import re, os, fcntl, time
apt_pkg.init()

datadir = '/home/dennis/ubugtu/data/facts'
aptdir = '/home/dennis/ubugtu/data/apt'
logdir = '/var/www/bots.ubuntulinux.nl/'
distros = ('dapper','edgy','feisty','breezy','edgy','dapper-commercial','dapper-seveas','breezy-seveas','dapper-imbrandon','edgy-imbrandon', 'dapper-backports','edgy-seveas')

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

msgcache = {}
def queue(irc, to, msg):
    now = time.time()
    for m in msgcache.keys():
        if msgcache[m] < now - 30:
            msgcache.pop(m)
    if (irc, to, msg) not in msgcache:
        msgcache[(irc, to, msg)] = now
        irc.queueMsg(ircmsgs.privmsg(to, msg))

class Encyclopedia(callbacks.Plugin):
    """!factoid: show factoid"""
    threaded = True

    def __init__(self, irc):
        callbacks.Plugin.__init__(self, irc)
        self.databases = {}
        self.times = {}
        self.seens = {}

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

    def _checkdists(self, channel):
        cd = self.registryValue('searchorder', channel=channel)
        return cd.split()
    
    def moderators(self, irc, msg, args):
        irc.reply(', '.join([ircdb.users.getUser(u).name for u in ircdb.users.users \
                             if 'addeditors' in ircdb.users.getUser(u).capabilities]))
    moderators = wrap(moderators)

    # Parse seenservs replies
    def doNotice(self, irc, msg):
        if msg.nick.lower() != 'seenserv':
            return
        resp = msg.args[1]
        for n in self.seens.keys():
            if self.seens[n][1] < time.time() - 10:
                self.seens.pop(n)
        for n in self.seens.keys():
            if n.lower() in resp.lower():
                queue(irc, self.seens[n][0], resp)
                self.seens.pop(n)

    def doPrivmsg(self, irc, msg):
        if chr(1) in msg.args[1]:
            return
        recipient, text = msg.args
        text = addressed(recipient, text, irc)
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
        # XXX these 3 belong in a different plugin, but hey
        if text.lower()[:4] in ('info','seen','find'):
            text = text.lower()
        if self.registryValue('packagelookup'):
            if text.startswith('info '):
                queue(irc, target, pkginfo(text[5:].strip(),self._checkdists(msg.args[0])))
                return
            if text.startswith('find '):
                queue(irc, target, findpkg(text[5:].strip(),self._checkdists(msg.args[0])))
                return
            if text.startswith('seen '):
                self.seens[text[5:].strip()] = (target, time.time())
                queue(irc, 'seenserv', "seen %s" % text[5:].strip())
                return

        # Factoid manipulation
        db = self.registryValue('database',channel)
        if not db:
            db,channel = self.registryValue('fallbackdb'), self.registryValue('fallbackchannel')
        if channel not in self.databases:
            self.databases[channel] = sqlite.connect(os.path.join(datadir, '%s.db' % db))
            self.databases[channel].name = db
        db = self.databases[channel]
        
        if text.lower().startswith('search '):
            irc.reply(searchfactoid(db, text[7:].strip().lower()))
            return
        do_new = False
        if text.lower().startswith('forget '):
            if ' is ' in text.lower() or text.lower().endswith(' is'):
                return # Bad hack attempt :)
            text = '%s =~ s/^/<deleted>/' % text[7:]
        if text.lower().startswith('unforget '):
            if ' is ' in text.lower() or text.lower().endswith(' is'):
                return # Bad hack attempt :)
            text = '%s =~ s/^<deleted>//' % text[9:]
        if ' is<sed>' in text:
            text = text.replace('is<sed>','=~',1)
        elif ' is <sed>' in text:
            text = text.replace('is <sed>','=~',1)
        if ' is ' in text and '=~' not in text and not ('|' in text and text.find(' is ') > text.find('|')):
            do_new = True
            if text.lower()[:3] in ('no ','no,'):
                do_new = False
                text = text[3:].strip()
            if text.startswith('is '):
                return
            p = text.lower().find(' is ')
            n, v = text[:p].strip(), text[p+4:].strip()
            if not n or not v:
                return
            for c in '!#@$^*/':
                if c not in text:
                    text = '%s =~ s%s.*%s%s%s' % (n, c, c, v, c)
                    break
            else:
                irc.error('Internal error, please report')
                return
        # Big action 1: editing factoids
        if '=~' in text:
            # Editing
            # Find factoid
            p = text.find('=~')
            name, value = text[:p].strip(), text[p+2:].strip()
            name = name.lower()
            if value.startswith('also '):
                name += '-also'
                value = value[5:].strip()
            if not capab(msg.prefix, 'editfactoids'):
                if len(name) > 20:
                    irc.error("I am only a bot, please don't think I'm intelligent :)")
                    return
                irc.reply("Your edit request has been forwarded to %s. Thank you for your attention to detail"%self.registryValue('relaychannel'),private=True)
                irc.queueMsg(ircmsgs.privmsg(self.registryValue('relaychannel'), "In %s, %s said: %s" % (msg.args[0], msg.nick, msg.args[1])))
                lfd = open(logdir + '/botlogs/lock','a')
                fcntl.lockf(lfd, fcntl.LOCK_EX)
                fd = open(logdir + '/botlogs/%s.log' % datetime.date.today().strftime('%Y-%m-%d'),'a')
                fd.write("%s  %-20s %-16s  %s\n" % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), channel, msg.nick, msg.args[1]))
                fd.close()
                fcntl.lockf(lfd,fcntl.LOCK_UN)
                lfd.close()
                os.chmod(logdir + '/botlogs/%s.log' % datetime.date.today().strftime('%Y-%m-%d'),0644)
                return
            # All clear!
            #irc.reply(str((name, value)))
            ####
            # Find existing factoid
            newtext = name
            newchannel = channel
            secondary = channel_specific = False
            if newtext.endswith('-also'):
                newtext = newtext[:-5]
                secondary = True
            if '-#' in newtext:
                newchannel = newtext[newtext.find('-#')+1:]
                newtext = newtext[:newtext.find('-#')]
                channel_specific = True
            existing = get_factoids(db, newtext, newchannel, resolve=True)
            # If it is an alias/also and new, check whether it resolves
            if secondary and not (existing.global_primary or existing.channel_primary):
                irc.error("I know nothing about %s yet" % newtext)
                return
            cur = db.cursor()
            # If it is new and exists, bail
            if do_new:
                if real_get_factoid(cur, name):
                    irc.reply("%s is already known" % name)
                    return
            # If it is an edit, but doesn't exist: bail
            else:
                if not real_get_factoid(cur, name):
                    irc.reply("I know nothing about %s yet" % name)
                    return
            # Edit factoid
            f = real_get_factoid(cur, name, True)
            if not f:
                cur.execute("""INSERT INTO facts (name, value, author, added) VALUES
                            (%s, '<deleted>', %s, %s)""", (name, msg.prefix, str(datetime.datetime.now())))
                db.commit()
                f = real_get_factoid(cur, name, True)
            if value.startswith('s'):
                value = value[1:]
            if value[-1] != value[0]:
                irc.reply("Missing end delimiter")
                return
            if value.count(value[0]) != 3:
                irc.reply("Too many (or not enough) delimiters")
                return
            regex, replace = value[1:-1].split(value[0])
            try:
                regex = re.compile(regex)
            except:
                irc.reply("Malformed regex")
                return
            newval = regex.sub(replace, f.value, 1)
            if newval == f.value:
                irc.reply("Nothing changed there")
                return
            f.value = newval
            
            # Check resolving of aliases
            if f.value.startswith('<alias>'):
                alias = f.value[7:].strip()
                if name == alias:
                    irc.error("Recursive <alias> detected. Bailing out!")
                    return
                aliases = get_factoids(db, alias, newchannel, resolve=True)
                if aliases.global_primary:
                    if name == aliases.global_primary.name:
                        irc.error("Recursive <alias> detected. Bailing out!")
                        return
                    f.value = '<alias> ' + aliases.global_primary.name
                elif aliases.channel_primary:
                    f.name += '-%s' % newchannel
                    f.value = '<alias> ' + aliases.channel_primary.name
                else:
                    irc.error("Unresolvable alias: %s" % alias)
                    return
            # Finally, save
            log("(%s) UPDATE facts SET value = %s WHERE name = %s" % (msg.prefix, f.value, f.name))
            cur.execute("UPDATE facts SET value = %s WHERE name = %s", (f.value, f.name))
            db.commit()
            irc.reply("I'll remember that, %s" % msg.nick)
        else:
            # Display a factoid
            # Find recipient
            _target = None
            retmsg = ''
            if '>' in text:
                _target = text[text.rfind('>')+1:].strip()
                text = text[:text.rfind('>')].strip()
            if text.startswith('tell '):
                text = ' ' + text
            if ' tell ' in text and ' about ' in text:
                _target = text[text.find(' tell ')+6:].strip().split(None,1)[0]
                text = text[text.find(' about ')+7:].strip()
            if '|' in text:
                retmsg = text[text.find('|')+1:].strip() + ': '
                text = text[:text.find('|')].strip()
            if _target:
            # Validate
                if _target == 'me':
                    _target = msg.nick
                for chan in irc.state.channels:
                    if _target in irc.state.channels[chan].users and msg.nick in irc.state.channels[chan].users:
                        target = _target   
                        retmsg = '%s wants you to know: ' % msg.nick
                        break
                else:
                    irc.error("That person could not be found in any channel you're in")
                    return
            factoids = get_factoids(db, text.lower(), channel, resolve = not display_info, info = display_info)
            replied = False
            if target.lower() == msg.nick.lower() and msg.args[0][0] == '#':
                queue(irc, target, "To send answers to yourself, please use /msg instead of spamming the channel")
            for key in ('channel_primary', 'global_primary'):
                if getattr(factoids, key):
                    replied = True
                    factoid = getattr(factoids,key)
                    if not display_info:
                        cur = db.cursor()
                        cur.execute("UPDATE FACTS SET popularity = %d WHERE name = %s", factoid.popularity+1, factoid.name)
                        db.commit()
                    if factoid.value.startswith('<reply>'):
                        #irc.queueMsg(ircmsgs.privmsg(target, '%s%s' % (retmsg, factoid.value[7:].strip())))
                        queue(irc, target, '%s%s' % (retmsg, factoid.value[7:].strip().replace('$chan',channel)))
                    else:
                        #irc.queueMsg(ircmsgs.privmsg(target, '%s%s is %s' % (retmsg, factoid.name, factoid.value.strip())))
                        queue(irc, target, '%s%s is %s' % (retmsg, factoid.name, factoid.value.strip().replace('$chan',channel)))
                    if not display_info:
                        break
            else:
                if not replied:
                    if self.registryValue('packagelookup'):
                        i = pkginfo(text,self._checkdists(msg.args[0]))
                        if not i.startswith('Package'):
                            queue(irc, target, i)
                        else:
                            if len(text) > 16:
                                irc.error("I am only a bot, please don't think I'm intelligent :)")
                                return
                            irc.reply(self.registryValue('notfoundmsg') % text)
                    else:
                        if len(text) > 16:
                            irc.error("I am only a bot, please don't think I'm intelligent :)")
                            return
                        irc.reply(self.registryValue('notfoundmsg') % text)
            for key in ('channel_secondary', 'global_secondary'):
                if getattr(factoids, key):
                    factoid = getattr(factoids,key)
                    #irc.queueMsg(ircmsgs.privmsg(target, '%s%s' % (retmsg, factoid.value.strip())))
                    queue(irc, target, '%s%s' % (retmsg, factoid.value.strip()))
                    if not display_info:
                        break

msgcache = {}
def send(irc, to, msg):
    now = time.time()
    for k in msgcache:
        if now - msgcache[k] > 10:
            msgcache.pop(k)
    k = (irc, to, msg)
    if k not in msgcache:
        msgcache[k] = time.time()
        irc.queueMsg(ircmsgs.privmsg(to, msg))
        
def addressed(recipients, text, irc):
    if recipients[0] == '#':
        text = text.strip()
        if text.lower() == '!ubotu':
            return 'ubotu'
        if text[0] == '!':
            text = text[1:]
            if text.lower().startswith('ubotu') and (len(text) < 5 or not text[5].isalnum()):
                t2 = text[5:].strip()
                if t2 and t2.find('>') != 0 and t2.find('|') != 0:
                    text = text[5:].strip()
            return text
        if text.lower().startswith('ubotu') and not text[5].isalnum(): # FIXME: use nickname variable
            return text[5:]
        return False
    else: # Private messages
        if text.strip()[0] == '%': # FIXME: replywhenaddressed.chars oslt
            return False
        for c in irc.callbacks:
            comm = text.split()[0]
            if c.isCommandMethod(comm) and not c.isDisabled(comm):
                return False
        if text[0] == '!':
            return text[1:]
        #if text.lower().startswith('ubotu'): # FIXME: use nickname variable
        #    return text[5:]
        return text

aptcommand = """apt-cache\\
                 -o"Dir::State::Lists=%s/%%s"\\
                 -o"Dir::etc::sourcelist=%s/%%s.list"\\
                 -o"Dir::State::status=%s/%%s.status"\\
                 -o"Dir::Cache=%s/cache"\\
                 %%s %%s""" % tuple([aptdir]*4)
aptfilecommand = """apt-file -s %s/%%s.list -c %s/apt-file/%%s -l -F search %%s""" % tuple([aptdir]*2)
def findpkg(pkg,checkdists,filelookup=True):
    _pkg = ''.join([x for x in pkg.strip().split(None,1)[0] if x.isalnum or x in '.-_+'])
    distro = checkdists[0]
    if len(pkg.strip().split()) > 1:
        distro = ''.join([x for x in pkg.strip().split(None,2)[1] if x.isalnum or x in '.-_+'])
    if distro not in distros:
        distro = checkdists[0]
    pkg = _pkg

    data = commands.getoutput(aptcommand % (distro, distro, distro, 'search -n', pkg))
    if not data:
        if filelookup:
            data = commands.getoutput(aptfilecommand % (distro, distro, pkg)).split()
            if data:
                if len(data) > 5:
                    return "File %s found in %s (and %d others)" % (pkg, ', '.join(data[:5]), len(data)-5)
                return "File %s found in %s" % (pkg, ', '.join(data))
            return 'Package/file %s does not exist in %s' % (pkg, distro)
        return "No packages matching '%s' could be found" % pkg
    pkgs = [x.split()[0] for x in data.split('\n')]
    if len(pkgs) > 5:
        return"Found: %s (and %d others)" % (', '.join(pkgs[:5]), len(pkgs) -5)
    else:
        return "Found: %s" % ', '.join(pkgs[:5])

def pkginfo(pkg,checkdists):
    _pkg = ''.join([x for x in pkg.strip().split(None,1)[0] if x.isalnum() or x in '.-_+'])
    distro = None
    if len(pkg.strip().split()) > 1:
        distro = ''.join([x for x in pkg.strip().split(None,2)[1] if x.isalnum() or x in '-._+'])
    if distro:
        if distro not in distros:
            checkdists = [checkdists[0]]
        else:
            checkdists = [distro]
    pkg = _pkg

    for distro in checkdists:
        data = commands.getoutput(aptcommand % (distro, distro, distro, 'show', pkg))
        data2 = commands.getoutput(aptcommand % (distro, distro, distro, 'showsrc', pkg))
        if not data or 'E: No packages found' in data:
            continue
        maxp = {'Version': '0'}
        packages = [x.strip() for x in data.split('\n\n')]
        for p in packages:
            if not p.strip():
                continue
            parser = FeedParser.FeedParser()
            parser.feed(p)
            p = parser.close()
            if apt_pkg.VersionCompare(maxp['Version'], p['Version']) < 0:
                maxp = p
            del parser
        maxp2 = {'Version': '0'}
        packages2 = [x.strip() for x in data2.split('\n\n')]
        for p in packages2:
            if not p.strip():
                continue
            parser = FeedParser.FeedParser()
            parser.feed(p)
            p = parser.close()
            if apt_pkg.VersionCompare(maxp2['Version'], p['Version']) < 0:
                maxp2 = p
            del parser
        archs = ''
        if maxp2['Architecture'] not in ('all','any'):
            archs = ' (Only available for %s)' % maxp2['Architecture']
        return("%s: %s. In component %s, is %s. Version %s (%s), package size %s kB, installed size %s kB%s" %
               (maxp['Package'], maxp['Description'].split('\n')[0], component(maxp['Section']),
                maxp['Priority'], maxp['Version'], distro, int(maxp['Size'])/1024, maxp['Installed-Size'], archs))
    if len(checkdists) > 1:
        return 'Package %s does not exist in any distro I know' % pkg
    return 'Package %s does not exist in %s' % (pkg, distro)
                       
def component(arg):
    if '/' in arg: return arg[:arg.find('/')]
    return 'main'

def real_get_factoid(cur,name,deleted=False):
    if deleted:
        cur.execute("SELECT name, value, author, added, popularity FROM facts WHERE name = %s", name)
    else:
        cur.execute("SELECT name, value, author, added, popularity FROM facts WHERE name = %s AND value NOT like '<deleted>%%'", name)
    factoid = cur.fetchall()
    if len(factoid):
        f = factoid[0]
        return Factoid(f[0],f[1],f[2],f[3],f[4])

def get_factoids(db, name, channel, resolve = True, info = False):
    cur = db.cursor()
    factoids = FactoidSet()
    factoids.global_primary    = real_get_factoid(cur, name)
    factoids.global_secondary  = real_get_factoid(cur, name + '-also')
    factoids.channel_primary   = real_get_factoid(cur, name + '-' + channel)
    factoids.channel_secondary = real_get_factoid(cur, name + '-' + channel + '-also')
    if resolve:
        factoids.global_primary    = resolve_alias(db, factoids.global_primary, channel)
        factoids.global_secondary  = resolve_alias(db, factoids.global_secondary, channel)
        factoids.channel_primary   = resolve_alias(db, factoids.channel_primary, channel)
        factoids.channel_secondary = resolve_alias(db, factoids.channel_secondary, channel)
    if info:
        # Get aliases for factoids
        factoids.global_primary    = factoid_info(db, factoids.global_primary, channel)
        factoids.global_secondary  = factoid_info(db, factoids.global_secondary, channel)
        factoids.channel_primary   = factoid_info(db, factoids.channel_primary, channel)
        factoids.channel_secondary = factoid_info(db, factoids.channel_secondary, channel)
    return factoids

def searchfactoid(db, factoid):
    keys = factoid.split()[:5]
    cur = db.cursor()
    ret = {}
    for k in keys:
        k = k.replace("'","\'")
        cur.execute("SELECT name FROM facts WHERE name LIKE '%%%s%%' OR VAlUE LIKE '%%%s%%'" % (k, k))
        res = cur.fetchall()
        for r in res:
            r = r[0]
            try:
                ret[r] += 1
            except:
                ret[r] = 1
    return 'Found: %s' % ','.join(sorted(ret.keys(), lambda x, y: cmp(ret[x], ret[y]))[:10])

def factoid_info(db,factoid,channel):
    if factoid:
        if not factoid.value.startswith('<alias>'):
            # Try and find aliases
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

def resolve_alias(db,factoid,channel,loop=0):
    if loop >= 10:
        return Factoid('','Error: infinite <alias> loop detected','','',0)
    if factoid and factoid.value.lower().startswith('<alias>'):
        new_factoids = get_factoids(db,factoid.value[7:].lower().strip(), channel, False)
        for x in ['channel_primary', 'global_primary']:
            if getattr(new_factoids, x):
                return resolve_alias(db, getattr(new_factoids, x), channel)
        return Factoid('','Error: unresolvable <alias>','','',0)
        #return None
    else:
        return factoid

def capab(prefix, capability):
    try:
        _ = ircdb.users.getUser(prefix)
        if ircdb.checkCapability(prefix, capability):
            return True
    except:
        pass
    return False
def log(msg):
    fd = open('/home/dennis/editlog','a')
    fd.write('%s\n' % msg)
    fd.close()
Class = Encyclopedia

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

fallback = ('ubuntu', '#ubuntu')
datadir = '/home/dennis/ubugtu/data/facts'
aptdir = '/home/dennis/ubugtu/data/apt'
relaychannel = '#ubuntu-ops'
# Keep 'distros' in search order!
distros = ('dapper','breezy','edgy','hoary','warty','dapper-seveas','breezy-seveas','dapper-buntudot')
defaultdistro = 'dapper'

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
        if text.startswith('info '):
            irc.reply(pkginfo(text[5:].strip()))
            return
        if text.startswith('find '):
            irc.reply(findpkg(text[5:].strip()))
            return
        if text.startswith('seen '):
            self.seens[text[5:].strip()] = (target, time.time())
            queue(irc, 'seenserv', "seen %s" % text[5:].strip())
            return

        # Factoid manipulation
        db = self.registryValue('database',channel)
        if not db:
            db,channel = fallback
        if channel not in self.databases:
            self.databases[channel] = sqlite.connect(os.path.join(datadir, '%s.db' % db))
            self.databases[channel].name = db
        db = self.databases[channel]
        
        if text.lower().startswith('search '):
            irc.reply(searchfactoid(text[7:].strip().lower()))
            return
        do_new = False
        if text.lower().startswith('forget '):
            if ' is ' in text.lower() or text.lower().endswith(' is'):
                return # Bad hack attempt :)
            text = '%s =~ s/^/<deleted>/' % text[7:]
        if ' is<sed>' in text:
            text = text.replace('is<sed>','=~',1)
        elif ' is <sed>' in text:
            text = text.replace('is <sed>','=~',1)
        if ' is ' in text and '=~' not in text:
            do_new = True
            if text.lower().startswith('no '):
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
            if not capab(msg.prefix, 'editfactoids'):
                irc.queueMsg(ircmsgs.privmsg(relaychannel, "In %s, %s said: %s" % (msg.args[0], msg.nick, msg.args[1])))
                irc.reply("Your edit request has been forwarded to #ubuntu-ops. Thank you for your attention to detail",private=True)
                lfd = open('/home/dennis/public_html/botlogs/lock','a')
                fcntl.lockf(lfd, fcntl.LOCK_EX)
                fd = open('/home/dennis/public_html/botlogs/%s.log' % datetime.date.today().strftime('%Y-%m-%d'),'a')
                fd.write("%s  %-20s %-16s  %s\n" % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), channel, msg.nick, msg.args[1]))
                fd.close()
                fcntl.lockf(lfd,fcntl.LOCK_UN)
                lfd.close()
                os.chmod('/home/dennis/public_html/botlogs/%s.log' % datetime.date.today().strftime('%Y-%m-%d'),0644)
                return
            # All clear!
            # Find factoid
            p = text.find('=~')
            name, value = text[:p].strip(), text[p+2:].strip()
            name = name.lower()
            if value.startswith('also '):
                name += '-also'
                value = value[5:].strip()
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
                aliases = get_factoids(db, alias, newchannel, resolve=True)
                if aliases.global_primary:
                    f.value = '<alias> ' + aliases.global_primary.name
                elif aliases.channel_primary:
                    f.name += '-%s' % newchannel
                    f.value = '<alias> ' + aliases.channel_primary.name
                else:
                    irc.error("Unresolvable alias:")
                    return
            # Finally, save
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
            if text.startswith('tell ') and ' about ' in text:
                _target = text[5:].strip().split(None,1)[0]
                text = text[text.find(' about ')+7:].strip()
            if _target:
            # Validate
                for chan in irc.state.channels:
                    if _target in irc.state.channels[chan].users and msg.nick in irc.state.channels[chan].users:
                        target = _target   
                        retmsg = '%s wants you to know: ' % msg.nick
                        break
                else:
                    irc.error("That person could not be found in any channel you're in")
                    return
            factoids = get_factoids(db, text, channel, resolve = not display_info, info = display_info)
            replied = False
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
                        queue(irc, target, '%s%s' % (retmsg, factoid.value[7:].strip()))
                    else:
                        #irc.queueMsg(ircmsgs.privmsg(target, '%s%s is %s' % (retmsg, factoid.name, factoid.value.strip())))
                        queue(irc, target, '%s%s is %s' % (retmsg, factoid.name, factoid.value.strip()))
                    if not display_info:
                        break
            else:
                if not replied:
                    i = pkginfo(text)
                    if not i.startswith('Package'):
                        queue(irc, target, i)
                    else:
                        irc.reply("Sorry, I don't know anything about %s - try searching on http://bots.ubuntulinux.nl/factoids.cgi" % text)
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
        if text[0] == '!':
            text = text[1:]
            if text.lower().startswith('ubotu'):
                t2 = text[5:].strip()
                if t2 and t2.find('>') != 0:
                    text = text[5:].strip()
            return text
        if text.lower().startswith('ubotu'): # FIXME: use nickname variable
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
def findpkg(pkg,filelookup=True):
    _pkg = ''.join([x for x in pkg.strip().split(None,1)[0] if x.isalnum or x in '.-'])
    distro = defaultdistro
    if len(pkg.strip().split()) > 1:
        distro = ''.join([x for x in pkg.strip().split(None,2)[1] if x.isalnum or x in '.-'])
    if distro not in distros:
        distro = defaultdistro
    pkg = _pkg

    data = commands.getoutput(aptcommand % (distro, distro, distro, 'search -n', pkg))
    if not data:
        if filelookup:
            print aptfilecommand % (distro, distro, pkg)
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

def pkginfo(pkg):
    _pkg = ''.join([x for x in pkg.strip().split(None,1)[0] if x.isalnum() or x in '.-'])
    distro = defaultdistro
    if len(pkg.strip().split()) > 1:
        distro = ''.join([x for x in pkg.strip().split(None,2)[1] if x.isalnum() or x in '-.'])
    if distro not in distros:
        distro = defaultdistro
    pkg = _pkg

    data = commands.getoutput(aptcommand % (distro, distro, distro, 'show', pkg))
    data2 = commands.getoutput(aptcommand % (distro, distro, distro, 'showsrc', pkg))
    if not data or 'E: No packages found' in data:
        return 'Package %s does not exist in %s' % (pkg, distro)
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
    print resolve
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

####################################
##
##    # Capability check
##    def _precheck(self, irc, msg, capability=None, timeout=None, withnick=False):
##        channel = msg.args[0].lower()
##        inchannel = channel.startswith('#')
##        excl = msg.args[1].startswith('!')
##        wn = msg.args[1].startswith('ubotu')
##        if inchannel and not (excl or (withnick and wn)):
##            return False
##        if msg.args[1].strip()[0] == '%': # FIXME: replywhenaddressed.chars oslt
##            return False
##        for c in irc.callbacks:
##            comm = msg.args[1].split()[0]
##            if c.isCommandMethod(comm) and not c.isDisabled(comm):
##                return False
##        if capability:
##            try:
##                _ = ircdb.users.getUser(msg.prefix)
##                if not ircdb.checkCapability(msg.prefix, capability):
##                    raise KeyError, "Bogus error to trigger the log"
##            except KeyError:
##                irc.queueMsg(ircmsgs.privmsg('#ubuntu-ops', "In %s, %s said: %s" % (msg.args[0], msg.nick, msg.args[1])))
##                irc.reply("Your edit request has been forwarded to #ubuntu-ops. Thank you for your attention to detail",private=True)
##                lfd = open('/home/dennis/public_html/botlogs/lock','a')
##                fcntl.lockf(lfd, fcntl.LOCK_EX)
##                fd = open('/home/dennis/public_html/botlogs/%s.log' % datetime.date.today().strftime('%Y-%m-%d'),'a')
##                fd.write("%s  %-20s %-16s  %s\n" % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),msg.args[0], msg.nick, msg.args[1]))
##                fd.close()
##                fcntl.lockf(lfd,fcntl.LOCK_UN)
##                lfd.close()
##                os.chmod('/home/dennis/public_html/botlogs/%s.log' % datetime.date.today().strftime('%Y-%m-%d'),0644)
##                return False
##        if timeout:
##            for key in self.times.keys():
##                if self.times[key] < time.time() - 15:
##                    self.times.pop(key)
##            if timeout in self.times:
##                return False
##            self.times[timeout] = time.time()
##        db = self.registryValue('database',channel)
##        if not db:
##            db,channel = fallback
##        if channel not in self.databases:
##            self.databases[channel] = sqlite.connect(os.path.join(datadir, '%s.db' % db))
##            self.databases[channel].name = db
##        return self.databases[channel]
##
##    def searchfactoid(self, irc, msg, match):
##        r"^!?search\s+(?P<query>.+)"
##        db = self._precheck(irc, msg, timeout=(msg.args[0],match.group('query')))
##        if not db: return
##        cur = db.cursor()
##        query = '%%%s%%' % match.group('query').replace('%','').replace('*','%')
##        try:
##            cur.execute("SELECT name FROM facts WHERE (value LIKE %s OR name LIKE %s ) AND value NOT LIKE '<alias>%%'", (query, query))
##            data = cur.fetchall()
##            all = [x[0] for x in data]
##            cur.execute("SELECT value FROM facts WHERE name LIKE %s AND value LIKE '<alias>%%'", query)
##            data = cur.fetchall()
##            all += [x[0][7:].strip() for x in data]
##            all = list(set(all))
##
##            if len(all) > 10:
##                irc.reply("Found: %s (and %d more)" % (', '.join(all[:10]), len(all)-10))
##            elif len(all):
##                irc.reply("Found: %s" % ', '.join(all))
##            else:
##                irc.reply("Found nothing")
##        except:
##            irc.error('An error occured (code 561)')
##
##    def showfactoid(self, irc, msg, match):
##        r"^(!?ubotu\S?\s+|!)?(?P<noalias>-)?\s*(tell\s+(?P<nick>\S+)\s+about\s+)?(?P<factoid>\S.*?)(>\s*(?P<nick2>\S+).*)?$"
##        withnick = bool(match.group(1)) and msg.args[1].startswith('ubotu')
##        db = self._precheck(irc, msg, withnick=True, timeout=(msg.args[0], match.group('nick'), match.group('factoid'), match.group('nick2')))
##        if not db: return
##        to = channel = msg.args[0]
##        if channel[0] != '#':
##            to = msg.nick
##        cur = db.cursor()
##        retmsg = ''
##        
##        noalias = match.group('noalias')
##        factoid = match.group('factoid').lower().strip()
##        if ' is ' in match.group(0) or \
##           '=~' in match.group(0) or \
##           '<sed>' in match.group(0) or \
##           factoid.startswith('forget ') or \
##           factoid.startswith('info ') or \
##           factoid.startswith('find ') or \
##           factoid.startswith('search ') or \
##           factoid.startswith('seen'):
##            return
##
##        #if channel.startswith('#'):
##        if True:
##            nick = match.group('nick')
##            if match.group('nick2'): nick = match.group('nick2')
##            if nick == 'me': nick = msg.nick
##            if nick:
##               if nick.lower() == 'ubotu':
##                   irc.error("You lose.")
##                   return
##               for chan in irc.state.channels:
##                    if nick in irc.state.channels[chan].users and\
##                       msg.nick in irc.state.channels[chan].users:
##                        retmsg = '%s wants you to know: ' % msg.nick
##                        to = nick
##                        break
##               else:
##                   irc.error("That person could not be found in any channel you're in")
##                   return
##
##        # Retrieve factoid
##        try:
##            factoid = get_factoid(db, factoid, channel)
##            if not factoid:
##                irc.reply('I know nothing about %s - try searching http://bots.ubuntulinux.nl/factoids.cgi?db=%s' % (match.group('factoid'),db.name))
##                return
##            # Output factoid
##            if noalias:
##                if not self._precheck(irc, msg, timeout=(to,factoid.name,1),withnick=True):
##                    return
##                cur.execute("SELECT name FROM facts WHERE value = %s", '<alias> ' + factoid.name)
##                data = cur.fetchall()
##                if(len(data)):
##                    #irc.queueMsg(ircmsgs.privmsg(to, "%s aliases: %s" % (factoid.name, ', '.join([x[0].strip() for x in data]))))
##                    aliases = "%s aliases: %s" % (factoid.name, ', '.join([x[0].strip() for x in data]))
##                else:
##                    if factoid.value.strip().startswith('<alias>'):
##                        aliases = "%s is %s" % (factoid.name, factoid.value.strip())
##                    else:
##                        aliases = "%s has no aliases" % factoid.name
##                authorinfo = "Added by %s on %s" % (factoid.author[:factoid.author.find('!')], factoid.added[:factoid.added.find('.')])
##                irc.queueMsg(ircmsgs.privmsg(to,"%s - %s" % (aliases, authorinfo)))
##            else:
##                factoid = resolve_alias(db,factoid,channel)
##                # Do timing
##                if not self._precheck(irc, msg, timeout=(to,factoid.name,2),withnick=True):
##                    return
##                cur.execute("UPDATE FACTS SET popularity = %d WHERE name = %s", factoid.popularity+1, factoid.name)
##                db.commit()
##                if factoid.value.startswith('<reply>'):
##                    irc.queueMsg(ircmsgs.privmsg(to, '%s%s' % (retmsg, factoid.value[7:].strip())))
##                else:
##                    irc.queueMsg(ircmsgs.privmsg(to, '%s%s is %s' % (retmsg, factoid.name, factoid.value.strip())))
##            # Now look for the -also factoid, but don't error on it
##            factoid = get_factoid(db, factoid.name + '-also', channel)
##            if not factoid:
##                return
##            if noalias:
##                if not self._precheck(irc, msg, timeout=(to,factoid.name,1)):
##                    return
##                cur.execute("SELECT name FROM facts WHERE value = %s", '<alias> ' + factoid.name)
##                data = cur.fetchall()
##                if(len(data)):
##                    aliases = "%s aliases: %s" % (factoid.name, ', '.join([x[0].strip() for x in data]))
##                else:
##                    if factoid.value.strip().startswith('<alias>'):
##                        aliases = "%s is %s" % (factoid.name, factoid.value.strip())
##                    else:
##                        aliases = "%s has no aliases" % factoid.name
##                authorinfo = "Added by %s on %s" % (factoid.author[:factoid.author.find('!')], factoid.added[:factoid.added.find('.')])
##                irc.queueMsg(ircmsgs.privmsg(to,"%s - %s" % (aliases, authorinfo)))
##            else:
##                factoid = resolve_alias(db,factoid,channel)
##                # Do timing
##                if not self._precheck(irc, msg, timeout=(to,factoid.name)):
##                    return
##                cur.execute("UPDATE FACTS SET popularity = %d WHERE name = %s", factoid.popularity+1, factoid.name)
##                db.commit()
##                irc.queueMsg(ircmsgs.privmsg(to, '%s%s' % (retmsg, factoid.value.strip())))
##        except:
##            raise
##            irc.error('An error occured (code 813)')
##
##    def addfactoid(self, irc, msg, match):
##        r"^!?(?P<no>no,?\s+)?(?P<factoid>\S.*?)\s+is\s+(?P<also>also\s+)?(?P<fact>\S.*)"
##        factoid = match.group('factoid').lower().strip()
##        fact = match.group('fact').strip()
##        if '<sed>' in match.group(0) or \
##           '=~' in match.group(0) or \
##           factoid.startswith('forget') or \
##           factoid.startswith('info') or \
##           factoid.startswith('find') or \
##           factoid.startswith('search'):
##            return
##        db = self._precheck(irc, msg, capability='editfactoids', timeout=(msg.args[0],match.group(0)))
##        if not db: return
##        channel = msg.args[0]
##        cur = db.cursor()
##
##        if match.group('also'):
##            factoid = get_factoid(db, match.group('factoid'), channel)
##            if not factoid:
##                irc.reply('I know nothing about %s yet' % match.group('factoid'))
##                return
##            factoid = factoid.name + '-also'
##
##        try:
##            # See if the alias exists and resolve it...
##            old_factoid = get_factoid(db, factoid, channel)
##            if old_factoid:
##                if not fact.startswith('<alias>'):
##                    old_factoid = resolve_alias(db, old_factoid, channel)
##                # Unresolvable alias
##                if not old_factoid.name:
##                    irc.reply(old_factoid.value)
##                    return
##                if match.group('no'):
##                    if fact.startswith('<alias>'):
##                        cur.execute("SELECT COUNT(*) FROM facts WHERE value = %s", '<alias> ' + factoid)
##                        num = cur.fetchall()[0][0]
##                        if num:
##                            irc.reply("Can't turn factoid with aliases into an alias")
##                            return
##                        alias_factoid = get_factoid(db, fact[7:].lower().strip(), channel)
##                        if not alias_factoid:
##                            alias_factoid =  Factoid('','Error: unresolvable <alias>','','',0)
##                        else:
##                            alias_factoid = resolve_alias(db, alias_factoid, channel)
##                        if not alias_factoid.name:
##                            irc.reply(alias_factoid.value)
##                            return
##                        fact = '<alias> %s' % alias_factoid.name
##                        fact = fact.lower()
##                    cur.execute("""UPDATE facts SET value=%s, author=%s, added=%s WHERE name=%s""", 
##                                (fact, msg.prefix, str(datetime.datetime.now()), old_factoid.name))
##                    db.commit()
##                    irc.reply("I'll remember that")
##                else:
##                    irc.reply('%s is already known...' % factoid)
##            else:
##                if fact.lower().startswith('<alias>'):
##                    old_factoid = get_factoid(db, fact[7:].lower().strip(), channel)
##                    if not old_factoid:
##                        old_factoid =  Factoid('','Error: unresolvable <alias>','','',0)
##                    else:
##                        old_factoid = resolve_alias(db, old_factoid, channel)
##                    if not old_factoid.name:
##                        irc.reply(old_factoid.value)
##                        return
##                    fact = '<alias> %s' % old_factoid.name
##                    fact = fact.lower()
##                cur.execute("""INSERT INTO facts (name, value, author, added) VALUES
##                            (%s, %s, %s, %s)""", (factoid, fact, msg.prefix, str(datetime.datetime.now())))
##                db.commit()
##                irc.reply("I'll remember that")
##        except:
##            irc.error('An error occured (code 735)')
##            
##    def editfactoid(self, irc, msg, match):
##        r"^!?(?P<factoid>.*?)\s*(=~|(\s+is\s*)<sed>)\s*s?(?P<regex>.*)"
##        db = self._precheck(irc, msg, capability='editfactoids', timeout=(msg.args[0],match.group(0)))
##        if not db: return
##        channel = msg.args[0]
##        cur = db.cursor()
##
##        factoid = match.group('factoid').lower().strip()
##        regex = match.group('regex').strip()
##        if factoid.startswith('forget') or \
##           factoid.startswith('info') or \
##           factoid.startswith('find') or \
##           factoid.startswith('search'): return
##        # Store factoid if nonexistant or 'no' is given
##        try:
##            # See if the alias exists and resolve it...
##            factoid = get_factoid(db, factoid, channel)
##            if factoid:
##                factoid = resolve_alias(db, factoid, channel)
##                # Unresolvable alias
##                if not factoid.name:
##                    irc.reply(old_factoid.value)
##                    return
##                delim = regex[0]
##                if regex[-1] != delim:
##                    irc.reply("Missing end delimiter")
##                    return
##                data = regex.split(delim)[1:-1]
##                if len(data) != 2:
##                    irc.reply("You used the delimiter too often. Maybe try another one?")
##                    return
##                regex, change = data
##                if '<alias>' in change.lower():
##                    irc.reply("Can't turn factoids into aliases this way")
##                    return
##                try:
##                    regex = re.compile(regex)
##                except:
##                    irc.reply("Malformed regex")
##                    return
##                newval = regex.sub(change, factoid.value, 1)
##                if newval != factoid.value:
##                    cur.execute("""UPDATE facts SET value=%s, author=%s, added=%s WHERE name=%s""", 
##                                (newval, msg.prefix, str(datetime.datetime.now()), factoid.name))
##                    db.commit()
##                    irc.reply("I'll remember that")
##                else:
##                    irc.reply("No changes, not saving")
##            else:
##                irc.reply('I know nothing about %s' % match.group('factoid'))
##        except:
##            irc.error('An error occured (code 735)')
##            
##    def deletefactoid(self, irc, msg, match):
##        r"^!?forget\s+(?P<factoid>\S.*)"
##        db = self._precheck(irc, msg, capability='editfactoids', timeout=(msg.args[0],match.group('factoid')))
##        if not db: return
##        channel = msg.args[0]
##        cur = db.cursor()
##        try:
##            cur.execute("SELECT COUNT(*) FROM facts WHERE value = %s", '<alias> ' + match.group('factoid'))
##            num = cur.fetchall()[0][0]
##            if num:
##                irc.reply("Can't forget factoids with aliases")
##            else:
##                cur.execute("DELETE FROM facts WHERE name = %s", match.group('factoid'))
##                cur.execute("DELETE FROM facts WHERE name = %s", match.group('factoid') + '-also')
##                db.commit()
##                irc.reply("I've forgotten it")
##        except:
##            raise
##            irc.error('An error occured (code 124)')
##        
Class = Encyclopedia

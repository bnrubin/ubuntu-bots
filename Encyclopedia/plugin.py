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
import re
import os
import fcntl
apt_pkg.init()

fallback = ('ubuntu', '#ubuntu')
datadir = '/home/dennis/ubugtu/data/facts'

def r(repo,section):
    if 'seveas' in repo:
        return 'Seveas'
    if '/' in section:
        return section[:section.find('/')]
    return 'main'

class Factoid:
    def __init__(self, name, value, author, added, popularity):
        self.name = name;     self.value = value
        self.author = author; self.added = added
        self.popularity = popularity

def get_factoid(db, name, channel):
    cur = db.cursor()
    cur.execute("SELECT name, value, author, added, popularity FROM facts WHERE name = %s", '%s-%s' % (name, channel))
    factoid = cur.fetchall()
    if len(factoid):
        f = factoid[0]
        return Factoid(f[0].replace(channel,'')[:-1],f[1],f[2],f[3],f[4])
    cur.execute("SELECT name, value, author, added, popularity FROM facts WHERE name = %s", name)
    factoid = cur.fetchall()
    if len(factoid):
        f = factoid[0]
        return Factoid(f[0],f[1].replace('$chan',channel),f[2],f[3],f[4])
    return None

def resolve_alias(db,factoid,channel,loop=0):
    if loop >= 10:
        return Factoid('','Error: infinite <alias> loop detected','','',0)
    if factoid.value.lower().startswith('<alias>'):
        new_factoid = get_factoid(db,factoid.value[7:].lower().strip(),channel)
        if not new_factoid:
            return Factoid('','Error: unresolvable <alias>','','',0)
        else:
            return resolve_alias(db, new_factoid, channel, loop+1)
    else:
        return factoid

class Encyclopedia(callbacks.PluginRegexp):
    """!factoid: show factoid"""
    threaded = True
    regexps = ['showfactoid', 'addfactoid', 'deletefactoid','info','find','editfactoid','searchfactoid','seen']

    def __init__(self, irc):
        callbacks.PluginRegexp.__init__(self, irc)
        self.databases = {}
        self.times = {}
        self.seens = {}

    # Capability check
    def _precheck(self, irc, msg, capability=None, timeout=None, withnick=False):
        channel = msg.args[0].lower()
        inchannel = channel.startswith('#')
        excl = msg.args[1].startswith('!')
        wn = msg.args[1].startswith('ubotu')
        if inchannel and not (excl or (withnick and wn)):
            return False
        for c in irc.callbacks:
            comm = msg.args[1].split()[0]
            if c.isCommandMethod(comm) and not c.isDisabled(comm):
                return False
        if capability:
            try:
                _ = ircdb.users.getUser(msg.prefix)
                if not ircdb.checkCapability(msg.prefix, capability):
                    raise KeyError, "Bogus error to trigger the log"
            except KeyError:
                irc.queueMsg(ircmsgs.privmsg('#ubuntu-ops', "In %s, %s said: %s" % (msg.args[0], msg.nick, msg.args[1])))
                irc.reply("Your edit request has been forwarded to #ubuntu-ops. Thank you for your attention to detail",private=True)
                lfd = open('/home/dennis/public_html/botlogs/lock','a')
                fcntl.lockf(lfd, fcntl.LOCK_EX)
                fd = open('/home/dennis/public_html/botlogs/%s.log' % datetime.date.today().strftime('%Y-%m-%d'),'a')
                fd.write("%s  %-20s %-16s  %s\n" % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),msg.args[0], msg.nick, msg.args[1]))
                fd.close()
                fcntl.lockf(lfd,fcntl.LOCK_UN)
                lfd.close()
                os.chmod('/home/dennis/public_html/botlogs/%s.log' % datetime.date.today().strftime('%Y-%m-%d'),0644)
                return False
        if timeout:
            for key in self.times.keys():
                if self.times[key] < time.time() - 15:
                    self.times.pop(key)
            if timeout in self.times:
                return False
            self.times[timeout] = time.time()
        db = self.registryValue('database',channel)
        if not db:
            db,channel = fallback
        if channel not in self.databases:
            self.databases[channel] = sqlite.connect(os.path.join(datadir, '%s.db' % db))
        return self.databases[channel]

    def searchfactoid(self, irc, msg, match):
        r"^!?search\s+(?P<query>.+)"
        db = self._precheck(irc, msg, timeout=(msg.args[0],match.group('query')))
        if not db: return
        cur = db.cursor()
        query = '%%%s%%' % match.group('query').replace('%','').replace('*','%')
        try:
            cur.execute("SELECT name FROM facts WHERE (value LIKE %s OR name LIKE %s ) AND value NOT LIKE '<alias>%%'", (query, query))
            data = cur.fetchall()
            all = [x[0] for x in data]
            cur.execute("SELECT value FROM facts WHERE name LIKE %s AND value LIKE '<alias>%%'", query)
            data = cur.fetchall()
            all += [x[0][7:].strip() for x in data]
            all = list(set(all))

            if len(all) > 10:
                irc.reply("Found: %s (and %d more)" % (', '.join(all[:10]), len(all)-10))
            elif len(all):
                irc.reply("Found: %s" % ', '.join(all))
            else:
                irc.reply("Found nothing")
        except:
            irc.error('An error occured (code 561)')

    def showfactoid(self, irc, msg, match):
        r"^(!?ubotu\S?\s+|!)?(?P<noalias>-)?\s*(tell\s+(?P<nick>\S+)\s+about\s+)?(?P<factoid>\S.*?)(>\s*(?P<nick2>\S+).*)?$"
        withnick = bool(match.group(1)) and msg.args[1].startswith('ubotu')
        db = self._precheck(irc, msg, withnick=True, timeout=(msg.args[0], match.group('nick'), match.group('factoid'), match.group('nick2')))
        if not db: return
        to = channel = msg.args[0]
        if channel[0] != '#':
            to = msg.nick
        cur = db.cursor()
        retmsg = ''
        
        noalias = match.group('noalias')
        factoid = match.group('factoid').lower().strip()
        if ' is ' in match.group(0) or \
           '=~' in match.group(0) or \
           '<sed>' in match.group(0) or \
           factoid.startswith('forget ') or \
           factoid.startswith('info ') or \
           factoid.startswith('find ') or \
           factoid.startswith('search ') or \
           factoid.startswith('seen'):
            return

        #if channel.startswith('#'):
        if True:
            nick = match.group('nick')
            if match.group('nick2'): nick = match.group('nick2')
            if nick == 'me': nick = msg.nick
            if nick:
               for chan in irc.state.channels:
                    if nick in irc.state.channels[chan].users and\
                       msg.nick in irc.state.channels[chan].users:
                        retmsg = '%s wants you to know: ' % msg.nick
                        to = nick
                        break
               else:
                   irc.error("That person could not be found in any channel you're in")
                   return

        # Retrieve factoid
        try:
            factoid = get_factoid(db, factoid, channel)
            if not factoid:
                irc.reply('I know nothing about %s - try searching bots.ubuntulinux.nl, help.ubuntu.com and wiki.ubuntu.com' % match.group('factoid'))
                return
            # Output factoid
            if noalias:
                if not self._precheck(irc, msg, timeout=(to,factoid.name,1),withnick=True):
                    return
                cur.execute("SELECT name FROM facts WHERE value = %s", '<alias> ' + factoid.name)
                data = cur.fetchall()
                if(len(data)):
                    #irc.queueMsg(ircmsgs.privmsg(to, "%s aliases: %s" % (factoid.name, ', '.join([x[0].strip() for x in data]))))
                    aliases = "%s aliases: %s" % (factoid.name, ', '.join([x[0].strip() for x in data]))
                else:
                    if factoid.value.strip().startswith('<alias>'):
                        aliases = "%s is %s" % (factoid.name, factoid.value.strip())
                    else:
                        aliases = "%s has no aliases" % factoid.name
                authorinfo = "Added by %s on %s" % (factoid.author[:factoid.author.find('!')], factoid.added[:factoid.added.find('.')])
                irc.queueMsg(ircmsgs.privmsg(to,"%s - %s" % (aliases, authorinfo)))
            else:
                factoid = resolve_alias(db,factoid,channel)
                # Do timing
                if not self._precheck(irc, msg, timeout=(to,factoid.name,2),withnick=True):
                    return
                cur.execute("UPDATE FACTS SET popularity = %d WHERE name = %s", factoid.popularity+1, factoid.name)
                db.commit()
                if factoid.value.startswith('<reply>'):
                    irc.queueMsg(ircmsgs.privmsg(to, '%s%s' % (retmsg, factoid.value[7:].strip())))
                else:
                    irc.queueMsg(ircmsgs.privmsg(to, '%s%s is %s' % (retmsg, factoid.name, factoid.value.strip())))
            # Now look for the -also factoid, but don't error on it
            factoid = get_factoid(db, factoid.name + '-also', channel)
            if not factoid:
                return
            if noalias:
                if not self._precheck(irc, msg, timeout=(to,factoid.name,1)):
                    return
                cur.execute("SELECT name FROM facts WHERE value = %s", '<alias> ' + factoid.name)
                data = cur.fetchall()
                if(len(data)):
                    aliases = "%s aliases: %s" % (factoid.name, ', '.join([x[0].strip() for x in data]))
                else:
                    if factoid.value.strip().startswith('<alias>'):
                        aliases = "%s is %s" % (factoid.name, factoid.value.strip())
                    else:
                        aliases = "%s has no aliases" % factoid.name
                authorinfo = "Added by %s on %s" % (factoid.author[:factoid.author.find('!')], factoid.added[:factoid.added.find('.')])
                irc.queueMsg(ircmsgs.privmsg(to,"%s - %s" % (aliases, authorinfo)))
            else:
                factoid = resolve_alias(db,factoid,channel)
                # Do timing
                if not self._precheck(irc, msg, timeout=(to,factoid.name)):
                    return
                cur.execute("UPDATE FACTS SET popularity = %d WHERE name = %s", factoid.popularity+1, factoid.name)
                db.commit()
                irc.queueMsg(ircmsgs.privmsg(to, '%s%s' % (retmsg, factoid.value.strip())))
        except:
            raise
            irc.error('An error occured (code 813)')

    def addfactoid(self, irc, msg, match):
        r"^!?(?P<no>no,?\s+)?(?P<factoid>\S.*?)\s+is\s+(?P<also>also\s+)?(?P<fact>\S.*)"
        db = self._precheck(irc, msg, capability='editfactoids', timeout=(msg.args[0],match.group(0)))
        if not db: return
        channel = msg.args[0]
        cur = db.cursor()

        factoid = match.group('factoid').lower().strip()
        fact = match.group('fact').strip()
        if '<sed>' in match.group(0) or \
           '=~' in match.group(0) or \
           factoid.startswith('forget') or \
           factoid.startswith('info') or \
           factoid.startswith('find') or \
           factoid.startswith('search'):
            return
        if match.group('also'):
            factoid = get_factoid(db, match.group('factoid'), channel)
            if not factoid:
                irc.reply('I know nothing about %s yet' % match.group('factoid'))
                return
            factoid = factoid.name + '-also'

        try:
            # See if the alias exists and resolve it...
            old_factoid = get_factoid(db, factoid, channel)
            if old_factoid:
                if not fact.startswith('<alias>'):
                    old_factoid = resolve_alias(db, old_factoid, channel)
                # Unresolvable alias
                if not old_factoid.name:
                    irc.reply(old_factoid.value)
                    return
                if match.group('no'):
                    if fact.startswith('<alias>'):
                        cur.execute("SELECT COUNT(*) FROM facts WHERE value = %s", '<alias> ' + factoid)
                        num = cur.fetchall()[0][0]
                        if num:
                            irc.reply("Can't turn factoid with aliases into an alias")
                            return
                        alias_factoid = get_factoid(db, fact[7:].lower().strip(), channel)
                        if not alias_factoid:
                            alias_factoid =  Factoid('','Error: unresolvable <alias>','','',0)
                        else:
                            alias_factoid = resolve_alias(db, alias_factoid, channel)
                        if not alias_factoid.name:
                            irc.reply(alias_factoid.value)
                            return
                        fact = '<alias> %s' % alias_factoid.name
                        fact = fact.lower()
                    cur.execute("""UPDATE facts SET value=%s, author=%s, added=%s WHERE name=%s""", 
                                (fact, msg.prefix, str(datetime.datetime.now()), old_factoid.name))
                    db.commit()
                    irc.reply("I'll remember that")
                else:
                    irc.reply('%s is already known...' % factoid)
            else:
                if fact.lower().startswith('<alias>'):
                    old_factoid = get_factoid(db, fact[7:].lower().strip(), channel)
                    if not old_factoid:
                        old_factoid =  Factoid('','Error: unresolvable <alias>','','',0)
                    else:
                        old_factoid = resolve_alias(db, old_factoid, channel)
                    if not old_factoid.name:
                        irc.reply(old_factoid.value)
                        return
                    fact = '<alias> %s' % old_factoid.name
                    fact = fact.lower()
                cur.execute("""INSERT INTO facts (name, value, author, added) VALUES
                            (%s, %s, %s, %s)""", (factoid, fact, msg.prefix, str(datetime.datetime.now())))
                db.commit()
                irc.reply("I'll remember that")
        except:
            irc.error('An error occured (code 735)')
            
    def editfactoid(self, irc, msg, match):
        r"^!?(?P<factoid>.*?)\s*(=~|(\s+is\s*)<sed>)\s*s?(?P<regex>.*)"
        db = self._precheck(irc, msg, capability='editfactoids', timeout=(msg.args[0],match.group(0)))
        if not db: return
        channel = msg.args[0]
        cur = db.cursor()

        factoid = match.group('factoid').lower().strip()
        regex = match.group('regex').strip()
        if factoid.startswith('forget') or \
           factoid.startswith('info') or \
           factoid.startswith('find') or \
           factoid.startswith('search'): return
        # Store factoid if nonexistant or 'no' is given
        try:
            # See if the alias exists and resolve it...
            factoid = get_factoid(db, factoid, channel)
            if factoid:
                factoid = resolve_alias(db, factoid, channel)
                # Unresolvable alias
                if not factoid.name:
                    irc.reply(old_factoid.value)
                    return
                delim = regex[0]
                if regex[-1] != delim:
                    irc.reply("Missing end delimiter")
                    return
                data = regex.split(delim)[1:-1]
                if len(data) != 2:
                    irc.reply("You used the delimiter too often. Maybe try another one?")
                    return
                regex, change = data
                if '<alias>' in change.lower():
                    irc.reply("Can't turn factoids into aliases this way")
                    return
                try:
                    regex = re.compile(regex)
                except:
                    irc.reply("Malformed regex")
                    return
                newval = regex.sub(change, factoid.value, 1)
                if newval != factoid.value:
                    cur.execute("""UPDATE facts SET value=%s, author=%s, added=%s WHERE name=%s""", 
                                (newval, msg.prefix, str(datetime.datetime.now()), factoid.name))
                    db.commit()
                    irc.reply("I'll remember that")
                else:
                    irc.reply("No changes, not saving")
            else:
                irc.reply('I know nothing about %s' % match.group('factoid'))
        except:
            irc.error('An error occured (code 735)')
            
    def deletefactoid(self, irc, msg, match):
        r"^!?forget\s+(?P<factoid>\S.*)"
        db = self._precheck(irc, msg, capability='editfactoids', timeout=(msg.args[0],match.group('factoid')))
        if not db: return
        channel = msg.args[0]
        cur = db.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM facts WHERE value = %s", '<alias> ' + match.group('factoid'))
            num = cur.fetchall()[0][0]
            if num:
                irc.reply("Can't forget factoids with aliases")
            else:
                cur.execute("DELETE FROM facts WHERE name = %s", match.group('factoid'))
                cur.execute("DELETE FROM facts WHERE name = %s", match.group('factoid') + '-also')
                db.commit()
                irc.reply("I've forgotten it")
        except:
            raise
            irc.error('An error occured (code 124)')
        
    aptcommand = """apt-cache\\
                     -o"Dir::State::Lists=/home/dennis/ubugtu/data/apt/%s"\\
                     -o"Dir::etc::sourcelist=/home/dennis/ubugtu/data/apt/%s.list"\\
                     -o"Dir::State::status=/home/dennis/ubugtu/data/apt/%s.status"\\
                     -o"Dir::Cache=/home/dennis/ubugtu/data/apt/cache"\\
                     %s %s"""
    def info(self, irc, msg, match):
        r"^!?info\s+(?P<package>\S+)(\s+(?P<distro>\S+))?"
        if not self._precheck(irc, msg, timeout=(msg.args[0],match.group('package'), match.group('distro'))):
            return
        distro = 'dapper'
        if (match.group('distro') in ('warty','hoary','breezy','dapper','edgy','breezy-seveas','dapper-seveas')):
            distro = match.group('distro')
        data = commands.getoutput(self.aptcommand % (distro, distro, distro, 'show', match.group('package')))
        if not data or 'E: No packages found' in data:
            irc.reply('Package %s does not exist in %s' % (match.group('package'), distro))
        else:
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
            irc.reply("%s: %s. In repository %s, is %s. Version %s (%s), package size %s kB, installed size %s kB" %
                      (maxp['Package'], maxp['Description'].split('\n')[0], r(distro, maxp['Section']),
                       maxp['Priority'], maxp['Version'], distro, int(maxp['Size'])/1024, maxp['Installed-Size']))
                       
    def find(self, irc, msg, match):
        r"^!?find\s+(?P<package>\S+)(\s+(?P<distro>\S+))?"
        if not self._precheck(irc, msg, timeout=(msg.args[0],match.group('package'), match.group('distro'),2)):
            return
        distro = 'dapper'
        if (match.group('distro') in ('warty','hoary','breezy','dapper','edgy')):
            distro = match.group('distro')
        data = commands.getoutput(self.aptcommand % (distro, distro, distro, 'search -n', match.group('package')))
        if not data:
            irc.reply("No packages matching '%s' could be found" % match.group('package'))
        else:
            pkgs = [x.split()[0] for x in data.split('\n')]
            if len(pkgs) > 5:
                irc.reply("Found: %s (and %d others)" % (', '.join(pkgs[:5]), len(pkgs) -5))
            else:
                irc.reply("Found: %s" % ', '.join(pkgs[:5]))

    def seen(self, irc, msg, match):
        r"^!?seen\s+(?P<nick>\S+)"
        if not self._precheck(irc, msg, timeout=(msg.args[0],match.group('nick'))):
            return
        to = msg.args[0]
        if msg.args[0][0] != '#':
            to = msg.nick
        self.seens[match.group('nick')] = (to, time.time())
        irc.queueMsg(ircmsgs.privmsg('seenserv', "seen %s" % match.group('nick')))

    def doNotice(self, irc, msg):
        if msg.nick.lower() == 'seenserv':
            resp = msg.args[1]
            for n in self.seens.keys():
                if self.seens[n][1] < time.time() - 10:
                    self.seens.pop(n)
            for n in self.seens.keys():
                if n.lower() in resp.lower():
                    irc.queueMsg(ircmsgs.privmsg(self.seens[n][0], resp))
                    self.seens.pop(n)
    
    def addeditor(self, irc, msg, args, name):
        self._precheck(irc, msg, capability='addeditors')
        try:
            u = ircdb.users.getUser(name)
        except:
            irc.error('User %s is not registered' % name)
        else:
            u.addCapability('editfactoids')
    addeditor = wrap(addeditor, ['text'])

    def editors(self, irc, msg, args):
        irc.reply(', '.join([ircdb.users.getUser(u).name for u in ircdb.users.users \
                             if 'editfactoids' in ircdb.users.getUser(u).capabilities]))
    editors = wrap(editors)
    def moderators(self, irc, msg, args):
        irc.reply(', '.join([ircdb.users.getUser(u).name for u in ircdb.users.users \
                             if 'addeditors' in ircdb.users.getUser(u).capabilities]))
    moderators = wrap(moderators)
    
    def removeeditor(self, irc, msg, args, name):
        self._precheck(irc, msg, capability='addeditors')
        try:
            u = ircdb.users.getUser(name)
        except:
            irc.error('User %s is not registered' % name)
        else:
            u.removeCapability('editfactoids')
    removeeditor = wrap(removeeditor, ['text'])
        
Class = Encyclopedia
# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:

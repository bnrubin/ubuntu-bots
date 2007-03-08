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

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import random, re, time, commands, urllib2
import supybot.ircmsgs as ircmsgs

mess = {
    't':           ('http://4q.cc/?pid=fact&person=mrt',               r'</h1>.*?<p>(?P<fact>.*?)</p>',      False),
    'chuck':       ('http://4q.cc/?pid=fact&person=chuck',             r'</h1>.*?<p>(?P<fact>.*?)</p>',      False),
    'vin':         ('http://4q.cc/?pid=fact&person=vin',               r'</h1>.*?<p>(?P<fact>.*?)</p>',      False),
    'bauer':       ('http://www.notrly.com/jackbauer/',                r'<p class="fact">(?P<fact>.*?)</p>', False),
    'bruce':       ('http://geekz.co.uk/schneierfacts/',               r'p class="fact">(?P<fact>.*?)</p',   False),
    'esr':         ('http://geekz.co.uk/esrfacts/',                    r'p class="fact">(?P<fact>.*?)</p',   False),
    'mcgyver':     ('http://www.macgyver.co.za/',                      r'wishtable">(?P<fact>.*?)<div',      False),
    'macgyver':    ('http://www.macgyver.co.za/',                      r'wishtable">(?P<fact>.*?)<div',      False),
    'hamster':     ('http://hamsterrepublic.com/dyn/bobsez',           r'<font.*?<b>(?P<fact>.*?)</font>',   False),
    'yourmom':     ('http://pfa.php1h.com',                            r'<p>(?P<fact>.*?)</p>',              True),
    'bush':        ('http://www.dubyaspeak.com/random.phtml',          r'(?P<fact><font.*</font>)',          True),
    'southpark':   ('http://www.southparkquotes.com/random.php?num=1', r'<p>(?P<fact>.*)</p>',               True),
    'mjg':         ('http://www.angryfacts.com',                       r'</p><h1>(?P<fact>.*?)</h1>',        False),
    'mjg59':       ('http://www.angryfacts.com',                       r'</p><h1>(?P<fact>.*?)</h1>',        False),
    'vmjg':        ('http://www.rjek.com/vmjg59.cgi',                  r'<body>(?P<fact>.*?)<p>',            True),
    'vmjg59':      ('http://www.rjek.com/vmjg59.cgi',                  r'<body>(?P<fact>.*?)<p>',            True),
    'bofh':        ('/home/dennis/ubugtu/plugins/Mess/bofh.txt',       'BOFH Excuse #%d: ',                  False),
    '42':          ('/home/dennis/ubugtu/plugins/Mess/42.txt',         '',                                   False),
    'magic8ball':  ('/home/dennis/ubugtu/plugins/Mess/ball.txt',       '',                                   False),
    'ferengi':     ('/home/dennis/ubugtu/plugins/Mess/ferengi.txt',    'Ferengi rule of acquisition ',       False)
}
data = {}
for m in mess.keys():
    if mess[m][0].startswith('http'):
        mess[m] = (mess[m][0],re.compile(mess[m][1], re.I|re.DOTALL), mess[m][2])
    else:
        fd = open(mess[m][0])
        data[mess[m][0]] = [x.strip() for x in fd.readlines()]
        fd.close()

badwords = ['sex','masturbate','fuck','rape','dick','pussy','prostitute','hooker',
            'orgasm','sperm','cunt','penis','shit','piss','urin','bitch','semen','cock']
tagre = re.compile(r'<.*?>')
def filter(txt,off):
    _txt = txt.lower()
    if not off:
        for b in badwords:
            if b in _txt:
                return None
    txt = txt.replace('<br />','').replace('\n','').replace('\r','')
    txt = txt.replace('<i>','/').replace('</i>','/').replace('<b>','*').replace('</b>','*')
    txt = txt.replace('&quot;','"').replace('&lt;','<').replace('&gt;','>')
    txt = tagre.sub('',txt)
    return txt

times = {}

def ok(func):
    func.offensive = False
    def newfunc(*args, **kwargs):
        global time
        plugin = args[0]
        channel = args[2].args[0]
        if not channel.startswith('#'):
            delay = 5
        else:
            if not plugin.registryValue('enabled', channel):
                return
            delay = plugin.registryValue('delay', channel)
        if channel not in times.keys():
            times[channel] = time.time()
        elif times[channel] < time.time() - delay:
            times[channel] = time.time()
        else:
            return
        i=0
        func(*args, **kwargs)
    newfunc.__doc__ = func.__doc__
    return newfunc

class Mess(callbacks.PluginRegexp):
    """Random Mess plugin"""
    threaded = True
    regexps = ['hugme']
    hugs = ["hugs %s","gives %s a big hug","gives %s a sloppy wet kiss",
            "huggles %s","squeezes %s","humps %s"]


    def isCommandMethod(self, name):
        if not callbacks.PluginRegexp.isCommandMethod(self, name):
            if name in mess:
                return True
            else:
                return False
        else:
            return True

    def listCommands(self):
        commands = callbacks.PluginRegexp.listCommands(self)
        #commands.extend(mes.keys())
        commands.sort()
        return commands

    def getCommandMethod(self, command):
        try:
            return callbacks.PluginRegexp.getCommandMethod(self, command)
        except AttributeError:
            return self.messcb
    
    @ok
    def messcb(self, irc, msg, args):
        """General mess"""
        global data
        cmd = msg.args[1][1:]
        (loc, tx, off) = mess[cmd]
        if off and not self.registryValue('offensive', msg.args[0]):
            return
        if loc.startswith('http'):
            i = 0
            while i < 5:
                inp = utils.web.getUrl(loc)
                fact = tx.search(inp).group('fact')
                fact = filter(fact,off)
                if fact:
                    irc.reply(fact)
                    return
                i += 1
        else:
            i = random.randint(0,len(data[loc])-1)
            if '%d' in tx:
                tx = tx % i
            irc.reply(tx + data[loc][i])
    messcb = wrap(messcb)

    # WARNING: depends on an alteration in supybot/callbacks.py - don't do
    # str(s) if s is unicode!
    @ok
    def dice(self, irc, msg, args, count):
        if not count: count = 1 
        elif count > 5: count = 5
        elif count < 1: count = 1
        t = u' '.join([x.__call__([u"\u2680",u"\u2681",u"\u2682",u"\u2683",u"\u2684",u"\u2685"]) for x in [random.choice]*count])
        irc.reply(t)
    dice = wrap(dice, [additional('int')])

    @ok
    def hugme(self, irc, msg, match):
        r""".*hug.*ubugtu"""
        irc.queueMsg(ircmsgs.action(msg.args[0], self.hugs[random.randint(0,len(self.hugs)-1)] % msg.nick))

    @ok
    def fortune(self, irc, msg, args):
        """ Display a fortune cookie """
        f = commands.getoutput('/usr/games/fortune -s')
        f.replace('\t','    ')
        f = f.split('\n')
        for l in f:
            if l:
                irc.reply(l)
    fortune = wrap(fortune)

    @ok
    def ofortune(self, irc, msg, args):
        """ Display a possibly offensive fortune cookie """
        if not self.registryValue('offensive', msg.args[0]):
            return
        f = commands.getoutput('/usr/games/fortune -so')
        f.replace('\t','    ')
        f = f.split('\n')
        for l in f:
            if l:
                irc.reply(l)
    ofortune = wrap(ofortune)

    @ok
    def futurama(self, irc, msg, args):
        """ Display a futurama quote """
        u = urllib2.urlopen('http://slashdot.org')
        h = [x for x in u.headers.headers if x.startswith('X') and not x.startswith('X-Powered-By')][0]
        irc.reply(h[2:-2].replace(' ',' "',1) + '"')
    futurama = wrap(futurama)

    @ok
    def pony(self, irc, msg, args, text):
        """ NO! """
        if not text:
            text = 'you'
        irc.reply("No %s can't have a pony, %s!" % (text, msg.nick))
    pony = wrap(pony, [additional('text')])

Class = Mess

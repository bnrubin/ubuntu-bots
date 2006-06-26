import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import random, re, time, commands, urllib2
import supybot.ircmsgs as ircmsgs

_bofhfile = '/home/dennis/ubugtu/plugins/Mess/bofh.txt'
_bofhdata = [x.strip() for x in open(_bofhfile).readlines()]

class Mess(callbacks.PluginRegexp):
    """Random Mess plugin"""
    threaded = True
    regexps = ['hugme']
    hugs = ["hugs %s","gives %s a big hug","gives %s a sloppy wet kiss",
            "huggles %s","squeezes %s","humps %s"]
    regex = re.compile('</h1>.*?<p>(.*?)</p>', re.DOTALL)
    entre = re.compile('&(\S*?);')
    jre1 = ('http://www.jackbauerfacts.com/index.php?rate_twenty_four',
            re.compile('current-rating.*?width.*?<td>(.*?)</td>', re.DOTALL))
    jre2 = ('http://www.notrly.com/jackbauer/',
             re.compile('<p class="fact">(.*?)</p>'))
    badwords = ['sex','masturbate','fuck','rape','dick','pussy','prostitute','hooker',
                'orgasm','sperm','cunt','penis','shit','piss','urin','bitch','semen']
    i = 0
    time = {}

    # WARNING: depends on an alteration in supybot/callbacks.py - don't do
    # str(s) if s is unicode!
    def dice(self, irc, msg, args, count):
        if not self.ok(msg.args[0]): return
        if not count: count = 1 
        if count > 5: count = 5
        t = u' '.join([x.__call__([u"\u2680",u"\u2681",u"\u2682",u"\u2683",u"\u2684",u"\u2685"]) for x in [random.choice]*count])
        print t
        #print str(t)
        irc.reply(t)
    dice = wrap(dice, [additional('int')])

    def hugme(self, irc, msg, match):
        r""".*hug.*ubugtu"""
        irc.queueMsg(ircmsgs.action(msg.args[0], self.hugs[random.randint(0,len(self.hugs)-1)] % msg.nick))


    def ok(self, channel, offensive = False):
        if not channel.startswith('#'):
            delay = 5
        else:
            if not self.registryValue('enabled', channel):
                return False
            if offensive and not self.registryValue('offensive', channel):
                return False
            delay = self.registryValue('delay', channel)
        if channel not in self.time.keys():
            self.time[channel] = time.time()
            return True
        if self.time[channel] < time.time() - delay:
            self.time[channel] = time.time()
            return True
        return False

    def fact(self,who,count=0):
        # The website is buggy, mysql errors rear their ugly head a lot. So we
        # retry up to 5 times :)
        if count > 5:
            return
        try:
            fact = utils.web.getUrl('http://4q.cc/index.php?pid=fact&person=%s' % who)
            reo = self.regex.search(fact)
            val = reo.group(1)
            while self.entre.search(val):
                entity = self.entre.search(val).group(1)
                if entity in entities:
                    val = self.entre.sub(entities[entity], val)
                else:
                    val = self.entre.sub('?', val)
            _val = val.lower()
            for word in self.badwords:
                if word in _val:
                    raise RuntimeError
            return val
        except:
            time.sleep(1)
            return self.fact(who,count+1)
            

    def t(self, irc, msg, args):
        """ Display a mr T. fact """
        if not self.ok(msg.args[0]): return
        f = self.fact('mrt')
        if f: irc.reply(f)
    t = wrap(t)
    
    def chuck(self, irc, msg, args):
        """ Display a Chuck Norris fact """
        if not self.ok(msg.args[0]): return
        f = self.fact('chuck')
        if f: irc.reply(f)
    chuck = wrap(chuck)
    
    def vin(self, irc, msg, args):
        """ Display a Vin Diesel fact """
        if not self.ok(msg.args[0]): return
        f = self.fact('vin')
        if f: irc.reply(f)
    vin = wrap(vin)

    hre  = re.compile('<font.*?<b>(.*?)</font>',re.DOTALL)
    hre2 = re.compile('<.*?>')
    def hamster(self, irc, msg, args):
        """ Bob sez! """
        if not self.ok(msg.args[0]): return
        try:
            data = utils.web.getUrl("http://hamsterrepublic.com/dyn/bobsez")
        except:
            return
        # Find correct data
        data = self.hre.search(data).group(1)
        data = self.hre2.sub('',data)
        irc.reply(data.strip())
    hamster = wrap(hamster)

    def fortune(self, irc, msg, args):
        """ Display a fortune cookie """
        if not self.ok(msg.args[0]): return
        f = commands.getoutput('fortune -s')
        f.replace('\t','    ')
        f = f.split('\n')
        for l in f:
            if l:
                irc.reply(l)
    fortune = wrap(fortune)
    def ofortune(self, irc, msg, args):
        """ Display a possibly offensive fortune cookie """
        if not self.ok(msg.args[0], True): return
        f = commands.getoutput('fortune -so')
        f.replace('\t','    ')
        f = f.split('\n')
        for l in f:
            if l:
                irc.reply(l)
    ofortune = wrap(ofortune)

    #def bash(self, irc, msg, args):
    #    """ Display a bash.org quote """
    #    if not self.ok(msg.args[0], True): return
    #    b = utils.web.getUrl('http://bash.org?random1')
    #    r = []
    #    infirst = False
    #    for line in b.split('\n'):
    #        if '#' in line and 'X' in line:
    #            if infirst:
    #                if len(r) < 6:
    #                    bw = False
    #                    for w in self.badwords:
    #                        if w in ''.join(r):
    #                            bw = True
    #                            break
    #                    if not bw:
    #                        for l in r:
    #                            if l:
    #                                 irc.reply(l)
    #                    return
    #            r = []
    #            infirst = True
    #        elif infirst:
    #            r.append(line.strip())
    #    irc.reply('hmm, weird')
    #bash = wrap(bash)

    def bofh(self, irc, msg, args, num):
        """ Display a BOFH excuse """
        if not self.ok(msg.args[0]): return
        if num and num >= 1 and num <= len(_bofhdata):
            i = num
        else:
            i = random.randint(0,len(_bofhdata)-1)
        irc.reply("BOFH excuse #%d: %s" % (i, _bofhdata[i]))
    bofh = wrap(bofh, [additional('int')])

    def bauer(self, irc, msg, args, count=0):
        """ Display a Jack Bauer fact """
        if not self.ok(msg.args[0]): return
        f = self._bauer()
        if f:
            irc.reply(f)
    bauer = wrap(bauer)

    def futurama(self, irc, msg, args):
        """ Display a futurama quote """
        if not self.ok(msg.args[0]): return
        u = urllib2.urlopen('http://slashdot.org')
        h = [x for x in u.headers.headers if x.startswith('X') and not x.startswith('X-Powered-By')][0]
        irc.reply(h[2:-2])
    futurama = wrap(futurama)

    def yourmom(self, irc, msg, args):
        """ Your mom hates IRC """
        if not self.ok(msg.args[0], True): return
        data = utils.web.getUrl('http://pfa.php1h.com/')
        irc.reply(data[data.find('<p>')+3:data.find('</p>')].strip())
    yourmom = wrap(yourmom)

    def bush(self, irc,msg,args):
        """Yes, bush needs help...."""
        if not self.ok(msg.args[0], True): return
        data = utils.web.getUrl('http://www.dubyaspeak.com/random.phtml')
        data = data[data.find('<font'):data.find('</font')]
        while '<' in data:
            data = data[:data.find('<')] + data[data.find('>')+1:]
        irc.reply(data.replace("\n",''))
    bush = wrap(bush)

    def _bauer(self,count=0):
#        if self.i % 2 == 0:
#            (url, re) = self.jre1
#        else:
#            (url, re) = self.jre2
#        self.i += 1
        (url, re) = self.jre2
        if count > 5:
            return
        try:
            fact = utils.web.getUrl(url)
            reo = re.search(fact)
            val = reo.group(1)
            while self.entre.search(val):
                entity = self.entre.search(val).group(1)
                if entity in entities:
                    val = self.entre.sub(entities[entity], val)
                else:
                    val = self.entre.sub('?', val)
            _val = val.lower()
            for word in self.badwords:
                if word in _val:
                    raise RuntimeError
            return val
        except:
            time.sleep(1)
            return self._bauer(count+1)

Class = Mess

from supybot.test import *

import supybot.conf as conf
import supybot.ircmsgs as ircmsgs
import supybot.schedule as schedule

import time


bConf = conf.supybot.plugins.Bantracker
bConf.enabled.setValue(True)


class BantrackerTestCase(ChannelPluginTestCase):
    plugins = ('Bantracker',)

    def getCallback(self):
        for cb in self.irc.callbacks:
            if cb.name() == 'Bantracker':
                break
        return cb

    def testCommentRequest(self):
        ban = ircmsgs.ban('#test', 'asd!*@*', prefix='op!user@host.net')
        self.irc.feedMsg(ban)
        msg = self.irc.takeMsg()
        # ban id is None is because there's no database for this TestCase
        self.assertEqual(str(msg).strip(), 
            "PRIVMSG op :Please comment on the ban of asd!*@* in #test, use: @comment None"
            " <comment>")

    def testReviewResquest(self):
        cb = self.getCallback()
        ban = ircmsgs.ban('#test', 'asd!*@*', prefix='op!user@host.net')
        self.irc.feedMsg(ban)
        self.irc.takeMsg() # ignore comment request comment
        bConf.reviewAfterTime.setValue(1.0/84600) # one second
        cb.reviewBans()
        self.assertFalse(cb.pendingReviews)
        print 'waiting 2 secs..'
        time.sleep(2)
        cb.reviewBans()
        # check is pending
        self.assertTrue(cb.pendingReviews)
        # check msg if op and only op says something
        self.feedMsg('Hi!', to='#test', frm='dude!user@host.net') 
        msg = self.irc.takeMsg()
        self.assertEqual(msg, None)
        self.feedMsg('Hi!', to='#test', frm='op!user@host.net') 
        msg = self.irc.takeMsg()
        self.assertEqual(str(msg).strip(),
                "PRIVMSG op :Please review ban 'asd!*@*' in #test")
        # don't ask again
        cb.reviewBans()
        self.assertFalse(cb.pendingReviews)



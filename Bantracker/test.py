# -*- Encoding: utf-8 -*-
###
# Copyright (c) 2008-2010 Terence Simpson
# Copyright (c) 2010 Elián Hanisch
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

from supybot.test import *

import supybot.conf as conf
import supybot.ircmsgs as ircmsgs
import supybot.world as world

import re
import time


pluginConf = conf.supybot.plugins.Bantracker
pluginConf.enabled.setValue(True)
pluginConf.bansite.setValue('http://foo.bar.com')
pluginConf.database.setValue('bantracker-test.db')

def quiet(channel, hostmask, prefix='', msg=None):
    """Returns a MODE to quiet nick on channel."""
    return ircmsgs.mode(channel, ('+q', hostmask), prefix, msg)

class BantrackerTestCase(ChannelPluginTestCase):
    plugins = ('Bantracker',)

    def setUp(self):
        self.setDb()
        super(BantrackerTestCase, self).setUp()
        pluginConf.request.setValue(False) # disable comments
        pluginConf.request.ignore.set('')
        pluginConf.request.forward.set('')
        pluginConf.review.setValue(False) # disable reviews
        pluginConf.review.when.setValue(1.0/86400) # one second
        pluginConf.review.ignore.set('')
        pluginConf.review.forward.set('')
        # Bantracker for some reason doesn't use Supybot's own methods for check capabilities,
        # so it doesn't have a clue about testing and screws my tests by default.
        # This would fix it until I bring myself to take a look
        cb = self.getCallback()
        f = cb.check_auth
        def test_check_auth(*args, **kwargs):
            if world.testing:
                return True
            else:
                return f(*args, **kwargs)
        cb.check_auth = test_check_auth

    def setDb(self):
        import sqlite, os
        dbfile = os.path.join(os.curdir, pluginConf.database())
        try:
            os.remove(dbfile)
        except:
            pass
        db = sqlite.connect(dbfile)
        cursor = db.cursor()
        cursor.execute('CREATE TABLE bans ('
                'id INTEGER PRIMARY KEY,'
                'channel VARCHAR(30) NOT NULL,'
                'mask VARCHAR(100) NOT NULL,'
                'operator VARCHAR(30) NOT NULL,'
                'time VARCHAR(300) NOT NULL,'
                'removal DATETIME,'
                'removal_op VARCHAR(30),'
                'log TEXT)')
        cursor.execute('CREATE TABLE comments ('
                'ban_id INTEGER,'
                'who VARCHAR(100) NOT NULL,'
                'comment MEDIUMTEXT NOT NULL,'
                'time VARCHAR(300) NOT NULL)')
        cursor.execute('CREATE TABLE sessions ('
                'session_id VARCHAR(50) PRIMARY KEY,'
                'user MEDIUMTEXT NOT NULL,'
                'time INT NOT NULL)')
        cursor.execute('CREATE TABLE users ('
                'username VARCHAR(50) PRIMARY KEY,'
                'salt VARCHAR(8),'
                'password VARCHAR(50))')
        db.commit()
        cursor.close()
        db.close()

    def getCallback(self):
        for cb in self.irc.callbacks:
            if cb.name() == 'Bantracker':
                break
        return cb

    def getDb(self):
        return self.getCallback().db

    def query(self, query, parms=()):
        cursor = self.getDb().cursor()
        cursor.execute(query, parms)
        return cursor.fetchall()

    def feedBan(self, hostmask, prefix='', channel=None, mode='b'):
        if not channel:
            channel = self.channel
        if not prefix:
            prefix = 'op!user@host.net'
        if mode == 'b':
            ban = ircmsgs.ban(channel, hostmask, prefix=prefix)
        elif mode == 'q':
            ban = quiet(channel, hostmask, prefix=prefix)
        elif mode == 'k':
            ban = ircmsgs.kick(channel, hostmask, s='kthxbye!', prefix=prefix)
        elif mode == 'p':
            ban = ircmsgs.part(channel, prefix=hostmask,
                    s='requested by %s (kthxbye!)' %prefix[:prefix.find('!')])
        self.irc.feedMsg(ban)
        return ban

    def testComment(self):
        self.assertResponse('comment 1', "I don't know any ban with id 1.")
        self.feedBan('asd!*@*')
        self.assertResponse('comment 1', 'No comments recorded for ban 1')
        self.assertResponse('comment 1 this is a test', 'The operation succeeded.')
        self.assertRegexp('comment 1', 'test: this is a test$')

    def testMultiComment(self):
        self.feedBan('asd!*@*')
        self.feedBan('qwe!*@*')
        self.assertResponse('comment 1,2,3 this is a test',
                            "I don't know any ban with id 3.")
        msg = self.irc.takeMsg()
        self.assertEqual(msg.args[1], "test: The operation succeeded.")
        self.assertRegexp('comment 1,2', 'test: this is a test$')
        msg = self.irc.takeMsg()
        self.assertTrue(msg.args[1].endswith("test: this is a test"))

    def testCommentDuration(self):
        self.feedBan('asd!*@*')
        self.assertResponse('comment 1 this is a test, 1 week 10', 'Ban set for auto removal: 1')
        self.assertRegexp('comment 1', 'test: this is a test, 1 week 10$')
        self.assertRegexp('baninfo 1', 'expires in 1 week$')

    def testCommentRequest(self):
        pluginConf.request.setValue(True)
        # test bans
        self.feedBan('asd!*@*')
        msg = self.irc.takeMsg()
        self.assertEqual(str(msg).strip(), 
            "PRIVMSG op :Please comment on the ban of asd!*@* in #test, use: @comment 1"
            " <comment>")
        # test quiets
        self.feedBan('dude!*@*', mode='q')
        msg = self.irc.takeMsg()
        self.assertEqual(str(msg).strip(), 
            "PRIVMSG op :Please comment on the quiet of dude!*@* in #test, use: @comment 2"
            " <comment>")
        # test kick/part
        self.feedBan('dude', mode='k')
        msg = self.irc.takeMsg()
        self.assertEqual(str(msg).strip(), 
            "PRIVMSG op :Please comment on the removal of dude in #test, use: @comment 3"
            " <comment>")
        self.feedBan('dude!dude@trollpit.com', mode='p')
        msg = self.irc.takeMsg()
        self.assertEqual(str(msg).strip(), 
            "PRIVMSG op :Please comment on the removal of dude in #test, use: @comment 4"
            " <comment>")

    def testCommentIgnore(self):
        pluginConf.request.setValue(True)
        pluginConf.request.ignore.set('FloodBot? FloodBotK?')
        self.feedBan('asd!*@*', prefix='floodbotk1!bot@botpit.com')
        msg = self.irc.takeMsg()
        self.assertEqual(msg, None)
        self.feedBan('dude!*@*', mode='q', prefix='FloodBot1!bot@botpit.com')
        msg = self.irc.takeMsg()
        self.assertEqual(msg, None)
        self.feedBan('dude', mode='k', prefix='FloodBot2!bot@botbag.com')
        msg = self.irc.takeMsg()
        self.assertEqual(msg, None)
        self.feedBan('dude!dude@trollpit.com', mode='p', prefix='FloodBotK2!bot@botbag.com')
        msg = self.irc.takeMsg()
        self.assertEqual(msg, None)
        self.feedBan('asd!*@*')
        msg = self.irc.takeMsg()
        self.assertEqual(str(msg).strip(), 
            "PRIVMSG op :Please comment on the ban of asd!*@* in #test, use: @comment 5"
            " <comment>")

    def testCommentForward(self):
        pluginConf.request.setValue(True)
        pluginConf.request.forward.set('bot')
        pluginConf.request.forward.channels.set('#channel')
        self.feedBan('qwe!*@*')
        msg = self.irc.takeMsg()
        self.assertEqual(str(msg).strip(), 
            "PRIVMSG op :Please comment on the ban of qwe!*@* in #test, use: @comment 1"
            " <comment>")
        self.feedBan('zxc!*@*', prefix='bot!user@host.com')
        msg = self.irc.takeMsg()
        self.assertEqual(str(msg).strip(), 
            "NOTICE #channel :Please somebody comment on the ban of zxc!*@* in #test done by bot,"
            " use: @comment 2 <comment>")

    def testReview(self):
        pluginConf.review.setValue(True)
        cb = self.getCallback()
        self.feedBan('asd!*@*')
        cb.reviewBans()
        self.assertFalse(cb.pendingReviews)
        print 'waiting 4 secs..'
        time.sleep(2)
        cb.reviewBans()
        # check is pending
        self.assertTrue(cb.pendingReviews)
        # send msg if a user with a matching host says something
        self.feedMsg('Hi!', frm='op!user@fakehost.net') 
        self.assertEqual(self.irc.takeMsg(), None)
        self.feedMsg('Hi!', frm='op_!user@host.net') 
        self.assertEqual(str(self.irc.takeMsg()).strip(),
                "PRIVMSG op_ :Review: ban 'asd!*@*' set on %s in #test, link: "\
                "%s/bans.cgi?log=1" %(cb.bans['#test'][0].ascwhen, pluginConf.bansite()))
        # don't ask again
        cb.reviewBans()
        self.assertFalse(cb.pendingReviews)
        # test again with two ops
        self.feedBan('asd2!*@*')
        self.irc.takeMsg()
        self.feedBan('qwe!*@*', prefix='otherop!user@home.net', mode='q')
        self.irc.takeMsg()
        time.sleep(2)
        cb.reviewBans()
        self.assertTrue(len(cb.pendingReviews) == 2)
        self.feedMsg('Hi!', frm='op!user@fakehost.net') 
        self.assertEqual(self.irc.takeMsg(), None)
        self.assertResponse('banreview', 'Pending ban reviews (2): otherop:1 op:1')
        self.feedMsg('Hi!', frm='mynickissocreative!user@home.net') 
        self.assertEqual(str(self.irc.takeMsg()).strip(),
                "PRIVMSG mynickissocreative :Review: quiet 'qwe!*@*' set on %s in #test, link: "\
                "%s/bans.cgi?log=3" %(cb.bans['#test'][2].ascwhen, pluginConf.bansite()))
        self.feedMsg('ping', to='test', frm='op!user@host.net') # in a query
        self.irc.takeMsg() # drop pong reply
        self.assertEqual(str(self.irc.takeMsg()).strip(),
                "PRIVMSG op :Review: ban 'asd2!*@*' set on %s in #test, link: "\
                "%s/bans.cgi?log=2" %(cb.bans['#test'][1].ascwhen, pluginConf.bansite()))

    def testReviewForward(self):
        pluginConf.review.setValue(True)
        pluginConf.review.forward.set('bot')
        pluginConf.review.forward.channels.set('#channel')
        cb = self.getCallback()
        self.feedBan('asd!*@*', prefix='bot!user@host.net')
        self.feedBan('asd!*@*', prefix='bot!user@host.net', mode='q')
        cb.reviewBans(self.irc)
        self.assertFalse(cb.pendingReviews)
        print 'waiting 2 secs..'
        time.sleep(2)
        cb.reviewBans(self.irc)
        # since it's a forward, it was sent already
        self.assertFalse(cb.pendingReviews)
        self.assertTrue(re.search(
                r"^NOTICE #channel :Review: ban 'asd!\*@\*' set by bot on .* in #test,"\
                r" link: .*/bans\.cgi\?log=1$", str(self.irc.takeMsg()).strip()))
        self.assertTrue(re.search(
                r"^NOTICE #channel :Review: quiet 'asd!\*@\*' set by bot on .* in #test,"\
                r" link: .*/bans\.cgi\?log=2$", str(self.irc.takeMsg()).strip()))

    def testReviewIgnore(self):
        pluginConf.review.setValue(True)
        pluginConf.review.ignore.set('FloodBot? FloodBotK?')
        cb = self.getCallback()
        self.feedBan('asd!*@*', prefix='floodbotk1!bot@botpit.com')
        cb.reviewBans(self.irc)
        self.assertFalse(cb.pendingReviews)
        print 'waiting 2 secs..'
        time.sleep(2)
        cb.reviewBans(self.irc)
        # since it's was ignored, it should not be queued
        self.assertFalse(cb.pendingReviews)

    def testReviewNickFallback(self):
        """If for some reason we don't have ops full hostmask, revert to nick match. This may be
        needed in the future as hostmasks aren't stored in the db."""
        pluginConf.review.setValue(True)
        cb = self.getCallback()
        self.feedBan('asd!*@*')
        cb.bans['#test'][0].who = 'op' # replace hostmask by nick
        print 'waiting 2 secs..'
        time.sleep(2)
        cb.reviewBans()
        # check is pending
        self.assertTrue(cb.pendingReviews)
        self.assertResponse('banreview', 'Pending ban reviews (1): op:1')
        # send msg if a user with a matching nick says something
        self.feedMsg('Hi!', frm='op_!user@host.net') 
        msg = self.irc.takeMsg()
        self.assertEqual(msg, None)
        self.feedMsg('Hi!', frm='op!user@host.net') 
        msg = self.irc.takeMsg()
        self.assertEqual(str(msg).strip(),
                "PRIVMSG op :Review: ban 'asd!*@*' set on %s in #test, link: "\
                "%s/bans.cgi?log=1" %(cb.bans['#test'][0].ascwhen, pluginConf.bansite()))
        # check not pending anymore
        self.assertFalse(cb.pendingReviews)

    def testReviewStore(self):
        """Save pending reviews and when bans were last checked. This is needed for plugin
        reloads"""
        msg1 = ircmsgs.privmsg('nick', 'Hello World')
        msg2 = ircmsgs.privmsg('nick', 'Hello World') # duplicate msg, should be ignored
        msg2 = ircmsgs.privmsg('nick', 'Hello World2')
        msg3 = ircmsgs.notice('#chan', 'Hello World')
        msg4 = ircmsgs.privmsg('nick_', 'Hello World')
        pr = self.getCallback().pendingReviews
        pr['host.net'] = [('op', msg1), ('op', msg2), ('op_', msg3)]
        pr['home.net'] = [('dude', msg4)]
        self.assertResponse('banreview', 'Pending ban reviews (4): op_:1 dude:1 op:2')
        pr.close()
        pr.clear()
        pr.open()
        self.assertResponse('banreview', 'Pending ban reviews (4): op_:1 dude:1 op:2')
        items = pr['host.net']
        self.assertTrue(items[0][0] == 'op' and items[0][1] == msg1)
        self.assertTrue(items[1][0] == 'op' and items[1][1] == msg2)
        self.assertTrue(items[2][0] == 'op_' and items[2][1] == msg3)
        items = pr['home.net']
        self.assertTrue(items[0][0] == 'dude' and items[0][1] == msg4)

    def testReviewBanreview(self):
        pr = self.getCallback().pendingReviews
        m = ircmsgs.privmsg('#test', 'ban review')
        pr['host.net'] = [('op', m), ('op_', m), ('op', m)]
        pr['home.net'] = [('dude', m)]
        pr[None] = [('dude_', m)]
        self.assertResponse('banreview', 'Pending ban reviews (5): dude_:1 op_:1 dude:1 op:2')
        self.assertResponse('banreview --verbose', 
                'Pending ban reviews (5): op@host.net:2 dude_:1 op_@host.net:1 dude@home.net:1')
        self.assertRegexp('banreview --flush op@host', '^No reviews for op@host')
        self.assertResponse('banreview --view dude_', 'ban review')
        self.assertResponse('banreview', 'Pending ban reviews (5): dude_:1 op_:1 dude:1 op:2')
        self.assertResponse('banreview --flush op@host.net', 'ban review')
        #                             love ya supybot ↓
        self.assertEqual(self.irc.takeMsg().args[1], 'test: ban review')
        self.assertResponse('banreview', 'Pending ban reviews (3): dude_:1 op_:1 dude:1')

    def testBan(self):
        self.feedBan('asd!*@*')
        fetch = self.query("SELECT id,channel,mask,operator FROM bans")
        self.assertEqual((1, '#test', 'asd!*@*', 'op'), fetch[0])

    def testQuiet(self):
        self.feedBan('asd!*@*', mode='q')
        fetch = self.query("SELECT id,channel,mask,operator FROM bans")
        self.assertEqual((1, '#test', '%asd!*@*', 'op'), fetch[0])

    def testKick(self):
        self.feedBan('troll', mode='k')
        fetch = self.query("SELECT id,channel,mask,operator FROM bans")
        self.assertEqual((1, '#test', 'troll', 'op'), fetch[0])

    def testPart(self):
        self.feedBan('troll!user@trollpit.net', mode='p')
        fetch = self.query("SELECT id,channel,mask,operator FROM bans")
        self.assertEqual((1, '#test', 'troll', 'op'), fetch[0])

    def testDuration(self):
        cb = self.getCallback()
        self.feedBan('asd!*@*')
        cb.autoRemoveBans(self.irc)
        self.assertFalse(cb.managedBans)
        self.assertNotError('duration 1 1')
        self.assertTrue(cb.managedBans) # ban in list
        print 'waiting 2 secs ...'
        time.sleep(2)
        cb.autoRemoveBans(self.irc)
        self.assertFalse(cb.managedBans) # ban removed
        msg = self.irc.takeMsg() # unban msg
        self.assertEqual(str(msg).strip(), "MODE #test -b :asd!*@*")

    def testDurationMergeModes(self):
        cb = self.getCallback()
        self.feedBan('asd!*@*')
        self.feedBan('qwe!*@*')
        self.feedBan('zxc!*@*')
        self.feedBan('asd!*@*', mode='q')
        self.feedBan('qwe!*@*', mode='q')
        self.feedBan('zxc!*@*', mode='q')
        self.assertNotError('duration 1,2,3,4,5,6 0')
        print 'waiting 1 secs ...'
        time.sleep(1)
        cb.autoRemoveBans(self.irc)
        msg = self.irc.takeMsg() # unban msg
        self.assertEqual(str(msg).strip(),
                         "MODE #test -qqqb zxc!*@* qwe!*@* asd!*@* :zxc!*@*")
        msg = self.irc.takeMsg()
        self.assertEqual(str(msg).strip(), "MODE #test -bb qwe!*@* :asd!*@*")

    def testDurationMultiSet(self):
        self.feedBan('asd!*@*')
        self.assertResponse('duration 1,2 10',
                            "Failed to set duration time on ban 2 (unknow id)")
        msg = self.irc.takeMsg()
        self.assertEqual(msg.args[1], "test: Ban set for auto removal: 1")


    def testDurationQuiet(self):
        cb = self.getCallback()
        self.feedBan('asd!*@*', mode='q')
        self.assertNotError('duration 1 0')
        print 'waiting 1 sec ...'
        time.sleep(1)
        cb.autoRemoveBans(self.irc)
        msg = self.irc.takeMsg() # unban msg
        self.assertEqual(str(msg).strip(), "MODE #test -q :asd!*@*")

    def testDurationBadType(self):
        self.feedBan('nick', mode='k')
        self.assertResponse('duration 1 0',
            "Failed to set duration time on ban 1 (not a ban or quiet)")
        self.feedBan('$a:nick')
        self.assertResponse('duration 2 0', 'Ban set for auto removal: 2')

    def testDurationBadId(self):
        self.assertResponse('duration 1 0', "Failed to set duration time on ban 1 (unknow id)")

    def testDurationInactiveBan(self):
        self.feedBan('asd!*@*')
        self.irc.feedMsg(ircmsgs.unban(self.channel, 'asd!*@*', 
                                       'op!user@host.net'))
        self.assertResponse('duration 1 0', 
                            "Failed to set duration time on ban 1 (ban was removed)")

    def testDurationTimeFormat(self):
        cb = self.getCallback()
        self.feedBan('asd!*@*')
        self.assertNotError('duration 1 10m')
        self.assertEqual(cb.managedBans.shelf[0].expires, 600)
        self.assertNotError('duration 1 2 weeks')
        self.assertEqual(cb.managedBans.shelf[0].expires, 1209600)
        self.assertNotError('duration 1 1m 2 days')
        self.assertEqual(cb.managedBans.shelf[0].expires, 172860)
        self.assertNotError('duration 1 24h 1day')
        self.assertEqual(cb.managedBans.shelf[0].expires, 172800)
        self.assertNotError('duration 1 1m1h1d1w1M1y')
        self.assertEqual(cb.managedBans.shelf[0].expires, 34822860)
        self.assertNotError('duration 1 999')
        self.assertEqual(cb.managedBans.shelf[0].expires, 999)

    def testDurationTimeFormatBad(self):
        self.assertError('duration 1 10 apples')

    def testDurationNotice(self):
        cb = self.getCallback()
        self.feedBan('asd!*@*')
        self.assertNotError('duration 1 300')
        pluginConf.autoremove.notify.channels().append('#test')
        try:
            cb.autoRemoveBans(self.irc)
            msg = self.irc.takeMsg()
            self.assertEqual(str(msg).strip(),
                "NOTICE #test :ban \x0309[\x03\x021\x02\x0309]\x03 \x0310asd!*@*\x03"\
                " in \x0310#test\x03 will expire in a few minutes.")
            # don't send the notice again.
            cb.autoRemoveBans(self.irc)
            self.assertFalse(self.irc.takeMsg())
        finally:
            del pluginConf.autoremove.notify.channels()[:]

    def testAutoremoveStore(self):
        self.feedBan('asd!*@*')
        self.feedBan('qwe!*@*')
        self.feedBan('zxc!*@*', mode='q')
        self.assertNotError('duration 1 10m')
        self.assertNotError('duration 2 1d')
        self.assertNotError('duration 3 1w')
        cb = self.getCallback()
        cb.managedBans.shelf[1].notified = True
        cb.managedBans.close()
        cb.managedBans.shelf = []
        cb.managedBans.open()
        L = cb.managedBans.shelf
        for i, n in enumerate((600, 86400, 604800)):
            self.assertEqual(L[i].expires, n)
        for i, n in enumerate((False, True, False)):
            self.assertEqual(L[i].notified, n)
        for i, n in enumerate((1, 2, 3)):
            self.assertEqual(L[i].ban.id, n)
        for i, n in enumerate(('asd!*@*', 'qwe!*@*', '%zxc!*@*')):
            self.assertEqual(L[i].ban.mask, n)
        self.assertEqual(L[0].ban.channel, '#test')

    def testBaninfo(self):
        cb = self.getCallback()
        self.feedBan('asd!*@*')
        self.assertResponse('baninfo 1', '[1] ban - asd!*@* - #test - never expires')
        self.assertNotError('duration 1 10')
        self.assertResponse('baninfo 1', '[1] ban - asd!*@* - #test - expires soon')
        self.assertNotError('duration 1 34502')
        self.assertResponse('baninfo 1', '[1] ban - asd!*@* - #test - expires in 9 hours and 35 minutes')
        self.irc.feedMsg(ircmsgs.unban(self.channel, 'asd!*@*', 
                                       'op!user@host.net'))
        self.assertResponse('baninfo 1', '[1] ban - asd!*@* - #test - not active')

    def testBaninfoGeneral(self):
        cb = self.getCallback()
        self.feedBan('asd!*@*')
        self.feedBan('qwe!*@*')
        self.assertNotError('duration 1 1d')
        self.assertResponse('baninfo', "1 bans set to expire: 1")
        self.assertNotError('duration 2 1d')
        self.assertResponse('baninfo', "2 bans set to expire: 1, 2")



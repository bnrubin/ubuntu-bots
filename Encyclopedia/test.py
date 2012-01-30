# -*- Encoding: utf-8 -*-
###
# Copyright (c) 2006 Dennis Kaarsemaker
# Copyright (c) 2010 Elián Hanisch
#
# This program is free software: you can redistribute it and/or modify 
# it under the terms of the GNU General Public License as published by 
# the Free Software Foundation, either version 3 of the License, or    
# (at your option) any later version.                                  
#                                                                      
# This program is distributed in the hope that it will be useful,      
# but WITHOUT ANY WARRANTY; without even the implied warranty of       
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the        
# GNU General Public License for more details.                         
#                                                                      
# You should have received a copy of the GNU General Public License    
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
###

from supybot.test import *
import supybot.conf as conf

Econf = conf.supybot.plugins.Encyclopedia
Econf.prefixchar.set('@')


class EncyclopediaTestCase(ChannelPluginTestCase):
    plugins = ('Encyclopedia',)

    def setUp(self):
        super(EncyclopediaTestCase, self).setUp()
        conf.supybot.reply.whenNotCommand.setValue(False)
        self.createDB()

    def createDB(self):
        import sqlite, os
        dbfile = os.path.join(Econf.datadir(), '%s.db' %Econf.database())
        try:
            os.remove(dbfile)
        except:
            pass
        db = sqlite.connect(dbfile)
        cursor = db.cursor()
        cursor.execute('CREATE TABLE facts ('\
                        'id INTEGER PRIMARY KEY,'\
                        'author VARCHAR(100) NOT NULL,'\
                        'name VARCHAR(20) NOT NULL,'\
                        'added DATETIME,'\
                        'value VARCHAR(200) NOT NULL,'\
                        'popularity INTEGER NOT NULL DEFAULT 0);')
        cursor.execute('CREATE TABLE log ('\
                        'id INTEGER PRIMARY KEY,'\
                        'author VARCHAR(100) NOT NULL,'\
                        'name VARCHAR(20) NOT NULL,'\
                        'added DATETIME,'\
                        'oldvalue VARCHAR(200) NOT NULL);')
        db.commit()
        cursor.close()
        db.close()
        self.getCallback().databases = {}

    def getCallback(self):
        for cb in self.irc.callbacks:
            if cb.name() == 'Encyclopedia':
                break
        return cb

    def testAdd(self):
        self.assertNotError('foo is bar')
        self.assertResponse('foo', 'foo is bar')

    def testEdit(self):
        self.assertNotError('foo is bar')
        self.assertNotError('no, foo is bar1')
        self.assertResponse('foo', 'foo is bar1')

    def testKeyword(self):
        self.assertNotError('hello is <reply> Hi, welcome to $chan!')
        self.assertResponse('hello', 'Hi, welcome to #test!')

    def testRequests(self):
        world.testing = False
        self.prefix = 'user!user@home.com'
        try:
            self.assertResponse('test-#ubuntu-se is <reply> blah', 
                                'Your edit request has been forwarded to #ubuntu-ops.  Thank you ' \
                                'for your attention to detail')
            self.assertEqual(self.irc.takeMsg().args[1],
                             'In #test, user said: @test-#ubuntu-se is <reply> blah')
            # test in private, it shouldn't use the prefix char.
            self.assertResponse('test-#ubuntu-se is <reply> blah', 
                                'Your edit request has been forwarded to #ubuntu-ops.  Thank you ' \
                                'for your attention to detail', private=True, usePrefixChar=False)
            self.assertEqual(self.irc.takeMsg().args[1],
                             'In test, user said: test-#ubuntu-se is <reply> blah')
        finally:
            world.testing = True



# vim:set shiftwidth=4 softtabstop=4 tabstop=4 expandtab textwidth=100:

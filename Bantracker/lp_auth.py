#!/usr/bin/python
#
# Copyright (c) 2005-2007 Dennis Kaarsemaker
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

import urllib,urllib2
import xml.dom.minidom as dom
import sha, re

_login_url  = 'https://launchpad.net/+login'
_login_data = 'loginpage_email=%s&loginpage_password=%s&loginpage_submit_login=Log%%20In'
_login_re   = re.compile('logged in as.*?a href=".*?/people/(.*?)"', re.DOTALL)
_urlopener  = urllib2.build_opener(urllib2.HTTPCookieProcessor(), urllib2.HTTPRedirectHandler())

class LaunchpadException(Exception):
    pass

class LaunchpadPerson:
    def __init__(self, email = None, password = None, nick = None):
        self.authenticated = False
        if email and password:
            self.email = email
            _nick = self._login(password)
            if _nick:
                self.authenticated = True
                nick = _nick
        if nick:
            self.get_data(nick)

    def get_data(self, nick):
        self.nick = nick
        try:
            u = urllib2.urlopen('http://launchpad.net/people/%s/+rdf' % urllib.quote(nick))
            rdf = u.read()
            rdf = dom.parseString(rdf)
        except:
            raise
            raise LaunchpadException('Could not parse launchpad data')
        self.mail_shasums = map(lambda x: x.childNodes[0].data.lower(), rdf.getElementsByTagName('foaf:mbox_sha1sum'))
        self.name = rdf.getElementsByTagName('foaf:name')[0].childNodes[0].data
        try:
            self.img = rdf.getElementsByTagName('foaf:img')[0].getAttribute('rdf:resource')
        except: # No image
            self.img = None
        try:
            self.key = rdf.getElementsByTagName('wot:fingerprint')[0].childNodes[0].data
        except: # No image
            self.key = None

    def check_group_membership(self, group):
        try:
            self.mail_shasums
        except AttributeError:
            raise LaunchpadException("Person not logged in and launchpad username not known")
        try:
            fd   = urllib2.urlopen('http://launchpad.net/people/%s/+rdf' % urllib.quote(group))
            rdf = fd.read()
            rdf = dom.parseString(rdf)
        except:
            raise LaunchpadException('Could not parse launchpad data')
        group_mail_shasums = map(lambda x: x.childNodes[0].data.lower(), rdf.getElementsByTagName('foaf:mbox_sha1sum'))
        # If the intersection of shasums and shasums2 is not empty, the persons
        # prefered mail address is in the group.
        return len([x for x in self.mail_shasums if x in group_mail_shasums]) > 0
            
    def _login(self, pw):
        req = urllib2.Request(_login_url, _login_data % (urllib.quote(self.email),urllib.quote(pw)))
        try:
            fd   = _urlopener.open(req)
            data = fd.read().lower()
        except: # Launchpad offline perhaps...
            raise LaunchpadException('Could not parse launchpad data')
        try:
            return _login_re.search(data).group(1)
        except:
            return False

if __name__ == '__main__':
    import sys
    person = LaunchpadPerson(sys.argv[1], sys.argv[2])
    print person.authenticated
    try:
        print person.nick
        print person.name
        print person.mail_shasums
        print person.img
    except:
        raise
        pass
    print person.check_group_membership(sys.argv[3])

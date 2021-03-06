# -*- Encoding: utf-8 -*-
###
# Copyright (c) 2006-2007 Dennis Kaarsemaker
# Copyright (c) 2008-2010 Terence Simpson
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

import cgi, cgitb, re, sys, math, os, hashlib, sqlite, random, time, datetime, pytz, Cookie, StringIO, urllib2
import cPickle as pickle
cgitb.enable()

form = cgi.FieldStorage()
cookie = Cookie.SimpleCookie()
if os.environ.has_key('HTTP_COOKIE'):
    cookie.load(os.environ['HTTP_COOKIE'])

if cookie.has_key('sess'):
    cookie['sess']['max-age'] = 2592000 * 3
    cookie['sess']['version'] = 1
if cookie.has_key('tz'):
    cookie['tz']['max-age'] = 2592000 * 3
    cookie['tz']['version'] = 1

class IOWrapper:
    '''Class to wrap default IO, used with templates'''
    def __init__(self):
        self.buf = []
    def write(self, val):
        self.buf.append(val)
    def getvalue(self):
        return self.buf
    
sys.stdout = IOWrapper()
sys.stderr = IOWrapper()

def send_page(template):
    '''Sends a template page and exit'''
    data = sys.stdout.getvalue()
    errdata = sys.stderr.getvalue()
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    print "Content-Type: text/html"
    print cookie
    print ""

    fd = open(template)
    tmpl = fd.read()
    fd.close()
    sys.stdout.write(tmpl[:tmpl.find('%e')])
    for e in errdata:
        sys.stdout.write(e)
    sys.stdout.write(tmpl[tmpl.find('%e')+2:tmpl.find('%s')])
#    print tmpl[:tmpl.find('%s')]
    for d in data:
        sys.stdout.write(d)
    sys.stdout.write(tmpl[tmpl.find('%s')+2:])
    sys.exit(0)

def q(txt):
    '''Simple HTML entity quoting'''
    return txt.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')


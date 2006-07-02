import cgi, cgitb, re, sys, math, os, md5, sqlite, random, time, datetime, pytz, Cookie, StringIO
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
    def __init__(self):
        self.buf = []
    def write(self, val):
        self.buf.append(val)
    def getvalue(self):
        return self.buf
    
sys.stdout = IOWrapper()

def send_page(template):
    data = sys.stdout.getvalue()
    sys.stdout = sys.__stdout__
    print "Content-Type: text/html"
    print cookie
    print ""

    fd = open(template)
    tmpl = fd.read()
    fd.close()
    print tmpl[:tmpl.find('%s')]
    for d in data:
        print d
    print tmpl[tmpl.find('%s')+2:]
    sys.exit(0)

def q(txt):
    return txt.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')
    

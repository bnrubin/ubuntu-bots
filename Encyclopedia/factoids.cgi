#!/usr/bin/python

import sqlite 
import datetime
import cgi, cgitb
from math import ceil
import re
cgitb.enable

NUM_PER_PAGE=50.0

buf = ''
def out(txt):
    global buf
    buf += str(txt)

def link(match):
    url = match.group('url')
    txt = url
    if len(txt) > 30:
        txt = txt[:20] + '&hellip;' + txt[-10:]
    return '<a href="%s">%s</a>' % (url, txt)
    
def q(txt):
    txt = str(txt).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace('\n','<br />')
    # linkify
    rx = re.compile('(?P<url>(https?://\S+|www\S+))')
    return rx.sub(link, txt)

database = 'ubuntu'

form = cgi.FieldStorage()
if 'db' in form:
    database = form['db'].value
try:
    page = int(form['page'].value)
except:
    page = 0
order_by = 'added DESC'
try:
    order_by = form['order'].value
    if order_by not in ('added DESC', 'added ASC', 'name DESC', 'name ASC', 'popularity DESC','popularity ASC'):
        order_by = 'added DESC'
except:
    order_by = 'added DESC'
    
con = sqlite.connect('/home/dennis/ubugtu/data/facts/%s.db' % database)
cur = con.cursor()

cur.execute("""SELECT COUNT(*) FROM facts WHERE value NOT LIKE '<alias>%%'""")
num = cur.fetchall()[0][0]
npages = int(ceil(num / float(NUM_PER_PAGE)))
out('&middot;')
for i in range(npages):
    out(' <a href="factoids.cgi?db=%s&order=%s&page=%s">%d</a> &middot;' % (database, order_by, i, i+1))
out('<br />Order by<br />&middot;')
out(' <a href="factoids.cgi?db=%s&order=%s&page=%d">%s</a> &middot;' % (database, 'name ASC', page, 'Name +'))
out(' <a href="factoids.cgi?db=%s&order=%s&page=%d">%s</a> &middot;' % (database, 'name DESC', page, 'Name -'))
out(' <a href="factoids.cgi?db=%s&order=%s&page=%d">%s</a> &middot;' % (database, 'popularity ASC', page, 'Popularity +'))
out(' <a href="factoids.cgi?db=%s&order=%s&page=%d">%s</a> &middot;' % (database, 'popularity DESC', page, 'Popularity -'))
out(' <a href="factoids.cgi?db=%s&order=%s&page=%d">%s</a> &middot;' % (database, 'added ASC', page, 'Date added +'))
out(' <a href="factoids.cgi?db=%s&order=%s&page=%d">%s</a> &middot;' % (database, 'added DESC', page, 'Date added -'))


out('<table cellspacing="0"><tr><th>Factoid</th><th>Value</th><th>Author</th></tr>')

cur.execute("SELECT name, value, author, added, popularity FROM facts WHERE value NOT LIKE '<alias>%%' ORDER BY %s LIMIT %d, %d" % (order_by, page*NUM_PER_PAGE, NUM_PER_PAGE))
factoids = cur.fetchall()
i = 0
for f in factoids:
    cur.execute("SELECT name FROM facts WHERE value LIKE %s", '<alias> ' + f[0])
    f = list(f)
    f[0] += '\n' + '\n'.join([x[0] for x in cur.fetchall()])
    out('<tr')
    if i % 2: out(' class="bg2"')
    i += 1
    out('><td>%s</td><td>%s</td><td>%s<br />Added on: %s<br />Requested %s times</td>' % tuple([q(x) for x in f]))

out('</table>')

print "Content-Type: text/html; charset=UTF-8"
print ""

fd = open('factoids.tmpl')
tmpl = fd.read()
fd.close()
print tmpl % (buf)

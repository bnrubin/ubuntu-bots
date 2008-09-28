#!/usr/bin/python
###
# Copyright (c) 2006,2007 Dennis Kaarsemaker
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

import sys
# This needs to be set to the location of the commoncgi.py file
sys.path.append('/var/www/')
from commoncgi import *

### Variables
NUM_PER_PAGE=50.0
# Directory of the factoids database
datadir = '/home/ubotu/data'
# Database name (without .db)
default_database = 'ubuntu'

#### You shouldn't have to change anything under this line ###

databases = [x for x in os.listdir(datadir)]

# Initialize
database = default_database
order_by = 'popularity DESC'
page = 0
search = ''
factoids = []
total = 0

# Read POST
if 'db' in form:
    database = form['db'].value
if database not in databases:
    database = default_database
con = sqlite.connect(os.path.join(datadir, database + '.db'))
cur = con.cursor()

try: page = int(form['page'].value)
except: pass
    
if 'order' in form:
    if form['order'].value in ('added DESC', 'added ASC', 'name DESC', 'name ASC', 'popularity DESC','popularity ASC'):
        order_by = form['order'].value
if 'search' in form:
    search = form['search'].value
    
# Select factoids
if search:
    keys = [urllib2.unquote(x.strip()) for x in search.split() if len(x.strip()) >=2][:5]
    if not keys:
        keys = ['']
    query1 = "SELECT name, value, author, added, popularity FROM facts WHERE name NOT LIKE '%-also' AND ("
    query2 = "SELECT COUNT(name) FROM facts WHERE "
    bogus = False
    for k in keys:
        k = k.replace("'","\'")
        if bogus:
            query1 += ' OR '
            query2 += ' OR '
        query1 += "name LIKE '%%%s%%' OR VAlUE LIKE '%%%s%%'" % (k, k)
        query2 += "name LIKE '%%%s%%' OR VAlUE LIKE '%%%s%%'" % (k, k)
        bogus=True

    query1 += ') ORDER BY %s LIMIT %d, %d' % (order_by, NUM_PER_PAGE*page, NUM_PER_PAGE)
    cur.execute(query1)
    factoids = cur.fetchall()
    cur.execute(query2)
    total = cur.fetchall()[0][0]
else:
    cur.execute("SELECT name, value, author, added, popularity FROM facts WHERE value NOT LIKE '<alias>%%' AND name NOT LIKE '%%-also' ORDER BY %s LIMIT %d, %d" % (order_by, page*NUM_PER_PAGE, NUM_PER_PAGE))
    factoids = cur.fetchall()
    cur.execute("""SELECT COUNT(*) FROM facts WHERE value NOT LIKE '<alias>%%'""")
    total = cur.fetchall()[0][0]

# Pagination links
npages = int(math.ceil(total / float(NUM_PER_PAGE)))
print '&middot;'
for i in range(npages):
    print '<a href="factoids.cgi?db=%s&search=%s&order=%s&page=%s">%d</a> &middot;' % (database, search, order_by, i, i+1)
    
print '<br />Order by<br />&middot;';
print ' <a href="factoids.cgi?db=%s&search=%s&order=%s&page=0">%s</a> &middot;' % (database, search, 'name ASC', 'Name +')
print ' <a href="factoids.cgi?db=%s&search=%s&order=%s&page=0">%s</a> &middot;' % (database, search, 'name DESC', 'Name -')
print ' <a href="factoids.cgi?db=%s&search=%s&order=%s&page=0">%s</a> &middot;' % (database, search, 'popularity ASC', 'Popularity +')
print ' <a href="factoids.cgi?db=%s&search=%s&order=%s&page=0">%s</a> &middot;' % (database, search, 'popularity DESC', 'Popularity -')
print ' <a href="factoids.cgi?db=%s&search=%s&order=%s&page=0">%s</a> &middot;' % (database, search, 'added ASC', 'Date added +')
print ' <a href="factoids.cgi?db=%s&search=%s&order=%s&page=0">%s</a> &middot;' % (database, search, 'added DESC', 'Date added -')

print '<table cellspacing="0"><tr><th>Factoid</th><th>Value</th><th>Author</th></tr>'

url_re = re.compile('(?P<url>(https?://\S+|www\S+))')
def q(x):
    x = str(x).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br />')
    return url_re.sub(link, x)
def link(match):
    url = match.group('url')
    txt = url
    if len(txt) > 30:
        txt = txt[:20] + '&hellip;' + txt[-10:]
    return '<a href="%s">%s</a>' % (url, txt)

i = 0
for f in factoids:
    f = list(f)
    f[2] = f[2][:30]
    if '.' in f[3]:
        f[3] = f[3][:f[3].find('.')]
    cur.execute("SELECT value FROM facts WHERE name = %s", f[0] + '-also')
    more = cur.fetchall()
    if len(more):
        f[1] += ' $hr$' + ' $hr$'.join([x[0] for x in more])
    cur.execute("SELECT name FROM facts WHERE value LIKE %s", '<alias> ' + f[0])
    f[0] += ' \n' + ' \n'.join([x[0] for x in cur.fetchall()])
    print '<tr'
    if i % 2: print ' class="bg2"'
    i += 1
    print '><td>%s</td><td>%s</td><td>%s<br />Added on: %s<br />Requested %s times</td>' % tuple([q(x) for x in f])

print '</table>'

send_page('factoids.tmpl')

#!/usr/bin/env python
###
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

import os
import sys
import time
# This needs to be set to the location of the commoncgi.py file
sys.path.append('/var/www/bot')
from commoncgi import *

### Variables
db = '/home/bot/data/bans.db'
num_per_page = 100
pagename = os.path.basename(sys.argv[0])
disable_anonymous = False # Set this to True to disable anonymous access

t1 = time.time()

con = sqlite.connect(db)
cur = con.cursor()

# Login check
error = ''
user = None

# Delete old sessions
try:
    session_timeout = int(time.time()) - (2592000 * 3)
    cur.execute('DELETE FROM sessions WHERE time < %d', (session_timeout,))
except:
    pass

# Session handling
if form.has_key('sess'):
    cookie['sess'] = form['sess'].value
if cookie.has_key('sess'):
    sess = cookie['sess'].value
    try:
        cur.execute('SELECT user FROM sessions WHERE session_id=%s',(sess,))
        user = cur.fetchall()[0][0]
    except:
        con.commit()
        pass

if not user and disable_anonymous:
    print "Sorry, bantracker is not available for anonymous users<br />"
    print "Join <a href=irc://irc.freenode.net/ubuntu-ops>#ubuntu-ops</a> on irc.freenode.net to discuss bans"
    send_page('bans.tmpl')
    sys.exit(0)

# Log
if form.has_key('log'):
    log_id = form['log'].value
    plain = False
    mark = False
    mark_value = ''
    regex = False
    regex_value = ''

    if form.has_key('plain') and form['plain'].value.lower() in ('1', 'true', 'on'):
        plain = True

    if form.has_key('mark'):
        mark = True
        mark_value = form['mark'].value
        if form.has_key('regex') and form['regex'].value in ('1', 'true', 'on'):
            regex = True
            regex_value = 'checked="checked"'

    con = sqlite.connect(db)
    cur = con.cursor()
    cur.execute("SELECT log FROM bans WHERE id=%s", log_id)
    log = cur.fetchall()
    con.commit()
    con.close()

    if not log or not log[0] or not log[0][0]:
        if plain:
            print >> sys.stderr, '<div id="error">No such log with ID: %s' % q(log_id)
            send_page('empty.tmpl')
        else:
            print >> sys.stderr, 'No such log with ID: %s' % q(log_id)
            send_page('log.tmpl')

    log = log[0][0]

    if not plain:
        print '  <div class="main">'
        print '    <form id="hform" action="%s" method="get">' % pagename
        print '      <fieldset>'
        print '        <input type="hidden" name="log" id="log" value="%s">' % q(log_id)
        print '        <label for="mark">Highlight:</label>'
        print '        <input type="text" name="mark" id="mark" value="%s"/>' % q(mark_value)
        print '        <input type="checkbox" name="regex" id="regex" %s>' % regex_value
        print '        <label for="regex">Regex</label>'
        print '      </fieldset>'
        print '      <input class="input" type="submit" id="hform_submit" value="Update">'
        print '    </form>'
        print '  </div>'

    pad = '<br />'
    if plain:
        pad = ''
        print '<pre id="textlog">'
    else:
        print '<div id="textlog">'

    if mark:
        if regex:
            mark = re.compile(mark_value, re.I)
        else:
            escaped = re.escape(mark_value).replace('%', '.*')
            mark = re.compile(escaped, re.I)

    lines = log.splitlines()
    for line in lines:
        if plain:
            print q(line)
        elif mark:
            if mark.search(line):
                print ' <span class="highlight">%s</span>%s' % (q(line), pad)
            else:
                print " <span>%s</span>%s" % (q(line), pad)
        else:
            print '  <span>%s</span>%s' % (q(line), pad)

    if plain:
        print '</pre>'
        send_page('empty.tmpl')

    print '</div><br />'
    print '<div>'
    print ' <form id="comment_form" action="%s" method="post">' % pagename
    print '  <fieldset>'
    print '   <legend>Add a comment</legend>'
    print '   <textarea cols="50" rows="5" class="input" name="comment"></textarea><br />'
    print '   <input type="hidden" name="comment_id" value="%s" />' % log_id
    print '   <input class="submit" type="submit" value="Send" />'
    print '  </fieldset>'
    print ' </form>'
    print '</div>'

    send_page('log.tmpl')

# Main page
# Process comments
if form.has_key('comment') and form.has_key('comment_id') and user:
    cur.execute('SELECT ban_id FROM comments WHERE ban_id=%s and comment=%s', (form['comment_id'].value, form['comment'].value))
    comm = cur.fetchall()
    if not len(comm):
        cur.execute('INSERT INTO comments (ban_id, who, comment, time) VALUES (%s, %s, %s, %s)',
                    (form['comment_id'].value,user,form['comment'].value,pickle.dumps(datetime.datetime.now(pytz.UTC))))
    con.commit()

# Write the page
print '<form action="%s" method="POST">' % pagename

# Personal data
print '<div class="pdata">'
if user:
    print 'Logged in as: %s <br /> ' % user

print 'Timezone: '
if form.has_key('tz') and form['tz'].value in pytz.common_timezones:
    tz = form['tz'].value
elif cookie.has_key('tz') and cookie['tz'].value in pytz.common_timezones:
    tz = cookie['tz'].value
else:
    tz = 'UTC'
cookie['tz'] = tz
print '<select class="input" name="tz">'
for zone in pytz.common_timezones:
    if zone == tz:
        print '<option value="%s" selected="selected">%s</option>' % (zone, zone)
    else:
        print '<option value="%s">%s</option>' % (zone, zone)
print '</select>'
print '<input class="submit" type="submit" value="change" />'
print '</form><br />'
print '</div>'

tz = pytz.timezone(tz)

haveQuery  = form.has_key('query') or form.has_key('channel') or form.has_key('operator')

def isOn(k):
    default = not haveQuery
    if not form.has_key(k):
        return default
    if form[k].value.lower() in ('on', '1', 'true', 'yes'):
        return True
    if form[k].value.lower() in ('off', '0', 'false', 'no'):
        return False
    return default

def makeInput(name, label, before=False, type="checkbox", extra=''):
    if before:
        print '<label for="%s">%s</label>' % (name, label)
    value = ''
    if type == "checkbox":
        if isOn(name):
            value = ' checked="checked"'
    else:
        if form.has_key(name):
            value = ' value="%s"' % form[name].value,

    print '<input class="input" type="%s" name="%s" id="%s"%s /> %s' \
            % (type, name, name, value, extra)
    if not before:
        print '<label for="%s">%s</label>' % (name, label)
    print '<br />'

# Search form
print '<div class="search">'
print '<form action="%s" method="GET">' % pagename
makeInput("channel", "Channel:", True, "text")
makeInput("operator", "Operator:", True, "text")
makeInput("query", "Search:", True, "text", extra="(% and _ are wildcards)")

# Search fields
print '<div style="float:left">'
makeInput("kicks", "Kicks")
makeInput("bans", "Bans")
makeInput("oldbans", "Removed bans")
print '</div>'
    
print '<div style="float:left">'
makeInput("mutes", "Include mutes")
makeInput("floodbots", "Include Floodbots")
print '</div>'
    
print '<div style="clear:both"><input  class="submit" type="submit" value="search" /></div>'
print '</form></div>'

# Pagination, only when not processing a search
if not form.has_key('query'):
    sort = ''
    if form.has_key('sort'):
        sort='&sort=' + form['sort'].value
    print '<div style="clear: both">&middot;'
    cur.execute('SELECT COUNT(*) FROM bans')
    nump = math.ceil(int(cur.fetchall()[0][0]) / float(num_per_page))
    for i in range(int(nump)):
        print '<a href="%s?page=%d%s">%d</a> &middot;' % (pagename, i, sort, i+1)
    print '</div>'

# Empty log div, will be filled with AJAX
print '<div id="log" class="log">&nbsp;</div>'

# Main bans table
# Table heading
print '<div>'
print '<table cellspacing="0">'
print '<thead>'
print '<tr>'
for h in [['Channel',0, 45], ['Nick/Mask',1, 25], ['Operator',2, 0], ['Time',6, 15]]:
    # Negative integers for backwards searching
    try:
        v = int(form['sort'].value)
        if v < 10: h[1] += 10
    except:
        pass
    print '<th style="width: %s%%"><a href="%s?sort=%s">%s</a></th>' % (pagename, h[2], h[1], h[0])
print '<th style="width: 15%">Log</th>'
print '<th>ID</th>'
print '</tr>'
print '</thead>'
print '<tbody>'

# Select and filter bans
def getBans(id=None, mask=None, kicks=True, oldbans=True, bans=True, floodbots=True, operator=None,
            channel=None):
    sql = "SELECT channel, mask, operator, time, removal, removal_op, id FROM bans"
    args = []
    where = []
    if id:
        where.append("id = %s")
        args.append(id)
    if mask:
        where.append("mask LIKE %s")
        args.append('%' + mask + '%')
    if not floodbots:
        where.append("operator NOT LIKE 'floodbot%%'")
    if operator:
        where.append("operator LIKE %s")
        args.append(operator)
    if channel:
        where.append("channel LIKE %s")
        args.append(channel)
    if not kicks:
        where.append("mask LIKE '%%!%%'")
    if not (oldbans or bans):
        where.append("mask NOT LIKE '%%!%%'")
    else:
        if kicks:
            s = "(mask NOT LIKE '%%%%!%%%%' OR (mask LIKE '%%%%!%%%%' AND %s))"
        else:
            s = "%s"
        if not oldbans:
             where.append(s % "removal IS NULL")
        elif not bans:
             where.append(s % "removal IS NOT NULL")
    sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"
    #print where, args, "<br/>"
    cur.execute(sql, args)
    return cur.fetchall()

def filterMutes(item):
    if item[1][0] == '%':
        return False
    return True

def getQueryTerm(query, term):
    if term[-1] != ':':
        term += ':'
    if term in query:
        idx = query.index(term) + len(term)
        ret = query[idx:].split(None, 1)[0]
        query = query.replace(term + ret, '', 1).strip()
        return (query, ret)
    return (query, None)


bans = []
oper = chan = False

if form.has_key('query'):
    query = form['query'].value
    if query.isdigit():
        bans = getBans(id=int(query))
        start = 0; end = 1
    else:
        if form.has_key('channel'):
            chan = form['channel'].value
        if form.has_key('operator'):
            oper = form['operator'].value

        bans = getBans(mask=query, kicks=form.has_key('kicks'),
                                   oldbans=form.has_key('oldbans'),
                                   bans=form.has_key('bans'),
                                   floodbots=form.has_key('floodbots'),
                                   operator=oper,
                                   channel=chan)

        if not form.has_key('mutes'):
            bans = filter(lambda x: filterMutes(x), bans)

        start = 0; end = len(bans)
else:
    page = 0
    try:
        page = int(form['page'].value)
    except:
        pass
    start = page * num_per_page
    end = (page+1) * num_per_page

# Sort the bans
def _sortf(x1,x2,field):
   if x1[field] < x2[field]: return -1
   if x1[field] > x2[field]: return 1
   return 0
        
if form.has_key('sort'):
    try:
        field = int(form['sort'].value)
    except:
        pass
    else:
        if field in (0,1,2,6,10,11,12,16):
            bans.sort(lambda x1,x2: _sortf(x1,x2,field%10))
            if field >= 10:
                bans.reverse()

# And finally, display them!
i = 0
for b in bans[start:end]:
    if i % 2:
        print '<tr class="bg2">'
    else:
        print "<tr>"
    # Channel
    print '<td id="channel-%d">%s %s</td>' % (b[6],'',b[0])
    # Mask
    print '<td id="mask-%d">%s' % (b[6], b[1])
    # Ban removal
    if b[4]:
        print '<br /><span class="removal">(Removed)</span>'
    print'</td>'
    # Operator
    print '<td id="operator-%d">%s' % (b[6], b[2])
    if b[4]:                  # Ban removal
        print u'<br /><span class="removal">%s</span>' % b[5]
    print '</td>'
    # Time
    print '<td id="time-%d">%s' % (b[6], pickle.loads(b[3]).astimezone(tz).strftime("%b %d %Y %H:%M:%S"))
    if b[4]:                  # Ban removal
        print '<br /><span class="removal">%s</span>' % pickle.loads(b[4]).astimezone(tz).strftime("%b %d %Y %H:%M:%S")
    print '</td>'
    # Log link
    print """<td>
                Show log <a class="pseudolink" id="loglink-%s" onclick="showlog('%s')">inline</a>
                | <a href="%s?log=%d">full</a>
            </td>""" % (b[6], b[6], pagename, b[6])

    # ID
    print '<td id="id-%d">%d</td>' % (b[6], b[6])
    print "</tr>"
    
    # Comments
    if i % 2:
        print '<tr class="bg2">'
    else:
        print "<tr>"
    cur.execute('SELECT who, comment, time FROM comments WHERE ban_id = %d', (b[6],))
    comments = cur.fetchall()
    if len(comments) == 0:
        print '<td colspan="5" class="comment">'
        print '<div class="invisible" id="comments">%d</div>' % b[6]
        print '<span class="removal">(No comments) </span>'
    else:
        print '<td colspan="5" class="comment" id="comments-%d">' % b[6]
        print '<div class="invisible" id="comments">%d</div>' % b[6]
        for c in comments:
            print q(c[1]).replace('\n', '<br />')
            print u' <span class="removal"><br />%s, %s</span><br />' % \
                (c[0],pickle.loads(c[2]).astimezone(tz).strftime("%b %d %Y %H:%M:%S"))
    if user:
        print """<span class="pseudolink" onclick="toggle('%s','comment')">Add comment</span>""" % b[6]
        print """<div class="invisible" id="comment_%s"><br />""" % b[6]
        print """   <form action="%s" method="POST">""" % pagename
        print """       <textarea cols="50" rows="5" class="input" name="comment"></textarea><br />"""
        print """       <input type="hidden" name="comment_id" value="%s" />""" % b[6]
        print """       <input class="submit" type="submit" value="Send" />"""
        print """   </form>"""
        print """</div>"""
    print '</td><td></td></tr>'
    i += 1

print '</table>'

if not bans and form.has_key('query'):
    if chan and oper:
        print "<center><u>No matches for:</u> &quot;%s&quot in %s by %s;</center>" % (form['query'].value, chan, oper)
    elif chan:
        print "<center><u>No matches for:</u> &quot;%s&quot; in %s</center>" % (form['query'].value, chan)
    elif oper:
        print "<center><u>No matches for:</u> &quot;%s&quot; by %s</center>" % (form['query'].value, oper)
    else:
        print "<center><u>No matches for:</u> &quot;%s&quot;</center>" % form['query'].value
elif form.has_key('query'):
    print "<center>Found %s matches</center>" % end

t2 = time.time()

print "Generated in %.4f seconds<br/>" % (t2 - t1)

# Aaaaaaaaaaaaaaaaand send!
send_page('bans.tmpl')

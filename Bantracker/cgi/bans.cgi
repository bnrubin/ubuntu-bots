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

import sys
import time
import urllib
import ConfigParser

CONFIG_FILENAME = "bantracker.conf"
config = ConfigParser.RawConfigParser()
config.add_section('webpage')

# set default values
config.set('webpage', 'database', '/home/bot/data/bans.db')
config.set('webpage', 'results_per_page', '100')
config.set('webpage', 'anonymous_access', 'True')
config.set('webpage', 'PLUGIN_PATH', '/var/www/bot')
config.set('webpage', 'irc_network', 'irc.freenode.net')
config.set('webpage', 'irc_channel', '#ubuntu-ops')

try:
    config.readfp(open(CONFIG_FILENAME))
except IOError:
    config.write(open(CONFIG_FILENAME, 'w'))

# This needs to be set to the location of the commoncgi.py file
PLUGIN_PATH = config.get('webpage', 'PLUGIN_PATH')
if PLUGIN_PATH:
    sys.path.append(PLUGIN_PATH)

try:
    from commoncgi import *
except:
    print "Content-Type: text/html" 
    print
    print "<p>Failed to load the module commoncgi</p>"
    print "<p>Check that the config option PLUGIN_PATH in '%s' is correct.</p>" % CONFIG_FILENAME ##< Is this "private" information?
    sys.exit(-1)

db = config.get('webpage', 'database')
num_per_page = config.getint('webpage', 'results_per_page')
anonymous_access = config.getboolean('webpage', 'anonymous_access')
irc_network = config.get('webpage', 'irc_network')
irc_channel = config.get('webpage', 'irc_channel')

t1 = time.time()

try:
    con = sqlite.connect(db)
    cur = con.cursor()
except sqlite.DatabaseError:
    print >> sys.stderr, "Unable to connect to to database '%s'" % db
    send_page('bans.tmpl')

def db_execute(query, args):
    try:
        cur.execute(query, args)
        return cur
    except sqlite.OperationalError:
        print >> sys.stderr, "The database is locked, wait a bit and try again."
        send_page('bans.tmpl')

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
if 'sess' in form:
    cookie['sess'] = form['sess'].value
if 'sess' in cookie:
    sess = cookie['sess'].value
    try:
        cur.execute('SELECT user FROM sessions WHERE session_id=%s',(sess,))
        user = cur.fetchall()[0][0]
    except:
        con.commit()
        pass

if not user and not anonymous_access:
    print "Sorry, bantracker is not available for anonymous users<br />"
    print 'Join <a href="irc://%s/%s">%s</a> on %s to discuss bans.' % (irc_network, irc_channel[1:], irc_channel, irc_network)
    send_page('bans.tmpl')

haveQuery = False

def urlencode(**kwargs):
    """Return the url options as a string, inserting additional ones if given."""
    d = dict([ (i.name, i.value) for i in form.list ])
    d.update(kwargs)
    return urllib.urlencode(d.items())

def isTrue(value):
    """Returns True if the form value is one of "1", "true", "yes", or "on", case insensitive"""
    if not value:
        return False
    return value.lower() in ('1', 'true', 'yes', 'on')

def isFalse(value):
    """Returns True if the form value is one of "0", "false", "no", or "off", case insensitive"""
    if not value:
        return False
    return value.lower() in ('0', 'false', 'no', 'off')

def isOn(k):
    global haveQuery
    default = not haveQuery
    if not k in form:
        return default
    if isTrue(form[k].value):
        return True
    if isFalse(form[k].value):
        return False
    return default


# Log
if 'log' in form:
    log_id = form['log'].value
    plain = False
    mark = False
    mark_value = ''
    regex = False
    regex_value = ''

    if 'plain' in form and isTrue(form['plain'].value):
        plain = True

    if 'mark' in form:
        mark = True
        mark_value = form['mark'].value
        if 'regex' in form and isTrue(form['regex'].value):
            regex = True
            regex_value = 'checked="checked"'

    log = db_execute("SELECT log FROM bans WHERE id=%s", log_id).fetchall()

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
        print '    <form id="hform" action="" method="get">'
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
            try:
                mark = re.compile(mark_value, re.I)
            except:
                print >> sys.stderr, "Malformed regex %r" % mark_value
                mark = False
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
    print ' <form id="comment_form" action="" method="post">'
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
if 'comment' in form and 'comment_id' in form and user:
    cur.execute('SELECT ban_id FROM comments WHERE ban_id=%s and comment=%s', (form['comment_id'].value, form['comment'].value))
    comm = cur.fetchall()
    if not len(comm):
        try:
            cur.execute('INSERT INTO comments (ban_id, who, comment, time) VALUES (%s, %s, %s, %s)',
                        (form['comment_id'].value, user,form['comment'].value, pickle.dumps(datetime.datetime.now(pytz.UTC))))
            con.commit()
        except sqlite.DatabaseError:
            con.rollback()
            print >> sys.stderr, "Sorry, failed to submit comment to the database. Please try again later."

# Write the page
print '<form action="" method="POST">'

# Personal data
print '<div class="pdata">'
if user:
    print 'Logged in as: %s <br /> ' % user

print 'Timezone: '
if 'tz' in form and form['tz'].value in pytz.common_timezones:
    tz = form['tz'].value
elif 'tz' in cookie and cookie['tz'].value in pytz.common_timezones:
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

haveQuery = 'query' in form or 'channel' in form or 'operator' in form

def makeInput(name, label, before=False, type="checkbox", extra=''):
    if before:
        print '<label for="%s">%s</label>' % (name, label)
    value = ''
    if type == "checkbox":
        if isOn(name):
            value = ' checked="checked"'
    else:
        if name in form:
            value = ' value="%s"' % form[name].value,

    print '<input class="input" type="%s" name="%s" id="%s"%s /> %s' \
            % (type, name, name, value, extra)
    if not before:
        print '<label for="%s">%s</label>' % (name, label)
    print '<br />'

# Search form
print '<div class="search">'
print '<form action="" method="GET">'
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

if not haveQuery:
    # sqlite2 sucks, getting the last bans takes a lot of time.
    # so lets disable that so at least the page loads quickly.
    ## Maybe we should include a link on the main page for those who do want
    ## to list the latest bans? --tsimpson
    print '<div style="clear: both"></div>'
    send_page('bans.tmpl')

# Select and filter bans
def getBans(id=None, mask=None, kicks=True, oldbans=True, bans=True, floodbots=True, operator=None,
            channel=None, limit=None, offset=0, withCount=False):
    sql = "SELECT channel, mask, operator, time, removal, removal_op, id FROM bans"
    args = []
    where = []
    if id:
        where.append("id=%s")
        args.append(id)
    if mask:
        where.append("mask LIKE %s")
        args.append('%' + mask + '%')
    if not floodbots:
        where.append("operator NOT LIKE 'floodbot%%'")
    if operator:
        where.append("operator LIKE %s") ## LIKE or ==? --tsimpson
        args.append(operator)
    if channel:
        where.append("channel LIKE %s") ## LIKE or ==? --tsimpson
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
    if where:
        where = " WHERE " + " AND ".join(where)
    else:
        where = ''
    sql += where
    sql += " ORDER BY id DESC"
    if limit:
        sql += " LIMIT %s OFFSET %s" % (limit, offset)
    #print sql, "<br/>"
    #print sql_count, "<br/>"
    #print args, "<br/>"
    # Things seems faster if we do the query BEFORE counting. Due to caches probably.
    bans = db_execute(sql, args).fetchall()
    count = None
    if withCount:
        sql_count = "SELECT count(*) FROM bans%s" % where
        count = int(db_execute(sql_count, args).fetchone()[0])
        return bans, count
    return bans

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

page = 0
if 'page' in form:
    page = int(form['page'].value)

bans = []
ban_count = 0
query = oper = chan = None
if 'query' in form:
    query = form['query'].value

if query and query.isdigit():
    bans = getBans(id=int(query))
    ban_count = len(bans)

if not bans:
    if 'channel' in form:
        chan = form['channel'].value
    if 'operator' in form:
        oper = form['operator'].value
    bans, ban_count = getBans(mask=query, kicks=isOn('kicks'),
                               oldbans=isOn('oldbans'),
                               bans=isOn('bans'),
                               floodbots=isOn('floodbots'),
                               operator=oper,
                               channel=chan,
                               limit=num_per_page,
                               offset=num_per_page * page,
                               withCount=True)

    if not isOn('mutes'):
        bans = filter(lambda x: filterMutes(x), bans)


# Sort the bans
def _sortf(x1,x2,field):
   if x1[field] < x2[field]: return -1
   if x1[field] > x2[field]: return 1
   return 0
        
if 'sort' in form:
    try:
        field = int(form['sort'].value)
    except:
        pass
    else:
        if field in (0,1,2,6,10,11,12,16):
            bans.sort(lambda x1,x2: _sortf(x1,x2,field%10))
            if field >= 10:
                bans.reverse()

if haveQuery:
    if not ban_count:
        print '<div style="clear: both">Nothing found.</div>'
    elif ban_count == 1:
        print '<div style="clear: both">Found one match.</div>'
    else:
        print '<div style="clear: both">Found %s matches.</div>' % ban_count

# Pagination
if bans:
    print '<div style="clear: both">'
    print '&middot;'
    num_pages = int(math.ceil(ban_count / float(num_per_page)))
    for i in range(num_pages):
        print '<a href="?%s">%d</a> &middot;' % (urlencode(page=i), i + 1)
    print '</div>'
else:
    # nothign to show
    print '<div style="clear: both"></div>' # if I don't print this the page is messed up.
    send_page('bans.tmpl')

# Empty log div, will be filled with AJAX
print '<div id="log" class="log">&nbsp;</div>'

# Main bans table
# Table heading
print '<div>'
print '<table cellspacing="0">'
print '<thead>'
print '<tr>'
for h in [ ('Channel',   0, 45), 
           ('Nick/Mask', 1, 25), 
           ('Operator',  2, 0),
           ('Time',      6, 15) ]:
    # Negative integers for backwards searching
    try:
        v = int(form['sort'].value)
        if v < 10: h[1] += 10
    except:
        pass
    #print '<th style="width: %s%%"><a href="?sort=%s">%s</a></th>' % (h[2], h[1], h[0])
    print '<th style="width: %s%%">%s</th>' % (h[2], h[0])
print '<th style="width: 15%">Log</th>'
print '<th>ID</th>'
print '</tr>'
print '</thead>'
print '<tbody>'

# And finally, display them!
i = 0
for b in bans:
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
                | <a href="?log=%d">full</a>
            </td>""" % (b[6], b[6], b[6])

    # ID
    print '<td id="id-%d">%d</td>' % (b[6], b[6])
    print "</tr>"
    
    # Comments
    if i % 2:
        print '<tr class="bg2">'
    else:
        print "<tr>"
    db_execute('SELECT who, comment, time FROM comments WHERE ban_id=%d', (b[6],))
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
        print """   <form action="" method="post">"""
        print """       <textarea cols="50" rows="5" class="input" name="comment"></textarea><br />"""
        print """       <input type="hidden" name="comment_id" value="%s" />""" % b[6]
        print """       <input class="submit" type="submit" value="Send" />"""
        print """   </form>"""
        print """</div>"""
    print '</td><td></td></tr>'
    i += 1


print '</table>'

t2 = time.time()

print "<!-- Generated in %.4f seconds -->" % (t2 - t1)

# Aaaaaaaaaaaaaaaaand send!
send_page('bans.tmpl')

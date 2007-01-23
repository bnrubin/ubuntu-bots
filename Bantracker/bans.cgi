#!/usr/bin/python
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
sys.path.append('/var/www/bots.ubuntulinux.nl')
from commoncgi import *
import lp_auth
import sha

### Variables
db       = '/home/dennis/ubugtu/data/bans.db'
lp_group = 'ubuntu-irc'
num_per_page = 100

con = sqlite.connect(db)
cur = con.cursor()

# Login check
person   = None
error    = ''
anonymous = form.has_key('anonymous')
anonlink =  ''
if anonymous:
    anonlink = '&anonymous=1';

# Delete old sessions
cur.execute("""DELETE FROM sessions WHERE time < %d""", int(time.time()) - 2592000 * 3)
# Registration?
if form.has_key('lpuser') and form.has_key('lpmail'):
    cur.execute("""SELECT * FROM USERS WHERE username = %s""", form['lpuser'].value)
    if len(cur.fetchall()):
        error = """User is already registered"""
    else:
        import sha, commands, random
        try:
            newperson = lp_auth.LaunchpadPerson(nick=form['lpuser'].value, email=form['lpmail'].value)
        except:
            error = """Username incorrect. Your username is the $someone in
                       http://launchpad.net/people/$someone that is your
                       launchpad homepage"""
        else:
            mailsha = sha.new('mailto:%s' % form['lpmail'].value).hexdigest().lower()
            if mailsha in newperson.mail_shasums:
                if not newperson.key:
                    error = """Your launchpad account does not have a GPG key. Please
                               set a GPG key on launchpad"""
                else:
                    chars = "qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM1234567890"
                    password = ""
                    salt = "" 
                    for i in xrange(8):
                        password += chars[random.randint(0,len(chars)-1)]
                        salt += chars[random.randint(0,len(chars)-1)]
                    try:
                        os.system('gpg --homedir /tmp --keyserver hkp://subkeys.pgp.net --recv-keys %s 2>/dev/null' % newperson.key)
                        (infd, outfd) = os.popen2('gpg --homedir /tmp --encrypt --armor --trust-model always --recipient %s 2>/dev/null' 
                                              % newperson.key)
                        infd.write(password)
                        infd.close()
                        gpg = outfd.read()
                        outfd.close()
                    except:
                        error = "A gpg error occured. Please check your key on launchpad"
                    else:
                        fd = os.popen('mail -a "From: Ubugtu <ubugtu@ubuntu-nl.org>" -s "Your bantracker account" %s' 
                                      % form['lpmail'].value.replace('ubuntu@sourceguru.net','mezzle@gmail.com'), 'w')
                        fd.write(gpg)
                        fd.close()
                        error = "Your password has been sent (encrypted) to your e-mail address"
                        cur.execute("""INSERT INTO users (username, salt, password) VALUES (%s, %s, %s)""",
                                    (form['lpuser'].value, salt, 
                                     sha.new(salt + sha.new(password + salt).hexdigest().lower()).hexdigest().lower()))
                        con.commit()
            else:
                error = """Username and mailaddress don't match. Username is the $someone
                           in http://launchpad.net/people/$someone that is your
                           launchpad homepage"""

# Session handling
if cookie.has_key('sess'):
    try:
        sess = cookie['sess'].value
        cur.execute("""SELECT user FROM sessions WHERE session_id=%s""",sess)
        user = cur.fetchall()[0][0]
        person = pickle.loads(user)
    except:
        con.commit()
        pass

# Login
if not person and form.has_key('user') and form.has_key('pw'):
    import sha
    cur.execute("SELECT salt, password FROM users WHERE username = %s", form['user'].value)
    data = cur.fetchall()
    if data:
        salt, password = data[0]
        if password != sha.new(salt + sha.new(form['pw'].value + salt).hexdigest().lower()).hexdigest().lower():
            error = "Username or password incorrect"
        else:
            try:
                person = lp_auth.LaunchpadPerson(nick = form['user'].value)
            except lp_auth.LaunchpadException:
                person = None
                error  = 'An error occured while talking to launchpad'
            person.authenticated = True
            if person.check_group_membership(lp_group):
                # Create a session
                sessid = md5.new('%s%s%d' % (os.environ['REMOTE_ADDR'], time.time(), random.randint(1,100000))).hexdigest()
                cookie['sess'] = sessid
                try:
                    cur.execute("""INSERT INTO sessions (session_id, user, time) VALUES
                                   (%s, %s, %d);""", (sessid, pickle.dumps(person), int(time.time())))
                except:
                    con.commit()
                    raise
                con.commit()
            else:
                person.authenticated = False
                error = "You are not in the '%s' group on launchpad" % lp_group

# Not authenticated.
if not (person and person.authenticated) and not anonymous:
    if error:
         print """<span style="color:red">%s</span>""" % error
    print """<form action="/bans.cgi" method="post">
             Login:<br />
             <input class="input" type="text" name="user" /><br />
             Password:<br />
             <input class="input" type="password" name="pw" /><br />
             <input class="submit" type="submit" value="Log in" />
           </form>
           <form>
             No account yet? Enter your launchpad name and mailaddress
             here.<br /><br />
             Name:<br />
             <input class="input" type="text" name="lpuser" /><br />
             Mail address:<br />
             <input class="input" type="text" name="lpmail" /><br /><br />
             <input class="submit" type="submit" value="Request password" />
           </form>
           <a href="/bans.cgi?anonymous=1">Browse the bantracker anonymously</a>
              """
    send_page('bans.tmpl')

# Log
if form.has_key('log'):
   cur.execute("""SELECT log FROM bans WHERE id=%s""", form['log'].value)
   log = cur.fetchall()
   con.commit()
   print q(log[0][0]).replace('\n', '<br />')
   send_page('empty.tmpl')

# Main page
# Process comments
if form.has_key('comment') and form.has_key('comment_id') and not anonymous:
    cur.execute("""SELECT ban_id FROM comments WHERE ban_id=%s and comment=%s""", (form['comment_id'].value, form['comment'].value))
    comm = cur.fetchall()
    if not len(comm):
        cur.execute("""INSERT INTO comments (ban_id, who, comment, time) VALUES (%s, %s, %s, %s)""",
                    (form['comment_id'].value,person.name,form['comment'].value,pickle.dumps(datetime.datetime.now(pytz.UTC))))
    con.commit()

# Write the page
print '<form action="bans.cgi" method="POST">'
if anonymous:
    print '<input type="hidden" name="anonymous" value="1" />'

# Personal data
print '<div class="pdata">'
if not anonymous:
    print 'Logged in as: %s <br /> ' % person.name
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
    print '<option value="%s"' % zone
    if zone == tz:
        print ' selected="selected"'
    print ">%s</option>" % zone
print '</select><input class="submit" type="submit" value="change" /></form><br />'
if not anonymous:
    if form.has_key('pw1') and form.has_key('pw2'):
        pw1 = form['pw1'].value; pw2 = form['pw2'].value
        if pw1 and pw2:
            if pw1 != pw2:
                print "Passwords don't match!<br />"
            else:
                cur.execute("SELECT salt FROM users WHERE username = %s", person.nick)
                salt = cur.fetchall()[0][0]
                cur.execute("UPDATE USERS SET password = %s WHERE username = %s",
                             (sha.new(salt + sha.new(pw1 + salt).hexdigest().lower()).hexdigest().lower(), person.nick))
                con.commit()
    print '<form action="bans.cgi" method="POST">'
    print 'Password: '
    print '<input class="input" type="password" name="pw1" size="10"/>'
    print '<input class="input" type="password" name="pw2" size="10"/>'
    print '<input class="submit" type="submit" value="change" /></form>'
print '</div>'

tz = pytz.timezone(tz)

# Search form
print '<div class="search">'
print '<form action="/bans.cgi" method="GET">'
if anonymous:
    print '<input type="hidden" name="anonymous" value="1" />'
print '<input class="input" type="text" name="query"'
if form.has_key('query'):
   print 'value="%s" ' % form['query'].value
print '/> Search string (% is wildcard)<br />'

# Search fields
print '<div style="float:left">'
print '<input class="input" type="checkbox" name="kicks" '
if form.has_key('kicks') or not form.has_key('query'):
    print 'checked="checked" '
print '/> Search in kicks<br />'
print '<input class="input" type="checkbox" name="oldbans" '
if form.has_key('oldbans') or not form.has_key('query'):
    print 'checked="checked" '
print '/> Search in removed bans<br />'
print '<input class="input" type="checkbox" name="bans" '
if form.has_key('bans') or not form.has_key('query'):
    print 'checked="checked"  '
print '/> Search in existing bans<br />'
print '</div>'
    
print '<div style="float:left">'
print '<input class="input" type="checkbox" name="oldmutes" '
if form.has_key('oldmutes') or not form.has_key('query'):
    print 'checked="checked" '
print '/> Search in removed mutes<br />'
print '<input class="input" type="checkbox" name="mutes" '
if form.has_key('mutes') or not form.has_key('query'):
    print 'checked="checked"  '
print '/> Search in existing mutes<br />'
print '</div>'
    
print '<div style="clear:both"><input  class="submit" type="submit" value="search" /></div>'
print '</form></div>'

# Pagination, only when not processing a search
if not form.has_key('query'):
    sort = ''
    if form.has_key('sort'):
        sort='&sort=' + form['sort'].value
    print '<div style="clear: both">&middot;'
    cur.execute('SELECT COUNT(id) FROM bans')
    nump = math.ceil(int(cur.fetchall()[0][0]) / float(num_per_page))
    for i in range(nump):
        print '<a href="bans.cgi?page=%d%s%s">%d</a> &middot;' % (i, sort, anonlink, i+1)
    print '</div>'

# Empty log div, will be filled with AJAX
print '<div id="log" class="log">&nbsp;</div>'

# Main bans table
# Table heading
print '<table cellspacing="0" ><tr>'
for h in [['Channel',0], ['Nick/Mask',1], ['Operator',2], ['Time',6]]:
    # Negative integers for backwards searching
    try:
        v = int(form['sort'].value)
        if v < 10: h[1] += 10
    except:
        pass
    print '<th><a href="bans.cgi?sort=%s%s">%s</a></th>' % (h[1],anonlink,h[0])
print '<th>Log</th></tr>'

# Select and filter bans
cur.execute("SELECT channel,mask,operator,time,removal,removal_op,id FROM bans ORDER BY id DESC")
bans = cur.fetchall()
    
def myfilter(item, regex, kick, ban, oldban, mute, oldmute):
    if '!' not in item[1]: 
        if not kick: return False
    elif item[1][0] == '%':
        if item[4]:
            if not oldmute: return False
        else:
            if not mute: return False
    else:
        if item[4]:
            if not oldban: return False
        else:
            if not ban: return False
    return regex.search(item[1]) or regex.search(item[2]) or regex.search(item[0]) or (item[5] and regex.search(item[5]))

if form.has_key('query'):
    k = b = ob = m = om = False
    if form.has_key('kicks'):    k  = True
    if form.has_key('oldbans'):  ob = True
    if form.has_key('bans'):     b  = True
    if form.has_key('oldmutes'): om = True
    if form.has_key('mutes'):    m  = True
    regex = re.compile(re.escape(form['query'].value).replace('\%','.*'), re.DOTALL | re.I)
    bans = filter(lambda x: myfilter(x, regex, k, b, ob, m, om), bans)
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
    print '<tr'
    if i % 2:
        print ' class="bg2"'
    i += 1
    print '>'
    # Channel
    print '<td>%s %s</td>' % ('',b[0])
    # Mask
    print '<td>%s' % b[1]
    # Ban removal
    if b[4]:
        print '<br /><span class="removal">(Removed)</span>'
    print'</td>'
    # Operator
    print '<td>%s' % b[2]
    if b[4]:                  # Ban removal
        print u'<br /><span class="removal">%s</span>' % b[5]
    print '</td>'
    # Time
    print '<td>%s'      % pickle.loads(b[3]).astimezone(tz).strftime("%b %d %Y %H:%M:%S")
    if b[4]:                  # Ban removal
        print '<br /><span class="removal">%s</span>' % pickle.loads(b[4]).astimezone(tz).strftime("%b %d %Y %H:%M:%S")
    print '</td>'
    # Log link
    print """<td><span class="pseudolink" onclick="showlog('%s')">Show log</span></td>""" % b[6]
    print '</tr>'
    
    # Comments
    print '<tr'
    if not i % 2:
        print ' class="bg2"'
    print '>'
    print '<td colspan="5" class="comment">'
    cur.execute("""SELECT who, comment, time FROM comments WHERE ban_id = %s""" % b[6])
    comments = cur.fetchall()
    if len(comments) == 0:
        print '<span class="removal">(No comments) </span>'
    else:
        for c in comments:
            print q(c[1])
            print u' <span class="removal"><br />%s, %s</span><br />' % \
                (c[0],pickle.loads(c[2]).astimezone(tz).strftime("%b %d %Y %H:%M:%S"))
    if not anonymous:
        print """<span class="pseudolink" onclick="toggle('%s','comment')">Add comment</span>""" % b[6]
        print """<div class="invisible" id="comment_%s"><br />""" % b[6]
        print """<form action="bans.cgi" method="POST"><textarea cols="50" rows="5" class="input" name="comment"></textarea><br />"""
        print """<input type="hidden" name="comment_id" value="%s" />""" % b[6]
        print """<input class="submit" type="submit" value="Send" /></form>"""
    print '</td></tr>'

print '</table>'

# Aaaaaaaaaaaaaaaaand send!
send_page('bans.tmpl')

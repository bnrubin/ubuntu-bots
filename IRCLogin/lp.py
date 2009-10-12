###
# Copyright (c) 2008, Terence Simpson
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

import sys, re, urllib2, RDF

def striphtml(data):
    '''striphtml(data) -> list
Try to strip away the HTML tags in the list "data"
'''
    start = re.compile('<[a-z]+.*>') # opening HTML tag <...>
    end = re.compile('</[a-z]+>') # closing HTML tag </...>
    # find and replace code
    for i in range(0, len(data)):
        # replace the closing tag first, as the starting regex will match up to the closing other wise
        r = end.search(data[i])
        while r:
            data[i] = data[i].replace(data[i][r.start():r.end()], '', 1)
            r = end.search(data[i])
        r = start.search(data[i])
        while r:
            data[i] = data[i].replace(data[i][r.start():r.end()], '', 1)
            r = start.search(data[i])
    # return the list back
    return data

def getIRCNick(user, errors=True):
    '''getIRCNick(user, errors) -> list
Try to get the IRC nick(s) from the LP account "user".
If errors is True print any errors to stderr, defaults to True
'''
    # Get the HTML data from LP
    try:
        data = urllib2.urlopen('https://launchpad.net/~%s' % user).read()
    except Exception, e:
        if errors: print >> sys.stderr, "Could not get user info (%s)" % e
        return
    details = '<div class="portletContent portletBody">'
    # Try and find the "Contact details" section
    sindex = data.find(details)
    if sindex == -1:
        if errors: print >> sys.stderr, "Could not get user info (No data)"
        return
    eindex = data.find('</div>', sindex) + 6
    data = data[sindex:eindex]
    data = [l.strip() for l in data.splitlines() if l.strip()]
    # Look for IRC info
    try:
        sindex = data.index('<th>IRC:</th>')
        eindex = data.index('</div>', sindex)
    except:
        if errors: print >> sys.stderr, "Could not get user info (No IRC nick(s) specified)"
        return
    data = data[sindex:eindex]
    ircnames = []
    count = 0
    # Loop through the data looking for IRC nicks
    while True:
        count += 1
        if count >= 10:
            break # Try not to loop forever :)
        try:
            # When this fails, it raises an exception
            s = data.index('<th>IRC:</th>')
            e = data.index('</tr>') + 1
            if e <= s:
                break
            # Limit to freenode nicks
            if 'freenode' in data[s:e] or 'ubuntu' in data[s:e]:
                ircnames.append(data[s:e])
            del data[s:e]
        except:
            return [striphtml(i)[1].lower() for i in ircnames]
    # incase we got to a break in the loop
    return [striphtml(i)[1].lower() for i in ircnames]

def getUsers(team='ubuntu-irc'):
    parser = RDF.Parser()
    stream = parser.parse_as_stream("https://launchpad.net/~%s/+rdf" % team) # Parse the teams RDF
    d = []
    # Get the RDF data for the team members
    for f in stream:
        if 'http://xmlns.com/foaf/0.1/nick' in str(f.predicate):
            d.append(f)

    # Do some silly text replacement and get the actual nick
    d = [str(i).replace('{',"").replace('}',"").split(', ')[2].replace('"','') for i in d]
    d.sort()
    return d

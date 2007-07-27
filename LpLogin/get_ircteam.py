#!/usr/bin/python

import urllib, urllib2
import xml.dom.minidom as dom
import re, sys, optparse

usage = "Usage: %prog [options] launchpad_group"
parser = optparse.OptionParser(usage=usage)
parser.add_option("-o", "--output", dest='outfile', help="Output to FILE",
                  metavar="FILE")
(options, args) = parser.parse_args()
if len(args) < 1:
    parser.error('No group specified')
lp_group = args[0]
if options.outfile:
    outfd = open(options.outfile,'w')
else:
    outfd = sys.stdout

people_re = re.compile(r'href="/~([^/"]*)"')
nickname_re = re.compile(r'<code.*?120.*?>(.*?)</code>.*\n.*freenode',re.I)
def get_group_members(group):
    nicks = []
    u = urllib2.urlopen('http://launchpad.net/~%s/+members' % urllib.quote(group))
    html = u.read().lower()
    # Split into people and groups
    p1 = html.find('active members')
    p2 = html.find('pending members')
    people = people_re.findall(html[p1:p2])
    for p in people:
        u = urllib2.urlopen('http://launchpad.net/~%s' % urllib.quote(p))
        html = u.read()
        n = nickname_re.findall(html)
        nicks += n
    return [x.lower() for x in nicks]

outfd.write("\n".join(get_group_members(lp_group)))

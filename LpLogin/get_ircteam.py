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

people_re = re.compile(r"""(?:href=".*?~(?P<person>[^/]*?)".*?)
                           #relationship.*?(href=".*?~(?P<group>.*?)".*?)*""",
                           re.VERBOSE | re.I | re.DOTALL)
nickname_re = re.compile(r'<code.*?120.*?>(.*?)</code>.*\n.*freenode',re.I)
def get_group_members(group):
    nicks = []
    u = urllib2.urlopen('http://launchpad.net/~%s' % urllib.quote(group))
    html = u.read().lower()
    # Split into people and groups
    p1 = html.find('team members')
    p2 = html.find('relationship to other teams')
    p3 = html.find('a member of')
    people = people_re.findall(html[p1:p2])
    teams = people_re.findall(html[p2:p3])
    for p in people:
        u = urllib2.urlopen('http://launchpad.net/~%s' % urllib.quote(p))
        html = u.read()
        n = nickname_re.findall(html)
        nicks += n
    for t in teams:
        nicks += get_group_members(t)
    return [x.lower() for x in nicks]

outfd.write("\n".join(get_group_members(lp_group)))

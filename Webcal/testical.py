#!/usr/bin/python
import datetime, pytz, urllib2, ical
def filter(events):
    ret = [x for x in events if x.seconds_ago() < 1800]
    ret.sort()
    ret.sort() # Needs this twice for some reason
    return ret

data = urllib2.urlopen("http://tinyurl.com/6mzmbr").read()
parser = ical.ICalReader(data)

events = filter(parser.events)

print "\n".join([x.schedule() for x in events])

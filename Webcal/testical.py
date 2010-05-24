#!/usr/bin/env python
# -*- Encoding: utf-8 -*-
###
# Copyright (c) 2008-2010 Terence Simpson
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

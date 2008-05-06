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

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.schedule as schedule
import supybot.ircmsgs as ircmsgs
import pytz
import ical
import datetime, shelve, re
import cPickle as pickle

class Webcal(callbacks.Plugin):
    """@schedule <timezone>: display the schedule in your timezone"""
    threaded = True

    def __init__(self, irc):
        callbacks.Privmsg.__init__(self, irc)
        self.irc = irc
        try:
            schedule.removeEvent(self.name())
            schedule.removeEvent(self.name() + 'b')
        except AssertionError:
            pass
        try:
            schedule.addPeriodicEvent(self.refresh_cache,  60 * 20, name=self.name())
            schedule.addPeriodicEvent(self.autotopics,     60, name=self.name() + 'b')
        except AssertionError:
            pass
        self.cache = {}
        self.firstevent = {}

    def die(self):
        try:
            schedule.removeEvent(self.name())
            schedule.removeEvent(self.name() + 'b')
        except AssertionError:
            pass
        self.cache.clear()

    def reset(self):
        self.cache.clear()

    def update(self, url):
        data = utils.web.getUrl(url)
        parser = ical.ICalReader(data)
        self.cache[url] = parser.events

    def refresh_cache(self):
        for c in self.irc.state.channels:
            url = self.registryValue('url', c)
            if url:
                self.update(url)

    def autotopics(self):
        for c in self.irc.state.channels:
            url = self.registryValue('url', c)
            if url and self.registryValue('doTopic', c):
                if url not in self.cache:
                    self.update(url)
                events = self.filter(self.cache[url], c)
                #if events[0].is_on() and self.firstevent[c].summary == events[0].summary:
                #    continue
                newtopic = self.maketopic(c, template=self.registryValue('topic',c))
                if newtopic.strip() != self.irc.state.getTopic(c).strip():
                    self.irc.queueMsg(ircmsgs.topic(c, newtopic))

    def filter(self, events, channel):
        now = datetime.datetime.now(pytz.UTC)
        fword = self.registryValue('filter', channel)
        return [x for x in events if fword.lower() in x.raw_data.lower() and x.seconds_ago() < 1800]
        
    def maketopic(self, c, tz=None, template='%s', num_events=6):
        url = self.registryValue('url',c)
        if url not in self.cache.keys():
            self.update(url)

        now = datetime.datetime.now(pytz.UTC)
        events = self.filter(self.cache[url],c)[:num_events]
        preamble = ''
        if not len(events):
            return template % "No meetings scheduled"
        # The standard slack of 30 minutes after the meeting will be an
        # error if there are 2 conscutive meetings, so remove the first 
        # one in that case
        if len(events) > 1 and events[1].startDate < now:
                events = events[1:]
        ev0 = events[0]
        if ev0.seconds_to_go() < 600:
            preamble = 'Current meeting: %s ' % ev0.summary.replace('Meeting','').strip()
            if num_events == 1:
                return preamble + (template % '')
            events = events[1:]

        if num_events == 1:
            ev = events[0]
            return template % ('Next meeting: %s in %s' % (ev.summary.replace(' Meeting','').strip(), ev.time_to_go()))

        events = [x.schedule(tz) for x in events]
        return preamble + (template % ' | '.join(events))
        
    # Now the commands
    def topic(self, irc, msg, args):
        c = msg.args[0]
        url = self.registryValue('url', c)
        if not url or not self.registryValue('doTopic',channel=c):
            return
        self.update(url)

        events = self.filter(self.cache[url], c)
        if events[0].is_on():
            irc.error("Won't update topic while a meeting is in progress")
            return
            
        newtopic = self.maketopic(c, template=self.registryValue('topic',c))
        if not (newtopic.strip() == irc.state.getTopic(c).strip()):
            irc.queueMsg(ircmsgs.topic(c, newtopic))
    topic = wrap(topic)

    def _tzfilter(self, tz, ud):
        if tz == ud:
            return True
        pos = tz.find('/')
        while not (pos == -1):
            if tz[pos+1:] == ud:
                return True
            pos = tz.find('/',pos+1)
        # Repeat, with spaces replaced by underscores
        ud = ud.replace(' ','_')
        if tz == ud:
            return True
        pos = tz.find('/')
        while not (pos == -1):
            if tz[pos+1:] == ud:
                return True
            pos = tz.find('/',pos+1)
        
        return False

    def schedule(self, irc, msg, args, tz):
        """ Retrieve the date/time of scheduled meetings in a specific timezone """
        if not tz:
            tz = 'utc'
        if irc.isChannel(msg.args[0]):
            c = msg.args[0]
        else:
            c = self.registryValue('defaultChannel')
            if not c:
                return
        url = self.registryValue('url', c)
        if not url:
            return
        tzs = filter(lambda x: self._tzfilter(x.lower(),tz.lower()), pytz.all_timezones)
        if not tzs:
            irc.error('Unknown timezone: %s - Full list: %s' % (tz, self.config.registryValue('tzUrl') or 'Value not set'))
            return
        newtopic = self.maketopic(c,tz=tzs[0])
        events = self.filter(self.cache[url], msg.args[0])
        if events[0].is_on(): # FIXME channel filter
            irc.error('Please don\'t use @schedule during a meeting')
            irc.reply('Schedule for %s: %s' % (tzs[0], newtopic), private=True)
        else:
            irc.reply('Schedule for %s: %s' % (tzs[0], newtopic))
    schedule = wrap(schedule, [additional('text')])

    def now(self, irc, msg, args, tz):
        """ Display the current time """
        if not tz:
            tz = 'utc'
        if irc.isChannel(msg.args[0]):
            c = msg.args[0]
        else:
            c = self.registryValue('defaultChannel')
            if not c:
                return
        url = self.registryValue('url', c)
        if not url:
            return
        tzs = filter(lambda x: self._tzfilter(x.lower(),tz.lower()), pytz.all_timezones)
        if not tzs:
            irc.error('Unknown timezone: %s - Full list: %s' % (tz, self.config.registryValue('tzUrl') or 'Value not set'))
            return
        now = datetime.datetime.now(pytz.UTC)
        newtopic = self.maketopic(c,tz=tzs[0],num_events=1)
        events = self.filter(self.cache[url], msg.args[0])
        newtopic = 'Current time in %s: %s - %s' % \
            (tzs[0], datetime.datetime.now(pytz.UTC).astimezone(pytz.timezone(tzs[0])).strftime("%B %d %Y, %H:%M:%S"), newtopic)

        if events[0].is_on(): # Fixme -- channel filter
            irc.error('Please don\'t use @schedule during a meeting')
            irc.reply(newtopic, private=True)
        else:
            irc.reply(newtopic)
    now = wrap(now, [additional('text')])
    time = now

    # Warn people that you manage the topic
    def doTopic(self, irc, msg):
        c = msg.args[0]
        if not self.registryValue('doTopic', c):
            return
        url = self.registryValue('url', c)
        irc.reply("The topic of %s is managed by me and filled with the contents of %s - please don't change manually" % 
                  (msg.args[0],url), private=True)
Class = Webcal

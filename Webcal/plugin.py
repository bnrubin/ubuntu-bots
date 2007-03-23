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
reload(ical)

def _event_to_string(event, timezone):
    if not timezone:
        return "%s UTC: %s" % (event.startDate.strftime("%d %b %H:%M"), event.summary)
    return "%s: %s" % (event.startDate.astimezone(pytz.timezone(timezone)).strftime("%d %b %H:%M"), event.summary)

def diff(delta):
    s = ''
    if delta.days:
        if delta.days != 1:
            s = 's'
        return '%d day%s' % (delta.days, s)
    h = ''
    if delta.seconds > 7200:
        s = 's'
    if delta.seconds > 3600:
        h = '%d hour%s ' % (int(delta.seconds/3600),s)
    s = ''
    minutes = (delta.seconds % 3600) / 60
    if minutes != 1:
        s = 's'
    return '%s%d minute%s' % (h,minutes,s)

class Webcal(callbacks.Plugin):
    """@schedule <timezone>: display the schedule in your timezone"""
    threaded = True

    def __init__(self, irc):
        callbacks.Privmsg.__init__(self, irc)
        self.irc = irc
        schedule.addPeriodicEvent(self._refresh_cache,  60 * 20, name=self.name())
        schedule.addPeriodicEvent(self._autotopics,     60, name=self.name() + 'b')
        self.cache = {}
        self.subs = shelve.open('/home/dennis/ubugtu/data/subscriptions.db')

    def die(self):
        schedule.removeEvent(self.name())
        schedule.removeEvent(self.name() + 'b')
        self.cache.clear()
        self.subs.close()

    def reset(self):
        self.cache.clear()

    def _filter(self, event, channel, now):
        fword = self.registryValue('filter', channel)
        if fword.lower() not in event.raw_data.lower():
            return False
        delta = event.endDate - now
        return delta.days >= 0 or (delta.days == -1 and abs(delta).seconds < 30 * 60)
        
    def _gettopic(self, url, channel, timezone=None, no_topic=False, num_events=6):
        if url not in self.cache.keys():
            self._refresh_cache(url)
        now = datetime.datetime.now(pytz.UTC)
        events = filter(lambda x: self._filter(x,channel,now),self.cache[url])[:num_events]
        preamble = ''
        if len(events):
            # The standard slack of 30 minutes after the meeting will be an
            # error if there are 2 conscutive meetings, so remove the first 
            # one in that case
            if len(events) > 1 and events[1].startDate < now:
                    events = events[1:]
            ev0 = events[0]
            delta = abs(ev0.startDate - now)
            if ev0.startDate < now or (delta.days == 0 and delta.seconds < 10 * 60):
                preamble = 'Current meeting: %s' % ev0.summary.replace('Meeting','').strip()
                if num_events == 1:
                    return preamble
                events = events[1:]
                preamble += ' | '
        # n_e = 1 -> next meeting
        # n_t = T -> n_t
        if num_events == 1:
            if not events:
                return "No meetings scheduled"
            return 'Next meeting: %s in %s' % (events[0].summary.replace('Meeting','').strip(), diff(delta))
        events = map(lambda x: _event_to_string(x,timezone), events)
        newtopic = ' | '.join(events).replace(' Meeting','')
        template = self.registryValue('topic', channel)
        if '%s' in template and not no_topic:
            newtopic = template % str(newtopic)
        return preamble + newtopic

    def _meeting_in_progress(self, url, channel):
        return False
        if url not in self.cache.keys():
            self._refresh_cache(url)
        now = datetime.datetime.now(pytz.UTC)
        events = filter(lambda x: self._filter(x,channel,now),self.cache[url])[:1]
        if len(events):
            if len(events) and events[0].endDate < now:
                    events = events[1:]
            if not events:
                return False
            ev0 = events[0]
            print now, ev0.startDate, ev0.endDate
            delta = abs(ev0.startDate - now)
            if ev0.startDate < now and delta.seconds > 10 * 5:
                return True
        return False
        
    def _autotopics(self):
        for c in self.irc.state.channels:
            url = self.registryValue('url', c)
            if self._meeting_in_progress(url, c):
                continue
            if url and self.registryValue('doTopic', c):
                newtopic = self._gettopic(url, c)
                if newtopic and not (newtopic.strip() == self.irc.state.getTopic(c).strip()):
                    self.irc.queueMsg(ircmsgs.topic(c, newtopic))

    def _refresh_cache(self,url=None):
        if url:
            data = utils.web.getUrl(url)
            parser = ical.ICalReader(data)
            self.cache[url] = parser.events
        else:
            for c in self.irc.state.channels:
                url = self.registryValue('url', c)
                if url:
                    data = utils.web.getUrl(url)
                    parser = ical.ICalReader(data)
                    self.cache[url] = parser.events

    def topic(self, irc, msg, args):
        url = self.registryValue('url', msg.args[0])
        if not url or not self.registryValue('doTopic',channel=msg.args[0]):
            return
        self._refresh_cache(url)
        if self._meeting_in_progress(url, msg.args[0]):
            irc.error("Can't update topic while a meeting is in progress")
            return
        newtopic = self._gettopic(url, msg.args[0])
        # Only change topic if it actually is different!
        if not (newtopic.strip() == irc.state.getTopic(msg.args[0]).strip()):
            irc.queueMsg(ircmsgs.topic(msg.args[0], newtopic))
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
        if not tzs or 'gmt' in tz.lower():
            irc.error('Unknown timezone: %s - Full list: http://bugbot.ubuntulinux.nl/timezones.html' % tz)
        else:
            if self._meeting_in_progress(url, c):
                irc.error('Please don\'t use @schedule during a meeting')
                irc.reply('Schedule for %s: %s' % (tzs[0],self._gettopic(url, c, timezone=tzs[0], no_topic=True)), private=True)
            else:
                irc.reply('Schedule for %s: %s' % (tzs[0],self._gettopic(url, c, timezone=tzs[0], no_topic=True)))
    schedule = wrap(schedule, [additional('text')])

    def now(self, irc, msg, args, tz):
        """ Display the current time """
        now = datetime.datetime.now(pytz.UTC)
        if not tz:
            tz = 'utc'
        tzs = filter(lambda x: self._tzfilter(x.lower(),tz.lower()), pytz.all_timezones)
        if not tzs or 'gmt' in tz.lower():
            irc.error('Unknown timezone: %s - Full list: http://bugbot.ubuntulinux.nl/timezones.html' % tz)
        else:
            if irc.isChannel(msg.args[0]):
                c = msg.args[0]
            else:
                c = self.registryValue('defaultChannel')
                if not c:
                    return
            meeting = ''
            url = self.registryValue('url', c)
            if url:
                meeting = self._gettopic(url, c, timezone=tzs[0], no_topic = True, num_events = 1)
                if meeting:
                    meeting = ' - ' + meeting
            irc.reply('Current time in %s: %s%s' % (tzs[0], 
                      now.astimezone(pytz.timezone(tzs[0])).strftime("%B %d %Y, %H:%M:%S"),meeting))
    now = wrap(now, [additional('text')])
    time = now

    def subscribe(self, irc, msg, args, regex):
        try:
            rx = re.compile(regex)
        except:
            irc.error("Invalid reguar expression")
            return
        self.subs[msg.nick.lower()] = (regex, rx)
        self.subs.sync()
        irc.reply("Subscription succesful")
    subscribe = wrap(subscribe, ['text'])
    
    def subscription(self, irc, msg, args):
        n = msg.nick.lower()
        if n in self.subs:
            irc.reply("Your subscription: %s" % self.subs[n][0])
        else:
            irc.reply("You haven't subscribed yet")
    subscription = wrap(subscription)

    # Warn people that you manage the topic
    def doTopic(self, irc, msg):
        if not self.registryValue('doTopic'):
            return
        irc.reply("The topic of %s is managed by me and filled with the contents of %s - please don't change manually" % (msg.args[0],url), private=True)

Class = Webcal

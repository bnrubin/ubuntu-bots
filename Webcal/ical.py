#!/usr/bin/env python
import sys, os
sys.path.append(os.path.dirname(__file__))
from icalendar import Calendar, cal, prop
from dateutil import tz as tzmod
from cStringIO import StringIO
import pytz
import urllib2
import datetime
import rruler

DEB_OBJ = None

SECONDS_PER_DAY=24*60*60
def seconds(timediff):
    return SECONDS_PER_DAY * timediff.days + timediff.seconds

def toTz(date, tz):
    assert isinstance(tz, datetime.tzinfo), "tz must be a tzinfo type"
    if isinstance(date, datetime.datetime):
        try:
            return date.astimezone(tz)
        except:
            return datetime.datetime.combine(date.date(), datetime.time(date.time().hour, date.time().minute, date.time().second, tzinfo=tz))
    elif isinstance(datetime.date):
        return datetime.datetime.combine(date, datetime.time(0, 0, 0, tzinfo=tz))

class ICalReader:
    def __init__(self, data):
        self.events = []
        self.timezones = {}
        self.raw_data = data
        self.readEvents()

    def readEvents(self):
        self.events = []
        self.timezones = {}
        parser = Calendar.from_string(self.raw_data)
        tzs = parser.walk("vtimezone")
        self.parseTzs(tzs)
        events = parser.walk("vevent")
        for event in events:
            res = self.parseEvent(event)
            if res:
                self.events.append(res)

    def parseTzs(self, tzs):
        if not tzs:
            return
        for tz in tzs:
            if 'X-LIC-LOCATION' in tz:
                del tz['X-LIC-LOCATION']
        data = ''.join([str(i) for i in tzs])
        data = '\r\n'.join([i for i in data.splitlines() if i.strip()])
        fd = StringIO(data)
        times = tzmod.tzical(fd)
        for tz in times.keys():
            self.timezones[tz] = times.get(tz)

    def parseEvent(self, e):
        for k in ["dtstart", "dtend", "summary"]:
            if not k in e:
                return
        if not isinstance(e['dtstart'].dt, datetime.datetime):
            return
        return ICalEvent.from_event(e, self)
        startDate = endDate = rule = summary = None
        startDate = self.parseDate(e.get("dtstart"))
        endDate = self.parseDate(e.get("dtend"))
        rule = e.get("RRULE")
        summary = e.get("summary")
        if e.get("exdate"):
            event.addExceptionDate(e['EXDATE'].ical()[7:])
        if not startDate or not endDate or not summary: # Bad event
            return

        event = ICalEvent()
        event.raw_data = str(e)
        event.summary = summary
        event.startDate = startDate
        event.endDate = endDate
        if rule:
            event.addRecurrenceRule(rule)
        return event

    def parseDate(self, date):
        if not date:
            return
        tz = pytz.UTC
        if 'tzid' in date.params:
            tz = self.timezones[date.params['tzid']]
        for attr in ['hour', 'minute', 'second']:
            if not hasattr(date.dt, attr):
                return
        return toTz(date.dt, tz)
#        return datetime.datetime(date.dt.year, date.dt.month, date.dt.day, date.dt.hour, date.dt.minute, date.dt.second, tzinfo=tz)

    def selectEvents(self, selectFunction):
        self.events.sort()
        events = filter(selectFunction, self.events)
        return events

    def todaysEvents(self, event):
        return event.startsToday()

    def tomorrowsEvents(self, event):
        return event.startsTomorrow()

    def eventsFor(self, date):
        self.events.sort()
        ret = []
        for event in self.events:
            if event.startsOn(date):
                ret.append(event)
        return re


#class ICalEvent:
#    def __init__(self):
#        self.exceptionDates = []
#        self.dateSet = None
#
#    def __str__(self):
#        return "%s (%s - %s)" % (self.summary, self.startDate, self.endDate)

class ICalEvent(cal.Event):
    def __init__(self, *args, **kwargs):
        self.exceptionDates = []
        self.dateSet = None
        self.__parent = super(ICalEvent, self)
        self.__parent.__init__(self, *args, **kwargs)

    @classmethod
    def from_event(cls, event, parent):
        global DEB_OBJ
        x = cls(**dict(event))
        x.__dict__ = event.__dict__
        x.exceptionDates = []
        x.dateSet = None
        x.summary = x['summary']
        x.timezone = x['dtstart'].dt.tzinfo
        x.startDate = parent.parseDate(x['dtstart'])
        x.endDate = parent.parseDate(x['dtend'])
        if not x.timezone:
            x.timezone = pytz.UTC
            x.startDate = parent.parseDate(x['dtstart'])
            x.endDate = parent.parseDate(x['dtend'])
        x.raw_data = str(x)
        if 'rrule' in event:
            x.addRecurrenceRule(event['rrule'])
        if x.summary == "Server Team Meeting":
            DEB_OBJ = x
        return x

    def __str__(self):
        return "%s (%s - %s)" % (self.summary, self.startDate, self.endDate)

    def __eq__(self, otherEvent):
        return self.startTime() == otherEvent.startTime()

    def __lt__(self, otherEvent):
        return self.startTime() < otherEvent.startTime()

    def __gt__(self, otherEvent):
        return self.startTime() > otherEvent.startTime()

    def __ge__(self, otherEvent):
        return self.startTime() >= otherEvent.startTime()

    def __le__(self, otherEvent):
        return self.startTime() <= otherEvent.startTime()

    def addExceptionDate(self, date):
        self.exceptionDates.append(date)

    def addRecurrenceRule(self, rule):
        self.dateSet = DateSet(self.startDate, self.endDate, rule)

    def startsToday(self):
        return self.startsOn(datetime.datetime.today())

    def startsTomorrow(self):
        tomorrow = datetime.datetime.today() + datetime.timedelta(1)
#        tomorrow = datetime.datetime.fromtimestamp(time.time() + SECONDS_PER_DAY)
        return self.startsOn(tomorrow)

    def startsOn(self, date):
        return (self.startDate.year == date.year and
                self.startDate.month == date.month and
                self.startDate.day == date.day or
                (self.dateSet and self.dateSet.includes(date)))

    def startTime(self):
        now = datetime.datetime.now(pytz.UTC)
        if self.dateSet and self.startDate < now:
            dates = self.dateSet.getRecurrence()
            for date in dates:
                if date.date() >= now.date():
                    if date.date() > now.date() or (date.date() == now.date and date.astimezone(pytz.UTC).time() >= now.time()):
                        return toTz(datetime.datetime.combine(date,self.startDate.time()), self.startDate.tzinfo)
        return self.startDate

    def endTime(self):
        now = datetime.datetime.now(pytz.UTC).date()
        if self.dateSet and self.endDate.date() < now:
            return toTz(datetime.datetime.combine(self.startTime().date(), self.endDate.time()), self.startDate.tzinfo)
        return self.endDate

    def schedule(self, timezone=None):
        if not timezone:
            return "%s UTC: %s" % (self.startTime().astimezone(pytz.UTC).strftime("%d %b %H:%M"), self.summary.replace('Meeting','').strip())
        if isinstance(timezone, basestring):
            return "%s: %s" % (self.startTime().astimezone(pytz.timezone(timezone)).strftime("%d %b %H:%M"), self.summary.replace('Meeting','').strip())
        return "%s: %s" % (self.startTime().astimezone(timezone).strftime("%d %b %H:%M"), self.summary.replace('Meeting','').strip())

    def is_on(self):
        now = datetime.datetime.now(pytz.UTC)
        return self.startTime() >= now and self.endTime() < now

    def has_passed(self):
        if self.dateSet:
            return toTz(datetime.datetime.combine(self.startTime().date(), self.endDate.time()), self.startDate.tzinfo) < datetime.datetime.now(pytz.UTC)
        return self.endDate < datetime.datetime.now(pytz.UTC)

    def seconds_to_go(self):
        return seconds(self.startTime() - datetime.datetime.now(pytz.UTC))

    def seconds_ago(self):
        return seconds(datetime.datetime.now(pytz.UTC) - self.endTime())

    def time_to_go(self):
        if self.endTime() < datetime.datetime.now(pytz.UTC):
            return False
        delta = self.startTime() - datetime.datetime.now(pytz.UTC)
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

class DateSet:
    def __init__(self, startDate, endDate, rule):
        self.startDate = startDate
        self.endDate = endDate
        self.frequency = None
        self.count = None
        self.untilDate = None
        self.byMonth = None
        self.byDate = None
        self.dates = None
        self.parseRecurrenceRule(rule)

    def parseRecurrenceRule(self, rule):
        freq = rruler.rrule_map[rule.pop('freq')[0]]
        now = datetime.datetime.now(self.startDate.tzinfo)
        rule['dtstart'] = now
        rule['until'] = now + datetime.timedelta(60)
        self.recurrence = rruler.rrule_wrapper(freq, **rule)

    def getRecurrence(self):
        if not self.dates:
            self.dates = []
            for x in list(self.recurrence):
                self.dates.append(toTz(x, self.startDate.tzinfo))
            self.dates.append(self.startDate)
        return self.dates

    def includes(self, date):
        if isinstance(date, datetime.datetime):
            date = date.date()
        return date in [x.date() for x in self.getRecurrence()]

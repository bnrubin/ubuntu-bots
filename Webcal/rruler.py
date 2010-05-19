#!/usr/bin/env python
from dateutil import rrule
import re, datetime

#wk_days = ('MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU')
wk_days = re.compile("([0-9]?)([M|T|W|F|S][O|U|E|H|R|A])")

rrule_map = {
'SECONDLY': rrule.SECONDLY,
'MINUTELY': rrule.MINUTELY,
'HOURLY': rrule.HOURLY,
'DAILY': rrule.DAILY,
'WEEKLY': rrule.WEEKLY,
'MONTHLY': rrule.MONTHLY,
'YEARLY': rrule.YEARLY,
'MO': rrule.MO,
'TU': rrule.TU,
'WE': rrule.WE,
'TH': rrule.TH,
'FR': rrule.FR,
'SA': rrule.SA,
'SU': rrule.SU }

def rrule_wrapper(*args, **kwargs):
    for k, v in kwargs.iteritems():
        if k == 'byday' or k == 'BYDAY':
            del kwargs[k]
            groups = wk_days.match(v[0]).groups()
            if groups[0]:
                kwargs['byweekday'] = rrule_map[groups[1]](int(groups[0]))
            else:
                kwargs['byweekday'] = rrule_map[groups[1]]
            
        else:
            del kwargs[k]
            k = k.lower()
            if isinstance(v, list):
                if len(v) > 1:
                    res = []
                    for x in v:
                        if isinstance(x, basestring) and wk_days.match(x):
                            res.append(rrule_map[wk_days.match(x).group(1)])
                        elif v in rrule_map:
                            res.append(rrule_map[x])
                        elif isinstance(x, datetime.datetime):
                            res.append(datetime.datetime.fromordinal(x.toordinal()))
                        else:
                            res.append(v)
                    kwargs[k] = tuple(res)
                else:
                    if isinstance(v[0], basestring) and wk_days.match(v[0]):
                        kwargs[k] = rrule_map[wk_days.match(v[0]).group(0)]
                    elif v[0] in rrule_map:
                        kwargs[k] = rrule_map[v[0]]
                    elif isinstance(v[0], datetime.datetime):
                        kwargs[k] = datetime.datetime.fromordinal(v[0].toordinal())
                    else:
                        kwargs[k] = v[0]
            else:
                kwargs[k] = v
    return rrule.rrule(*args, **kwargs)

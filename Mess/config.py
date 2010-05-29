# -*- Encoding: utf-8 -*-
###
# Copyright (c) 2006-2007 Dennis Kaarsemaker
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

import supybot.conf as conf
import supybot.registry as registry

def configure(advanced):
    from supybot.questions import expect, something, yn, output

    def anything(prompt, default=None):
        """Because supybot is pure fail"""
        from supybot.questions import expect
        return expect(prompt, [], default=default)

    Mess = conf.registerPlugin('Mess', True)

    def getDelay():
        output("What should be the minimum number of seconds between mess output?")
        delay = something("Enter an integer greater or equal to 0", default=Mess.delay._default)

        try:
            delay = int(delay)
            if delay < 0:
                raise TypeError
        except TypeError:
            output("%r is not a valid value, it must be an interger greater or equal to 0" % delay)
            return getDelay()
        else:
            return delay

    output("WARNING: This plugin is unmaintained, may have bugs and is potentially offensive to users")
    Mess.enabled.setValue(yn("Enable this plugin for all channels?", default=Mess.enabled._default))
    Mess.offensive.setValue(yn("Enable possibly offensive content?", default=Mess.offensive._default))
    Mess.delay.setValue(getDelay())

Mess = conf.registerPlugin('Mess')
conf.registerChannelValue(conf.supybot.plugins.Mess, 'enabled',
    registry.Boolean(False,"""Enable the non-offensive mess that the bot can spit out in the
    channel"""))
conf.registerChannelValue(conf.supybot.plugins.Mess, 'offensive',
    registry.Boolean(False,"""Enable all possibly offensive mess that the bot can spit out in the
    channel"""))
conf.registerChannelValue(conf.supybot.plugins.Mess, 'delay',
    registry.Integer(10,""" Minimum number of seconds between mess """))

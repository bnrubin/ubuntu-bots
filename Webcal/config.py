# -*- Encoding: utf-8 -*-
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

import supybot.conf as conf
import supybot.registry as registry

def configure(advanced):
    from supybot.questions import expect, something, yn, output

    def anything(prompt, default=None):
        """Because supybot is pure fail"""
        from supybot.questions import expect
        return expect(prompt, [], default=default)

    Webcal = conf.registerPlugin('Webcal', True)

    output("Every option, except for the default channel and URL to a list of time zones, is channel-specific.")
    output("The values you enter here will be the defaults unless overridden by a channel-specific value")
    doTopic = yn("Manage the topic for all channels?", default=Webcal.doTopic._default)
    url = anything("What is the default URL to the iCal feed, for all channels?", default=Webcal.url._default)
    defaultChannel = anything("What channel should be default when none is given?", default=Webcal.defaultChannel._default)
    tzUrl = anything("What is the URL to the list of available time zonez?", default=Webcal.tzUrl._default)

    if advanced:
        filter = anything("What should the filter be for the iCal feed, for all channels?", default=Webcal.filter._default)
        topic = anything("What template should be used for the topic, for all channels", default=Webcal.topic._default)
    else:
        filter = Webcal.filter._default
        topic = Webcal.topic._default

    Webcal.doTopic.setValue(doTopic)
    Webcal.url.setValue(url)
    Webcal.defaultChannel.setValue(defaultChannel)
    Webcal.tzUrl.setValue(tzUrl)
    Webcal.filter.setValue(filter)
    Webcal.topic.setValue(topic)

Webcal = conf.registerPlugin('Webcal')
conf.registerChannelValue(conf.supybot.plugins.Webcal, 'url',
    registry.String('',"""Webcal URL for the channel"""))
conf.registerChannelValue(conf.supybot.plugins.Webcal, 'filter',
    registry.String('',"""What to filter on in the ical feed"""))
conf.registerChannelValue(conf.supybot.plugins.Webcal, 'topic',
    registry.String('',"""Topic template"""))
conf.registerChannelValue(conf.supybot.plugins.Webcal, 'doTopic',
    registry.Boolean(False,"""Whether to manage the topic"""))
conf.registerGlobalValue(conf.supybot.plugins.Webcal, 'defaultChannel',
    registry.String('',"""Default channel to determine schedule for /msg replies"""))
conf.registerGlobalValue(conf.supybot.plugins.Webcal, 'tzUrl',
    registry.String('http://ubottu.com/timezones.html', """URL to the list of timezones supported by the Webcal plugin"""))

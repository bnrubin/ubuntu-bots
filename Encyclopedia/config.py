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
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('Encyclopedia', True)

Encyclopedia = conf.registerPlugin('Encyclopedia')
conf.registerChannelValue(Encyclopedia, 'database',
    registry.String('ubuntu', 'Name of database to use'))
conf.registerChannelValue(Encyclopedia, 'relaychannel',
    registry.String('#ubuntu-ops', 'Relay channel for unauthorized edits'))
conf.registerGlobalValue(Encyclopedia, 'notfoundmsg',
    registry.String('Factoid %s not found', 'Reply when factoid isn\'t found'))
conf.registerChannelValue(Encyclopedia,'prefixchar',
    registry.String('!','Prefix character for factoid display/editing'))
conf.registerGlobalValue(Encyclopedia, 'datadir',
    registry.String("", 'Path to dir containing factoid databases', private=True))
conf.registerChannelValue(Encyclopedia, 'alert',
    registry.SpaceSeparatedListOfStrings(['ops', 'op', 'kops', 'calltheops'], 'factoid name(s) used for alerts', private=True))
conf.registerChannelValue(Encyclopedia, 'remotedb',
    registry.String('http://ubottu.com/ubuntu.db', 'Remote location of the master database', private=True))
conf.registerChannelValue(Encyclopedia, 'ignores',
    registry.SpaceSeparatedListOfStrings(['find', 'info'], 'factoid name(s) to ignore', private=True))
conf.registerChannelValue(Encyclopedia, 'privateNotFound',
    registry.Boolean(False, "If set to True, send notfoundmsg in private rather than in the channel"))


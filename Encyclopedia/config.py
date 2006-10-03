###
# Copyright (c) 2006, Dennis Kaarsemaker
# All rights reserved.
#
#
###

import supybot.conf as conf
import supybot.registry as registry

def configure(advanced):
    # This will be called by supybot to configure this module.  advanced is
    # a bool that specifies whether the user identified himself as an advanced
    # user or not.  You should effect your configuration by manipulating the
    # registry as appropriate.
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('Encyclopedia', True)


Encyclopedia = conf.registerPlugin('Encyclopedia')
# This is where your configuration variables (if any) should go.  For example:
# conf.registerGlobalValue(Factoid, 'someConfigVariableName',
#     registry.Boolean(False, """Help for someConfigVariableName."""))
conf.registerChannelValue(Encyclopedia, 'database',
    registry.String('', 'Name of database to use'))
conf.registerGlobalValue(Encyclopedia, 'packagelookup',
    registry.Boolean(True, "Whether to look up packages"))
conf.registerChannelValue(Encyclopedia, 'fallbackdb',
    registry.String('ubuntu', 'Fallback database'))
conf.registerGlobalValue(Encyclopedia, 'fallbackchannel',
    registry.String('#ubuntu', 'Fallback channel'))
conf.registerGlobalValue(Encyclopedia, 'relaychannel',
    registry.String('#ubuntu-ops', 'Relay channel for unauthorized edits'))
conf.registerGlobalValue(Encyclopedia, 'notfoundmsg',
    registry.String('Factoid %s not found', 'Reply when factoid isn\'t found'))


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:

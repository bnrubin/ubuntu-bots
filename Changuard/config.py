import supybot.conf as conf
import supybot.registry as registry

def configure(advanced):
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('Changuard', True)

Changuard = conf.registerPlugin('Changuard')
conf.registerChannelValue(conf.supybot.plugins.Changuard, 'enabled',
    registry.Boolean(False,"""Enable the guard plugin"""))

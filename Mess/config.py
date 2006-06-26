import supybot.conf as conf
import supybot.registry as registry

def configure(advanced):
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('Mess', True)

Mess = conf.registerPlugin('Mess')
conf.registerChannelValue(conf.supybot.plugins.Mess, 'enabled',
    registry.Boolean(False,"""Enable all mess that Ubugtu can spit out in the
    channel"""))
conf.registerChannelValue(conf.supybot.plugins.Mess, 'offensive',
    registry.Boolean(False,"""Enable all possibly offensive mess that Ubugtu can spit out in the
    channel"""))
conf.registerChannelValue(conf.supybot.plugins.Mess, 'delay',
    registry.Integer(10,""" Minimum number of seconds between mess """))

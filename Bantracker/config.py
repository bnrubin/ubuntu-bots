import supybot.conf as conf
import supybot.registry as registry

def configure(advanced):
    conf.registerPlugin('Bantracker', True)

Bantracker = conf.registerPlugin('Bantracker')
conf.registerChannelValue(conf.supybot.plugins.BanTracker, 'enabled',
        registry.Boolean(False, """Enable the bantracker"""))

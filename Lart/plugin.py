# -*- Encoding: utf-8 -*-
###
# Copyright (c) 2005, Daniel DiPaolo
#           (c) 2006, Dennis Kaarsemaker
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

import re

from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.ircdb as ircdb
import supybot.conf as conf
import random

def checkIgnored(hostmask, recipient='', users=ircdb.users, channels=ircdb.channels):
    if ircdb.ignores.checkIgnored(hostmask):
        return True
    try:
        id = ircdb.users.getUserId(hostmask)
        user = users.getUser(id)
    except KeyError:
        # If there's no user...
        if ircutils.isChannel(recipient):
            channel = channels.getChannel(recipient)
            if channel.checkIgnored(hostmask):
                return True
            else:
                return False
        else:
            return False
    if user._checkCapability('owner'):
        # Owners shouldn't ever be ignored.
        return False
    elif user.ignore:
        return True
    elif recipient:
        if ircutils.isChannel(recipient):
            channel = ircdb.channels.getChannel(recipient)
            if channel.checkIgnored(hostmask):
                return True
            else:
                return False
        else:
            return False
    else:
        return False

class Lart(plugins.ChannelIdDatabasePlugin):
    _meRe = re.compile(r'\bme\b', re.I)
    _myRe = re.compile(r'\bmy\b', re.I)
    def _replaceFirstPerson(self, s, nick):
        s = self._meRe.sub(nick, s)
        s = self._myRe.sub('%s\'s' % nick, s)
        return s

    def addValidator(self, irc, text):
        if '$who' not in text:
            irc.error('Larts must contain $who.', Raise=True)

    def lart(self, irc, msg, args, channel, id, text):
        """[<channel>] [<id>] <who|what> [for <reason>]

        Uses the Luser Attitude Readjustment Tool on <who|what> (for <reason>,
        if given).  If <id> is given, uses that specific lart.  <channel> is
        only necessary if the message isn't sent in the channel itself.
        """
        if not self.registryValue('enabled', msg.args[0]):
            return
        if ' for ' in text:
            (target, reason) = map(str.strip, text.split(' for ', 1))
        else:
            (target, reason) = (text, '')

        if id is not None:
            try:
                lart = self.db.get(channel, id)
            except KeyError:
                irc.error(format('There is no lart with id #%i.', id))
                return
        else:
            lart = self.db.random(channel)
            if not lart:
                irc.error(format('There are no larts in my database '
                                 'for %s.', channel))
                return
        text = self._replaceFirstPerson(lart.text, msg.nick)
        formatText = ircutils.stripFormatting(target).lower()
        if (ircutils.strEqual(target, irc.nick) or 'Evilrockbot' in formatText) and random.uniform(0,100) < 25:
            target = msg.nick
            reason = ''
        elif 'stdin' in formatText or 'tsimpson' in formatText:
            target = msg.nick
            reason = ''
        else:
            target = self._replaceFirstPerson(target, msg.nick)
            reason = self._replaceFirstPerson(reason, msg.nick)
        if target.endswith('.'):
            target = target.rstrip('.')
        text = text.replace('$who', target)
        text = text.replace('$chan', msg.args[0])
        if reason:
            text += ' for ' + reason
        if self.registryValue('showIds', channel):
            text += format(' (#%i)', lart.id)
        irc.reply(text, action=True)
    lart = wrap(lart, ['channeldb', optional('id'), 'text'])
    pity = lart

    def callPrecedence(self, irc):
        before = []
        for cb in irc.callbacks:
            if cb.name() == 'IRCLogin':
                before.append(cb)
        return (before, [])

    def inFilter(self, irc, msg):
        if not msg.command == 'PRIVMSG':
            return msg
        if not conf.supybot.defaultIgnore():
            return msg
        s = callbacks.addressed(irc.nick, msg)
        if not s:
            return msg
        if checkIgnored(msg.prefix):
            return msg
        try:
            if ircdb.users.getUser(msg.prefix):
                return msg
        except:
            pass
        cmd, args = (s.split(None, 1) + [None])[:2]
        if cmd and cmd[0] in str(conf.supybot.reply.whenAddressedBy.chars.get(msg.args[0])):
            cmd = cmd[1:]
        if cmd in self.listCommands():
            tokens = callbacks.tokenize(s, channel=msg.args[0])
            self.Proxy(irc, msg, tokens)
        return msg

Class = Lart

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:

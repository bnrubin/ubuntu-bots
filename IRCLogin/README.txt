Allows any nickserv-identified user to login without password.
Grabs IRC nicks from the members in the ubuntu-irc Launchpad team, these are
stored in a binary file.

It is recommended to run @updateusers manually when the plugin is first loaded
to grab the users list from launchpad.

This plugin is designed to work with the bantracker plugin, so adds the
'bantracker' capability to all the users it finds in the team.

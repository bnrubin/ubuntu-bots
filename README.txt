This directory contains the supybot plugins that allow you to create a clone of
ubottu for your channels.
This file contains some basic set-up information that will be useful when
setting up an ubottu clone for the first time.

These plugins are designed to work with Python 2.5 and Python 2.6, they are
untested and unsupported on Python 3.0. The recommended way to set-up these
plugins is to first create a directory for the bot, then move this directory to
there and rename it to "plugins". Alternatively you can create an empty plugins
directory and create links to each separate plugin directory inside there.
After that you should make sure you have the following installed on the system:

Name            Debian/Ubuntu package       Website
Python-apt      python-apt                  N/A Debian (and derivatives) only
PySQLite        python-sqlite               http://ubottu.com/python-sqlite/
pytz            python-tz                   http://pypi.python.org/pypi/pytz/
SOAPpy          python-soappy               http://soapy.sourceforge.net/

(Optional)
Launchpadlib    python-launchpadlib         https://launchpad.net/launchpadlib
apt-file        apt-file                    N/A Debian (and derivatives) only

Launchpadlib will become a required module for Bugtracker (and possibly others)

Once these packages are installed, and in the bot directory containing the
"plugins" sub-directory, run this command: "supybot-wizard".
This wizard will guide you through the process of setting up the bot for an IRC
network. You should use the default answers when unsure.
When the wizard asks "Would you like to look at plugins individually?" answer
"y", there you will be presented with a list of plugins to choose. The ones
from ubuntu-bots are:

Name            Description
Bantracker      Helps to track bans/kicks/quiets/removes in channels
Bugtracker      Show information on bugs for various bug trackers.
Encyclopedia    A factoid encyclopaedia.
IRCLogin        Allows password-less login from users identified to services.
Lart            A database of "larts". (Unmaintained)
Mess            Random mess, pulls random things from the internet. (Unmaintained)
PackageInfo     Lookup information on Debian packages and file search.
(works on Debian and derivatives only, unless you take special measures)
Webcal          Updates a channel topic based on events in an iCal. (Unmaintained)

Note: Mess and Lart are largely unmaintained but are working, Webcal is
unmaintained and mostly broken except for extremely simple iCal feeds.

If you chose to enable Bantracker or Encyclopedia, initial databases will be
created in the "data" directory. These are named "bans.db" for the Bantracker
plugin and "ubuntu.db" for the Encyclopedia plugin. You can obtain the same
database that ubottu uses by overwriting the "ubuntu.db" file with the one
located at http://ubottu.com/ubuntu.db or by running the "@sync" command with
the bot in IRC.
The Bantracker database from ubottu is not available to the
public, as it will contain logs of channels which are not publically logged.

If you enabled the PackageInfo plugin several .list files will be created in
"data/aptdir/", these will be used with the "apt-cache" and "apt-file" commands
to retrieve package information and find files within packages.
When asked if you want to run the "update_apt" script you should
answer "y" to download the package information, this will take a while
depending on the speed of your connection and proximity to the default servers.
The same is true for the "update_apt_file" script, which will only be ran if
"apt-file" is installed. You should then edit the two scripts replacing the path
in "DIR=/home/bot/aptdir" with the path to your aptdir, which should be under
"data/aptdir" in your bots directory. You can then set up a cron job that will
run the two scripts daily, weekly or monthly. These scripts should be ran as
the user the bot is run as.

Once you have selected the plugins you want to enable, you will be asked "Would
you like to set the prefix char(s) for your bot?", you should answer "y" and
set it to anything other than the prefix character for Encyclopedia and
PacakgeInfo. If you weren't asked, it defaults to '!' for those plugins. The
recommended character to use is '@'. Do not set the prefix chacter for commands
and for the plugins to the same value, you will run into trouble.


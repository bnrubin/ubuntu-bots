Factoid plugin
Note: This plugin used to have package lookup, this was mooved to the
PackageInfo plugin.

Pick a name for your database. A lowercase-only name without spaces is probably
best, this example wil use myfactoids as name. Then create a directory to store
your databases in (somewere in $botdir/data would be best).
If you choose to enable this plugin during supybot-wizard the database will be
created for you. If noy, you can create the database manually.
In the new directory create an SQLite2 database with the following command:

sqlite myfactoids.db
Then copy/paste in the below 2 tables:

CREATE TABLE facts (
        id INTEGER PRIMARY KEY,
        author VARCHAR(100) NOT NULL,
        name VARCHAR(20) NOT NULL,
        added DATETIME,
        value VARCHAR(200) NOT NULL,    
        popularity INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE log (
        id INTEGER PRIMARY KEY,
        author VARCHAR(100) NOT NULL,
        name VARCHAR(20) NOT NULL,
        added DATETIME,
        oldvalue VARCHAR(200) NOT NULL
);


If you want to create more databases, repeat these last two steps.

When the databases exist, you need to configure the bots to actually use them.
To do that, set the global value supybot.plugins.encyclopedia.datadir to the new
dirand the channel value supybot.plugins.encyclopedia.database to the name of
the database (without the .db suffix).

Documentation on adding/editing factoids can be found on
https://ubottu.com/devel/wiki/Plugins#Encyclopedia
To give people edit access, let them register with your bot and use the command:
@addeditor nickname_here
(replace @ with your prefix char). Similarly you can use removeeditor :).

The web interface is a simple cgi script with some templates, css and the
commoncgi.py file from the bzr tree. Make sure you set the variables datadir and
database in factoids.cgi to the correct values. Also set default_db to the one
you want to show by default.

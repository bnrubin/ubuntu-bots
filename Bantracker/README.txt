This plugin can store all bans/kicks etc in an sqlite database. It includes a
cgi script to view bans/kicks and comment on them. To view/user the bantracker
web interface a user must use the @btlogin command from the bot. They must also
have the 'bantracker' capability.
You can use the @mark <nick|hostmask> [<channel>] [<comment>]
command to manually add an entry to the bantracker without having to actially
kick/ban someone.

The schema of the SQLite2 database:

CREATE TABLE bans (
    id INTEGER PRIMARY KEY,
    channel VARCHAR(30) NOT NULL,
    mask VARCHAR(100) NOT NULL,
    operator VARCHAR(30) NOT NULL,
    time VARCHAR(300) NOT NULL,
    removal DATETIME,
    removal_op VARCHAR(30),
    log TEXT
);
CREATE TABLE comments (
    ban_id INTEGER,
    who VARCHAR(100) NOT NULL,
    comment MEDIUMTEXT NOT NULL,
    time VARCHAR(300) NOT NULL
);
CREATE TABLE sessions (
    session_id VARCHAR(50) PRIMARY KEY,
    user MEDIUMTEXT NOT NULL,
    time INT NOT NULL
);
CREATE INDEX comments_ban_id ON comments(ban_id);

To configure the plugin, create the SQLite2 database with above structure and
set supybot.plugins.bantracker.database to its filename. Then enable it, either
per-channel or globally, by setting the channel variable:
supybot.plugins.bantracker.enabled
You can create the database by using the "sqlite" command-line tool by passing
the file name and then copy/paste the above table schema. Then type ".quit" to
save and exit.
If you choose to enable this plugin during the initial setup (with the command
supybot-wizard), then the database will be created automatically for you.

If you wish to use the web interface, it also uses commoncgi.py which should be
on your sys.path (or as you can see in cgt/bans.cgi, sys.path is modified to
include the dir of commoncgi.py).
You should place the contents of the cgi/ directory somewhere accessible by
your web server, and modify the CONFIG_FILENAME variable near the top of the
script to point to the location of your bantracker.conf.
Then modify the bantracker.conf file to reflect the proper values for your
setup.

The meanings of the entries in bantracker.conf are:
Key                 Type    Description
anonymous_access    Boolean True if annonmous access is allowed, otherwise
                            False.
database            String  The full path to the SQLite bantracker database.
results_per_page    Number  The maximum number of results that should be shown
                            per page.
plugin_path         String  The full path to the directory that contains the
                            commoncgi.py file.
irc_network         String
                            The DNS name of the IRC network anonymous users are
                            directed to when anonymous access is disabled.
irc_channel         String  The channel name anonymous users are directed to
                            when anonmous access is disabled.


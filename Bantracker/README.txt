This plugin can store all bans/kicks etc in an sqlite database. It includes a
cgi script to view bans/kicks and comment on them. To view/user the bantracker
web interface a user must use the @btlogin command from the bot. They must also
have the 'bantracker' capability.
You can use the @mark <nick|hostmask> [<channel>] [<comment>]
command to manually add an entry to the bantracker without having to actially
kick/ban someone.

It also uses commoncgi.py which should be on your sys.path (or as you can see in
the script, sys.path is modified to include the dir of commoncgi.py)

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
the file name and then copy/paste the above table schema.
If you choose to enable this plugin during the initial setup (with the command
supybot-wizard), then the database will be created automatically for you.

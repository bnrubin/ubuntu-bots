###
# Copyright (c) 2006-2007 Dennis Kaarsemaker
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
###
import commands, os, apt
from email import FeedParser

def component(arg):
    if '/' in arg: return arg[:arg.find('/')]
    return 'main'

class Apt:
    def __init__(self, plugin):
        self.aptdir = plugin.registryValue('aptdir')
        self.distros = []
        if self.aptdir:
            self.distros = [x[:-5] for x in os.listdir(self.aptdir) if x.endswith('.list')]
            self.aptcommand = """apt-cache\\
                                 -o"Dir::State::Lists=%s/%%s"\\
                                 -o"Dir::etc::sourcelist=%s/%%s.list"\\
                                 -o"Dir::State::status=%s/%%s.status"\\
                                 -o"Dir::Cache=%s/cache"\\
                                 %%s %%s""" % tuple([self.aptdir]*4)
            self.aptfilecommand = """apt-file -s %s/%%s.list -c %s/apt-file/%%s -l -F search %%s""" % tuple([self.aptdir]*2)

    def find(self, pkg, checkdists, filelookup=True):
        _pkg = ''.join([x for x in pkg.strip().split(None,1)[0] if x.isalnum or x in '.-_+'])
        distro = checkdists[0]
        if len(pkg.strip().split()) > 1:
            distro = ''.join([x for x in pkg.strip().split(None,2)[1] if x.isalnum or x in '.-_+'])
        if distro not in self.distros:
            distro = checkdists[0]
        pkg = _pkg

        data = commands.getoutput(self.aptcommand % (distro, distro, distro, 'search -n', pkg))
        if not data:
            if filelookup:
                data = commands.getoutput(self.aptfilecommand % (distro, distro, pkg)).split()
                if data:
                    if len(data) > 5:
                        return "File %s found in %s (and %d others)" % (pkg, ', '.join(data[:5]), len(data)-5)
                    return "File %s found in %s" % (pkg, ', '.join(data))
                return 'Package/file %s does not exist in %s' % (pkg, distro)
            return "No packages matching '%s' could be found" % pkg
        pkgs = [x.split()[0] for x in data.split('\n')]
        if len(pkgs) > 5:
            return"Found: %s (and %d others)" % (', '.join(pkgs[:5]), len(pkgs) -5)
        else:
            return "Found: %s" % ', '.join(pkgs[:5])

    def info(self, pkg, checkdists):
        _pkg = ''.join([x for x in pkg.strip().split(None,1)[0] if x.isalnum() or x in '.-_+'])
        distro = None
        if len(pkg.strip().split()) > 1:
            distro = ''.join([x for x in pkg.strip().split(None,2)[1] if x.isalnum() or x in '-._+'])
        if distro:
            if distro not in self.distros:
                checkdists = [checkdists[0]]
            else:
                checkdists = [distro]
        pkg = _pkg

        for distro in checkdists:
            data = commands.getoutput(self.aptcommand % (distro, distro, distro, 'show', pkg))
            data2 = commands.getoutput(self.aptcommand % (distro, distro, distro, 'showsrc', pkg))
            if not data or 'E: No packages found' in data:
                continue
            maxp = {'Version': '0'}
            packages = [x.strip() for x in data.split('\n\n')]
            for p in packages:
                if not p.strip():
                    continue
                parser = FeedParser.FeedParser()
                parser.feed(p)
                p = parser.close()
                if apt.VersionCompare(maxp['Version'], p['Version']) < 0:
                    maxp = p
                del parser
            maxp2 = {'Version': '0'}
            packages2 = [x.strip() for x in data2.split('\n\n')]
            for p in packages2:
                if not p.strip():
                    continue
                parser = FeedParser.FeedParser()
                parser.feed(p)
                p = parser.close()
                if apt.VersionCompare(maxp2['Version'], p['Version']) < 0:
                    maxp2 = p
                del parser
            archs = ''
            if maxp2['Architecture'] not in ('all','any'):
                archs = ' (Only available for %s)' % maxp2['Architecture']
            return("%s: %s. In component %s, is %s. Version %s (%s), package size %s kB, installed size %s kB%s" %
                   (maxp['Package'], maxp['Description'].split('\n')[0], component(maxp['Section']),
                    maxp['Priority'], maxp['Version'], distro, int(maxp['Size'])/1024, maxp['Installed-Size'], archs))
        return 'Package %s does not exist in %s' % (pkg, ', '.join(checkdists))
                       

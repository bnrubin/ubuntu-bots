#!/usr/bin/python
import sys
sys.path.append('/home/dennis/public_html')
from commoncgi import *

for file in sorted(os.listdir('/home/dennis/public_html/botlogs'),reverse=True)[1:101]:
    print '<a href="/botlogs/%s">%s</a><br/>' % (file, file)

send_page('plain.tmpl')

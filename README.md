# gkctopicbot #

A simplistic Python 2.x irc bot with feedparser and Twisted, which is be
able to

* Change an irc channel topic prompted by a (proboards forum) RSS feed.
* Notify irc channel patrons about new forum posts (again, via RSS feed).
* Get authed with QuakeNet Q
* Parse url titles (with Requests and BeautifulSoup)
* Provide simple entertainment (Hellooo! Awww.) to channel patrons

## usage ##

This being heavily in development, you probably do not want to use this.

However, if you insist:
Create a 'config.yaml' file, see 'config-example.yaml' for syntax.
Run with by executing the script 'bin/gkctopicbot'.

## license ##

If you managed to find *this* terrible thing, you probably could write 
a better irc bot by yourself, too. Do so. 

For completeness, however, I declare this project GNU GPLv3. Search internet 
for terms.

Naturally, other licenses may apply to libraries used (Twisted and feedparser
are both MIT Licensed).


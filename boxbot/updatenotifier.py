# -*- coding: utf-8 -*-

"""
update notifier module

notifies about comic updates
"""

import logging
log = logging.getLogger(__name__)

import datetime

from twisted.internet import task, reactor, threads

# custom
import clock



class Notifier(object):

    """Docstring for Notifier. """
    
    bot = None
    comics = None   # a dictionary of update schedules
    default_comic = None

    def __init__(self, notifyConfig, bot):
        """@todo: to be defined1. """
        self.bot = bot
        self.comics, self.default_comic = self.parseConfig(notifyConfig)
        log.debug("a notifier instance created")

    def parseSchedule(self, schedule):
        return {k: datetime.time(int(l[0]), int(l[1])) for (k, l) in schedule}

    def parseConfig(self, notifyConfig):
        comics = {comic: self.parseSchedule(sch) for (comic, sch) in notifyConfig['comics']}
        return comics, notifyConfig['defaulComic'] 

    def parseMsg(self, msg):
        for k in comics.keys():
            idents = k.split()
            for i in idents:
                # "next update" is the cmdstring to call Notifier
                # get rid of this hardcoded value someday
                if i in msg[len("next update "):]:
                    return k

    def askedNextUpdateWith(self, msg):
        d = thread.deferToThread(self.parseMsg(msg))
        d.addCallback(handleCommand)
        d.addErrback(handleCommandError)

    def handleCommandError(self, e):
        log.info("Asked time until next update but couldn't parse comic name")
        self.bot.announce("Aww, I couldn't parse that!")
        return None
    
    def handleCommand(self, cmd):
        if not cmd:
            log.info("comic name wasn't specified, assuming the default...")
            comic = self.default_comic
        elif cmd not in self.comics:
            log.info("the parsed comic name not recognized...")
            self.bot.announce("Aww, I don't recognize that comic!")
            return None
        else:
            log.debug("comic_name successfully retrieved from msg")
            comic = cmd
        
        d = threads.deferToThread(clock.timeUntilNextUpdate(comics[comic]))
        d.addCallback(lambda e: bot.announce(e))

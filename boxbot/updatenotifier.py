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
        return {k: datetime.time(int(schedule[k][0]), int(schedule[k][1])) 
                for k in schedule}

    def parseConfig(self, notifyConfig):
        comics = {comic: self.parseSchedule(notifyConfig['comics'][comic]) 
                for comic in notifyConfig['comics']}
        return comics, notifyConfig['defaultComic'] 

    def parseMsg(self, msg):
        log.debug("parsing msg %s" % msg)
        for k in self.comics.keys():
            idents = k.split()
            log.debug("idents %s" %idents)
            for i in idents:
                # "next update" is the cmdstring to call Notifier
                # get rid of this hardcoded value someday
                if i in msg[len(self.bot.nickname + "next update ") + 1:]:
                    return k
        log.debug("returning empty string")
        return ""

    def askedNextUpdateWith(self, msg):
        self.handleCommand(self.parseMsg(msg))

    def handleCommandError(self, e):
        e.trap(Exception)
        log.error("next update command parsing error: %s" % e)
    
    def handleCommand(self, cmd):
        log.debug("handling cmd: %s" % cmd)
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
        
        log.info("Announcing time until the next update")
        self.bot.announce("Time until the next update in the comic " + cmd) 
        self.bot.announce(clock.timeUntilNextUpdate(self.comics[comic]))

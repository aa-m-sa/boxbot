# -*- coding: utf-8 -*-

"""
rssfeed module
"""

import logging
log = logging.getLogger(__name__)

import feedparser
import re

from twisted.internet import task, reactor, threads

from command import command

# todo:
#  * use deferreds properly?
#  * proper exceptions and error-handling

# objective:
# implement thread watching

class TopicStatus:
    """Wrapper for topic"""

    def __init__(self, comicId, text):
        log.debug("created a TopicStatus instance (%d, %s)" % (comicId, text))
        self.comicId = comicId
        self.text = text
        self.fullTitle = "[" + str(comicId) + "]" + text


    def isFresher(self, irctopic):
        if self.comicId > irctopic.comicId:
            return True
        elif self.comicId == irctopic.comicId:
            return self.text != irctopic.text

class Feed:
    """
    Represents the feed.

    id: comic number id (in '[dddd] blahblah', dddd is the id)
    """
    threadEntries = {}
    titleRe = r'\[(\d{4})\](.*)'
    postbyRe = r'Last reply by (.+) on'
    linkRe = r'(\d+)'
    mostRecentId = None
    recentComicEntry = None
    first = True


    def __init__(self, url):
        self.titlePat = re.compile(self.titleRe)
        self.postbyPat = re.compile(self.postbyRe)
        self.linkPat = re.compile(self.linkRe)

        self.url = url
        log.debug("a feed created: %s", url)

    def refresh(self):
        log.debug("updating the feed")
        self.updatedThreads = []
        self.parsedFeed = feedparser.parse(self.url)
        self._readThreadEntries()
        self._setCurrentTopic()
        self.first = False
        log.debug("topic in the updated feed: %s", self.topic)
        return self.topic, self.updatedThreads

        # consider introducing more proper twisted style threading here?
        # i.e. instead of deferToThread in Monitor.rssCheck, do it here, something like:
        # d = threads.deferToThread(feedparser.parse(self.url))
        # d.addCallback(handleParsedFeed)
        # -> handleParsedFeed takes the parsed feed, calls findComicEntries & setCurretTopic

    def _readThreadEntries(self):
        """
        Pours through the feed to find the threads with new posts
        * with every thread, compare the new entry to the stored to see if there's new post
          -> add the thread to self.updatedThreads if affirmative
        * with comic entries, see if there's more recent topic title
        """
        log.debug("reading the feed...")
        for e in self.parsedFeed.entries:
            # has any thread new posts?
            if e.link in self.threadEntries:
                if e.published_parsed > self.threadEntries[e.link].published_parsed:
                    self.threadEntries[e.link] = e
                    self._addToUpdated(e)
            else:
                self.threadEntries[e.link] = e
                # on first run threadEntries empty -> all existing look new
                # after first run, all new entries are necros or new threads
                if not self.first:
                    self._addToUpdated(e)

            # has the thread a comic thread style title?
            comicTitle = self._parseComicTitle(e)
            if comicTitle:
                # what's the most recent [0000] id?
                if not self.mostRecentId or comicTitle['id'] > self.mostRecentId:
                    self.mostRecentId = comicTitle['id']
                # the recent comic entry will be the one with most recent post
                if not self.recentComicEntry:
                    self.recentComicEntry = e
                else:
                    self.recentComicEntry = self._newer(e, self.recentComicEntry)

    def _addToUpdated(self, e):
        e.postby = self.postbyPat.match(e.summary).group(1)
        e.recentlink = "http://gunnerkrigg.proboards.com/threads/recent/" + self.linkPat.search(e.link).group(1)
        self.updatedThreads.append(e)

    def _setCurrentTopic(self):
        parsed = self._parseComicTitle(self.recentComicEntry)
        self.topic = TopicStatus(parsed['id'], parsed['text'])
        log.debug("set current topic in the feed instance (%d)", parsed['id'])

    def _newer(self, entrya, entryb):
        if entrya.published_parsed > entryb.published_parsed:
            return entrya
        else:
            return entryb

    def _parseComicTitle(self, entry):
        m = self.titlePat.match(entry.title)
        if m:
            return {'id': int(m.group(1)), 'text': m.group(2)}
        else:
            return m

class Monitor:
    """
    Reads the RSS feed with a given frequency,
    commands the bot accordingly
    """

    topicRe = r'(.*)\[(\d{4})\](.*)'

    bot = None

    moduleName = 'rssfeed'

    def __init__(self, rssConfig, bot, updatesTitle = True):
        self.feed = Feed(rssConfig['url'])
        self.delay = rssConfig['freq']
        self.isRunning = False
        self.bot = bot
        self.updatesTitle = updatesTitle
        self.blockedForumUsers = {}

        # precompile regex for topicparser
        self.topicPat = re.compile(self.topicRe)

        # is this a good way to do this?
        # consider another options:
        # ...threading? ...proper delayed twisted deferrers? ...?
        # now it acts like it were a gigantic 'one' method, timewise(?)
        # now if rssCheck takes much time -> much blockin >.>

        # we make rssCheck() a looping call
        self.loopcall = task.LoopingCall(self.rssCheck)
        log.debug("Monitor instance created")

        bot.registerModule(self.moduleName, self)

    # bot commands
    @command('rssfeed', ['refresh','update-feed'])
    def forceFeedRefresh(self, cmdTokens, **kwargs):
        """Forces monitor to refresh all feeds.

        Slightly less descriptive 'update-feed' keyword provided for legacy purposes
        """
        log.info("bot received an update command. calling rssCheck()...")
        self.bot.announce('Checking rss feed!')
        self.rssCheck()


    def start(self):
        """Get the bot and start following the feed"""
        log.info("starting following a feed...")
        self.isRunning = True
        self.loopcall.start(self.delay)

    def stop(self):
        """Stop following the feed"""
        self.loopcall.stop()
        log.info("stopped following a feed")

    def blockForumUser(self, user, byWho, reason):
        """Add user to block list"""
        log.info("blocked forum user: %s", user)
        log.info("block by %s", byWho)
        self.blockedForumUsers[user] = (byWho, reason);

    def clearBlockedUser(self, user):
        """Clea a blocked forum poster"""
        try:
            del self.blockedForumUsers[user]
            log.info("removed user %s from blocklist", user)
        except KeyError:
            log.warning("can't remove user %s from blocklist", user)
            pass

    def blockedUserInfo(self, user):
        """Details about blocked forum poster"""
        try:
            details = self.blockedForumUsers[user]
            return details
        except KeyError:
            return None

    def isABlockedUser(self, user):
        """nuff said"""
        return user in self.blockedForumUsers

    def _fetchIrcTopic(self):
        """Get the current irc topic id status from the bot"""
        log.debug("reading irc topic...")
        self._rawirctopic = self.bot.getTopic()
        log.debug("raw irc topic got form bot: %s", self._rawirctopic)

        # we might not be able to correctly parse raw irctopic if
        # a user has set it into non-standard form
        try:
            a, d, t = self._parseIrcTopic()
            self._preamble = a
        except ValueError as e:
            log.debug("handling ValueError (probs couldn't parse irc topic): %s", e)
            # will consider the whole irc topic as a preamble (=retained)
            self._preamble = self._rawirctopic
            d, t = 0, ""
        except TypeError as e:
            log.debug("handling TypeError (probs wiht raw irctopic): %s", e)
            self._preamble = self._rawirctopic = ""
            d, t = 0, ""
        log.debug("set preamble: %s", self._preamble)
        return TopicStatus(d, t)

    def _parseIrcTopic(self):
        """
        Parse the 'raw' irc topic provided by the bot:
            return comicId, thread title text and copy the 'preamble'
        """
        # assume irctopic is of the form:
        # "stuff - stuff blah bleh - [0000] Wow. a topic title
        log.debug("parsing raw irc topic: %s", self._rawirctopic)
        try:
            m = self.topicPat.match(self._rawirctopic)
        except TypeError:
            # _rawirctopic can't be mathced
            raise
        if not m:
            log.debug("irc topic of wrong form. abort parsing, raise error")
            raise ValueError("channel topic of wrong form, couldn't match")
        preamble = m.group(1)
        comicId = int(m.group(2))
        text = m.group(3)
        return preamble, comicId, text

    def rssCheck(self):
        """
        Check if the rss feed has been updated with a fresh fora comic thread
        if yes, call ircTopicUpdater
        """
        log.debug("checking the rss feed...")
        d_feed = threads.deferToThread(self.feed.refresh)

        d_feed.addCallback(self._handleFeedUpdate)

    def _handleFeedUpdate(self, (feedTopic, updatedThreads)):
        """ Receives the current topic in the feed"""
        log.debug("determining if topic should be updated")
        ircTopic = self._fetchIrcTopic()
        log.debug("sees current topic as %s" % ircTopic.fullTitle)
        log.debug("sees feedTopic as %s" % feedTopic.fullTitle)
        if feedTopic.isFresher(ircTopic):
            self._ircTopicUpdate(feedTopic)

        log.debug("announcing threads with new posts")
        for t in updatedThreads:
            if t.postby not in self.blockedForumUsers:
                self.bot.announce(t.postby + " posted to '" + t.title + "' " + t.recentlink)
            else:
                log.debug("filtering forum post by " + t.posty)
                log.debug("filtered:" + self.blockedForumsUsers)


    def _ircTopicUpdate(self, feedTopic):
        """
        instruct the bot to set the irc topic into a fresh one
        """
        log.info("monitor wants to update irc topic")
        t = self._preamble + feedTopic.fullTitle
        if self.updatesTitle:
            log.info("commanding bot to change the topic...")
            self.bot.setTopic(t)
        else:
            self._wantsToSet = t
            log.warning("asked to update topic but updatesTitle set false.")
            log.info("commanding bot to announce topic... %s", t)
            self.bot.announceWant(t)

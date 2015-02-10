# -*- coding: utf-8 -*-

"""
an IRC bot based on twisted matrix libraries

updates channel topic prompted by a RSS feed

License: GPLv3. See readme.
"""

import logging

log = logging.getLogger(__name__)

from twisted.words.protocols import irc
from twisted.internet import reactor, protocol, task, defer, threads

import sys
import argparse
import yaml

# custom modules
import rssfeed
import urltitle
import updatenotifier
import twitter

# todo: features:
# * a fully fledged command parser
#
# todo: refactoring / codebase improvement:
# * proper error & exception handling for stability / hardness
# * separate bot (which takes commands and processes them) and protocol/client ?
#   ...e.g. copy pyfibot and subclass Bot from BotCore/IrcProtocol

class Bot(irc.IRCClient):
    """A protocol object (our 'bot') for IRC'ing"""

    # settings
    lineRate = 1
    maxWAnnounce = 4
    doneWAnnounce = 0

    willAuth = True

    hasQuit = False
    announceAllowed = True

    # "AI"
    awws = 0
    maxAwws = 3
    cachedTopic = None

    def __init__(self, factory):
        self.factory = factory
        self.nickname = self.factory.config['nickname']
        self.realname = self.factory.config['realname']


    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        log.info("connection made. starting heartbeat")
        self.startHeartbeat()

    def connectionLost(self, reason):
        irc.IRCClient.connectionLost(self, reason)
        log.info("connection lost: %s", reason)

    def signedOn(self):
        """Called when bot has successfully connected to a server."""
        log.info("signed on.")

        if self.willAuth:
            # if we're on quakenet... well, for now we're are, but TODO: check!!
            log.info("we're on quakenet and authenticating...")
            self.mode(self.nickname, True, "x")     # set user mode +x
            # authname, authpass should be got in a more sensible way
            self.msg("Q@CServe.quakenet.org", "AUTH %s %s" %
                    (self.factory.quakeConfig['authName'], self.factory.quakeConfig['authPass']))

        # join the channel
        self.join(self.factory.channel)

    def joined(self, channel):
        log.info("successfully joined the channel: %s", channel)
        self.cachedOp = False
        if not self.factory.feedMonitor.isRunning:
            log.info("starting feed monitor...")
            self.factory.feedMonitor.start()

    def modeChanged(self, user, channel, setted, modes, args):
        log.debug("noticed mode change: %s, %s, %s, %s, %s"
                % (user, channel, setted, modes, args))
        if channel == self.factory.channel:
            if self.nickname in args:
                log.info("bot mode changed by %s. set: %s modes: %s"
                        % (user, str(setted), modes))
                if 'o' in modes:
                    self.cachedOp = setted
                    log.debug("bot op mode changed: %s", setted)
            if 'o' in modes and setted:
                # reset wantAnnounce counter if bot sees someone to get ops
                log.debug("resetting doneWAnnounce counter...")
                self.doneWAnnounce = 0

    def topicUpdated(self, user, channel, newTopic):
        """In channel, user changed the topic to newTopic.

        Also called when first joining a channel."""

        log.info("%s topic updated by %s: %s" % (channel, user, newTopic))
        self.cachedTopic = newTopic
        # joined the channel and got a topic: start monitoring the feed

    def blockForumUserPosts(self, userName, byWho, reason="Not specified"):
        """Suppress notifying about forum posts made by userName"""
        self.factory.feedMonitor.blockForumUser(userName, byWho, reason)

    def urlfetcher(self, msg):

        def titleAnnounce(titletext):
            log.info("channel patron posted an url, announcing title")
            self.announce(titletext)

        log.debug("bot to determine if privmsg an url")
        url = urltitle.parseUrl(msg)
        if url:
            d = threads.deferToThread(urltitle.fetchTitle, url)
            d.addCallback(titleAnnounce)
            d.addErrback(lambda e: log.error("couldn't fetch title, %s", e))

    def privmsg(self, user, channel, msg):
        """This will get called when the bot receives a message"""
        log.debug("bot received a message: %s: %s: %s" % (channel, user, msg))

        msg = msg.decode('utf-8')

        self.urlfetcher(msg)

        def parseBotCmd(cmd):
            return msg.startswith(self.nickname + ", " + cmd) or msg.startswith(self.nickname + ": " + cmd)
        # A QUICK HACK:
        # proper command parser to be implemented
        if channel == self.factory.channel:
            if parseBotCmd("quit"):
                log.info("bot received a quitting command")
                self.quit("Awww.")
            elif parseBotCmd("update feed"):
                log.info("bot received an update command. calling rssCheck()...")
                self.factory.feedMonitor.rssCheck()
            elif parseBotCmd("set topic"):
                log.info("bot received a command to start setting topic")
                self.factory.feedMonitor.updatesTitle = True
                self.factory.feedMonitor.rssCheck()
            elif parseBotCmd("stop setting topic") or parseBotCmd("stop"):
                log.info("bot received a command to start setting topic")
                self.factory.feedMonitor.updatesTitle = False
            elif parseBotCmd("silence"):
                log.info("silencing bot")
                self.announceAllowed = False
            elif parseBotCmd("unsilence"):
                log.info("unsilencing bot")
                self.announceAllowed = True
            elif parseBotCmd("introduce yourself") or parseBotCmd("help"):
                log.info("bot received an introduce command. proceeding...")
                self.announce("HELLOOO")
                self.announce("boxbot-" + self.factory.config['build'] + ", command with 'boxbot: <commandstr>'")
                self.announce("important commands: quit, stop (setting topic), silence, block-forum-user (user)")
                self.announce("contact maus if I'm too terrible and break something.")
            elif parseBotCmd("next update"):
                log.info("bot asked to retrieve time until the next comic update")
                self.factory.comicNotifier.askedNextUpdateWith(msg)
            elif parseBotCmd("block-forum-user"):
                log.info("blocking forum notifications from a user with a msg %s", msg)
                blockParams = msg.split()
                if len(blockParams) > 2:
                    if len(blockParams) == 4:
                        self.blockForumUserPosts(blockParams[2], user, blockParams[3])
                    else:
                        self.blockForumUserPosts(blockParams[2], user)
            elif parseBotCmd("unblock-user"):
                log.info("removing block")
                blockParams = msg.split()
                if len(blockParams) == 3:
                    self.announce("Removing filter on " + blockParams[2])
                    self.factory.feedMonitor.clearBlockedUser(blockParams[2])
            elif parseBotCmd("tell-block-status"):
                bparams = msg.split()
                if len(bparams) == 3:
                    bstatus = self.factory.feedMonitor.isABlockedUser(bparams[2])
                    self.announce("Posts by " + bparams[2] + " blocked: " + str(bstatus))
                    if bstatus:
                        details = self.factory.feedMonitor.blockedUserInfo(bparams[2])
                        self.announce("Block by " + details[0] + " (" + details[1] + ")")
            elif self.nickname in msg:
                self.announceAww()

    def action(self, user, channel, data):
        data = data.decode('utf-8')

        self.urlfetcher(data)

        if channel == self.factory.channel and self.nickname in data:
            if "fish" in data or "trout" in data or "large" in data:
                if "slaps" in data:
                    self.describe(self.factory.channel, "slaps " + user + " with a large HELLOOO-OOO....")
            else:
                self.announceAww()

    # commands that monitor should be able to use
    def announceAww(self):
            log.info("bot called, responding with aww")
            self.awws += 1
            if self.awws < self.maxAwws:
                self.announce("Awww.")
            else:
                self.announce("Awww. (Help available by calling me with 'boxbot: help')")
                self.awws = 0

    def quit(self, msg):
        """Disconnect from network"""
        self.hasQuit = True
        log.info("bot quitting (with message %s). stopping heartbeat...", msg)
        self.stopHeartbeat()
        log.info("stopping feedmonitor...")
        self.factory.feedMonitor.stop()
        irc.IRCClient.quit(self, msg)

    def applyColorFormat(self, *msg, **kwargs):
        """put some nice colors on the message"""
        colors = kwargs.get('colors', None)
        toAssemble = []
        if not colors or len(colors) != len(msg):
            for m in msg:
                toAssemble.append(irc.attributes.fg.gray[m])
        else:
            for m, c in zip(msg, colors):
                if not c:
                    toAssemble.append(irc.attributes.fg.gray[m])
                else:
                    toAssemble.append(c[m])
        return irc.assembleFormattedText(irc.attributes.normal[toAssemble])

    def announce(self, *msg, **kwargs):
        """Announce a message (or a message consisting of multiple parts) to channel.

        Optionally, one can specify special colors (or other irc effects) for
        each part of the msg by providing a tuple of valid twisted irc
        attributes (or None for those parts where the default format should be
        applied)"""
        specialColors = kwargs.get('specialColors', None)
        if self.announceAllowed:
            colored = self.applyColorFormat(msg, colors=specialColors)
            self.say(self.factory.channel, colored.encode('utf-8'))
            log.info("bot announced: %s", msg)
        else:
            log.info("announce called but bot is silenced")

    def announceWant(self, topic):
        log.info("announceWant called")
        # timer: actually announce the want only N times
        if self.doneWAnnounce <= self.maxWAnnounce:
            log.debug("announcement counter ok, making an announcement")
            self.announce("wants to set topic to: " + topic)
            self.doneWAnnounce += 1

    def setTopic(self, topic):
        """Set the channel topic"""
        # check if opp'd, then set, otherwise, complain
        log.info("bot asked to set topic")
        if self.cachedOp:
            log.info("bot setting topic to: %s", topic)
            self.topic(self.factory.channel, topic.encode('utf-8'))
        else:
            log.info("bot thinks it's not able to set topic")
            self.announceWant(topic)

    def getTopic(self):
        """Get the channel topic"""
        if self.cachedTopic:
            return self.cachedTopic
        else:
            return ""


class BotFactory(protocol.ReconnectingClientFactory):
    """A factory for Bots"""

    def __init__(self, config):
        """Initializing the factory"""
        self.config = config
        self.channel = config['channel']
        self.rssConfig = config['rss']
        self.quakeConfig = config['quakeAuth']
        self.notifyConfig = config['notifyComics']
        self.twitterConfig = config['twitter']
        # pass the config to feed monitor
        log.debug("bot factory initilized")

    def startFactory(self):
        """This will be called before I begin listening on a Port or Connector."""
        log.debug("factory starting")
        pass

    def stopFactory(self):
        """Called before stopping listening on all Ports/Connectors. """
        log.debug("factory stopping")

    def buildProtocol(self, addr):
        """Create an instance of a subclass of Protocol."""
        log.debug("build protocol called: building bot.")
        # successfully connected, create the bot
        p = Bot(self)
        self.bot = p
        # start monitoring the feed with a Monitor;
        # provide it with a bot to manipulate
        log.debug("creating a feed monitor with a bot...")
        self.feedMonitor = rssfeed.Monitor(self.rssConfig, p)
        # start the comic update notifier clock thingy, and provide it a bot too:
        log.debug("creating a comic update time notifier")
        self.comicNotifier = updatenotifier.Notifier(self.notifyConfig, p)

        log.debug("creating a twitter feed listener")
        self.tweetListener = twitter.IRCListener(self.twitterConfig, p)

        # reset reconnection delay
        self.resetDelay()
        return p

    def clientConnectionLost(self, connector, reason):
        """Connection lost, if not quitting, reconnect."""
        log.info("connection lost (%s)" % reason)
        if self.bot.hasQuit:
            log.info("quitting: stopping reactor")
            reactor.stop()
        else:
            log.info("reconnect via parent...")
            protocol.ReconnectingClientFactory.clientConnectionLost(self,
                    connector, reason)

    def clientConnectionFailed(self, connector, reason):
        log.info("connection failed (%s), should reconnect..." % reason)
        protocol.ReconnectingClientFactory.clientConnectionFailed(self,
                connector, reason)

def readConfig(configFile):
    try:
        with open(configFile) as handle:
            config = yaml.load(handle)
    except IOError:
        log.error("could not open %s" % (configFile))
        raise
    log.debug("config file read successfully")
    return config

def main(args):
    log.info("-"*10)
    log.info("entered main")

    # reading from yaml config file
    try:
        config = readConfig(args.config)
        # !!! config file is not validated!
        # wrong syntax etc can cause problems
    except Exception as e:
        log.error("reading config file failed. terminating...")
        sys.exit(1)

    factory = BotFactory(config)

    host, port = config['network']['host'], config['network']['port']
    log.debug("got config")
    log.debug("...connection details: %s:%d, channel %s" % (host, port, config['channel']))
    log.debug("...rss details: %s, delay %d sec" 
            % (config['rss']['url'], config['rss']['freq']))
    log.debug("...comic-notify details: TODO")

    log.info("connecting to %s:%d" % (host, port))
    reactor.connectTCP(host, port, factory)
    reactor.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="path to the yaml config file")
    parser.add_argument("--log", choices=["debug", "info"], help="logging level", default="info")
    args = parser.parse_args()

    #loggin setup
    numericLevel = getattr(logging, args.log.upper(), None)
    logging.basicConfig(filename='boxbot.log', level=numericLevel,
            format='%(asctime)s, %(name)s %(levelname)s %(message)s')

    main(args)

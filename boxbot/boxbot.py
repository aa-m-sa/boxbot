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

# commands
import command

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

class CoreCommands:
    """Bot core commands"""
    moduleName = "core"

    def __init__(self, bot):
        self.bot = bot
        self.bot.registerModule(self.moduleName, self)

    @command.command("core", ['quit'])
    def quit(self, tokens, **kwargs):
        log.info("bot received a quitting command")
        self.bot.quit("Awww.")

    @command.command("core", ['silence'])
    def silence(self, tokens, **kwargs):
        log.info("silencing bot")
        self.bot.announceAllowed = False

    @command.command("core", ['unsilence'])
    def unsilence(self, tokens, **kwargs):
        log.info("unsilencing bot")
        self.bot.announceAllowed = True

    @command.command("core", ['help'])
    def help(self, tokens, **kwargs):
        log.info("bot received an introduce command. proceeding...")
        self.bot.announce("HELLOOO")
        self.bot.announce("boxbot-" + self.bot.factory.config['build'] + ", command with 'boxbot: <commandstr>'")
        self.bot.announce("You can get list of commands by calling me with 'list-commands'")
        self.bot.announce("contact maus if I'm too terrible and break something.")

    @command.command("core", ['list-commands'])
    def listCommands(self, tokens, **kwargs):
        log.info("bot asked to list commands")
        for m in command.allCommands:
            s = "Module: " + m + "; commands: "
            s += ", ".join(command.allCommands[m].keys())
            self.bot.announce(s)


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

    # command stuff; TODO move this elsewhere
    commandDelimiters = [':', ',']

    regModules = {}


    def __init__(self, factory):
        self.factory = factory
        self.nickname = self.factory.config['nickname']
        self.realname = self.factory.config['realname']
        self.commandCore = CoreCommands(self)

    def registerModule(self, module, instance):
        self.regModules[module] = instance

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

        def notValidCommand():
            self.announce("You must provide me a valid command!")

        accepted = [self.nickname + d for d in self.commandDelimiters]
        if channel == self.factory.channel and msg.startswith(tuple(accepted)):
            commandTokens = msg.split()
            if len(commandTokens) < 2:
                notValidCommand()
                return
            key = commandTokens[1]
            # stupid debug stuff
            log.debug('Trying to dechiper ' + key)
            for mod in command.allCommands:
                if key in command.allCommands[mod]:
                    # maybe something more Twisted would more apt? meh
                    fun = command.allCommands[mod][key]
                    log.debug('Calling fun ' + str(fun))
                    fun(self.regModules[mod], commandTokens[1:], user=user, channel=channel, msg=msg)
                    return
            notValidCommand()
        elif self.nickname in msg:
            self.announceAww()

        # TODO re-implement this using new command API
        #    elif parseBotCmd("next update"):
        #        log.info("bot asked to retrieve time until the next comic update")
        #        self.factory.comicNotifier.askedNextUpdateWith(msg)

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
        sys.exit()

    def applyColorFormat(self, *msg, **kwargs):
        """put some nice colors on the message"""
        colors = kwargs.get('colors')
        toAssemble = []
        log.debug(msg)
        log.debug(colors)
        msg = [m.encode('utf-8') for m in msg]
        if not colors or len(colors) != len(msg):
            log.debug("no colors")
            for m in msg:
                log.debug(m)
                log.debug(type(m))
                toAssemble.append(irc.attributes.fg.gray[m])
        else:
            log.debug("colors!")
            for m, c in zip(msg, colors):
                log.debug(m)
                log.debug(c)
                if not c:
                    log.debug("no c")
                    toAssemble.append(irc.attributes.fg.gray[m])
                else:
                    log.debug("using special color")
                    log.debug(c)
                    toAssemble.append(c[m])
        return irc.assembleFormattedText(irc.attributes.normal[toAssemble])

    def announce(self, *msg, **kwargs):
        """Announce a message (or a message consisting of multiple parts) to channel.

        Optionally, one can specify special colors (or other irc effects) for
        each part of the msg by providing a tuple of valid twisted irc
        attributes (or None for those parts where the default format should be
        applied)"""
        specialColors = kwargs.get('specialColors')
        if self.announceAllowed:
            colored = self.applyColorFormat(*msg, colors=specialColors)
            self.say(self.factory.channel, colored)
            log.info("bot announced: %s", msg)
        else:
            log.info("announce called but bot is silenced")

    def announceWant(self, topic):
        log.info("announceWant called")
        # timer: actually announce the want only N times
        if self.doneWAnnounce <= self.maxWAnnounce:
            log.debug("announcement counter ok, making an announcement")
            self.announce("wants to set topic to ", topic, specialColors=(None, irc.attributes.fg.blue))
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

        # attach external modules:
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

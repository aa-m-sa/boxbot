# -*- coding: utf-8 -*-

"""
twitter reader module

Relays tweets to IRC
"""

# depends on tweepy; just do `pip install tweepy`

import logging
log = logging.getLogger(__name__)

from tweepy.streaming import StreamListener
from tweepy import OAuthHandler
from tweepy import Stream
import tweepy
from twisted.words.protocols.irc import attributes

import json

class IRCListener(StreamListener):

    def __init__(self, config, bot):
        self.bot = bot

        self.auth = OAuthHandler(config["auth"]["consumer_key"], config["auth"]["consumer_secret"])
        self.auth.set_access_token(config["auth"]["access_token"], config["auth"]["access_token_secret"])

        api = tweepy.API(self.auth)

        stream = Stream(self.auth, self)

        self.users = [str(api.get_user(u).id) for u in config["follow"]]
        stream.filter(follow=self.users, async=True)

        log.debug("a twitter.IRCListener instance created")

    def on_data(self, data):
        parsed = json.loads(data)
        if "text" in parsed and parsed["user"]["id_str"] in self.users:
            # TODO: use Twisted color formatting
            tweeter = parsed["user"]["name"]
            tweet = parsed["text"]
            statusLinkPart = "- https://twitter.com/" + parsed["user"]["screen_name"] + "/status/" + parsed["id_str"]
            self.bot.announce(tweeter, " tweeted ", tweet, statusLinkPart, specialColors=(None, None, attributes.fg.blue, None))
        return True

    def on_error(self, status):
        log.debug("Twitter error: " + str(status))

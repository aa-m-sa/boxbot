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

import json

class IRCListener(StreamListener):

    def __init__(self, config, bot):
        self.bot = bot

        self.auth = OAuthHandler(config["auth"]["consumer_key"], config["auth"]["consumer_secret"])
        self.auth.set_access_token(config["auth"]["access_token"], config["auth"]["access_token_secret"])

        stream = Stream(self.auth, self)
        stream.userstream(track=config["follow"], async=True)

        log.debug("a twitter.IRCListener instance created")

    def on_data(self, data):
        parsed = json.loads(data)
        if "text" in parsed:
            self.bot.announce(parsed["user"]["name"] + " tweeted \"" + parsed["text"] + "\"")
        return True

    def on_error(self, status):
        log.debug("Twitter error: " + status)

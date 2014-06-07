# -*- coding: utf-8 -*-

"""
urltitle module
"""

import logging
log = logging.getLogger(__name__)

from twisted.internet import reactor, defer
from  bs4 import BeautifulSoup
import requests

def parseUrl(msg):
    """
    See if maybeUrl is an url.
    """
    urlIndex = msg.find('http://')
    
    if urlIndex == -1:
        wwwIndex = msg.find('www')
        if wwwIndex == -1:
            return ""
        msg = "http://" + msg[wwwIndex:]
        urlIndex = 0

    msgParts = msg[urlIndex:].split()
    return msgParts[0]

def fetchTitle(url):
    """
    fetches the title of the document behind the url
    Returns a twisted deferred.
    """
    d = defer.Deferred()

    try:
        r = requests.get(url, timeout = 1.0)
    except Exception as e:
        # requests threw an exception
        log.error("requests produced exception %s", e)
        d.errback(e)
    else: 
        soup = BeautifulSoup(r.text)
        d.callback(soup.title.string)

    return d

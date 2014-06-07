# -*- coding: utf-8 -*-

"""
urltitle module
"""

import logging
log = logging.getLogger(__name__)

from twisted.internet import reactor, defer
from  bs4 import BeautifulSoup
import requests
import re

urlRe = r'http(s)?://'
urlPat = re.compile(urlRe)
wwwRe = r'www([.].+){2}'
wwwPat = re.compile(wwwRe)

def sizeOf(contLength):
    num = int(contLength)
    for d in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return "%.1f %s" % (num, d)
        num /= 1024.0

def parseUrl(msg):
    """
    See if maybeUrl is an url.
    """
    url = urlPat.search(msg)
    
    if not url:
        www = wwwPat.search(msg)
        if not www:
            return ""
        msg = "http://" + msg[www.start():]
        urlIndex = 0
    else:
        urlIndex = url.start()

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
        if r.headers['content-type'] == 'text/html':
            soup = BeautifulSoup(r.text)
            d.callback("Title: " + soup.title.string)
        else:
            d.callback("content-type: "+ r.headers['content-type'] + ", size "
                    + sizeOf(r.headers['content-length']))

    return d

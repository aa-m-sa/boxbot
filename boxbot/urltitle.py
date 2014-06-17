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
        r = requests.head(url, timeout = 1.0)
        if 'text/html' in r.headers['content-type']:
            rd = requests.get(url)
            soup = BeautifulSoup(rd.text)
            titlestring = "Title: " + soup.title.string.strip()
        else:
            titlestring = "content-type: "+ r.headers['content-type'] + ", size " + sizeOf(r.headers['content-length'])
    except Exception as e:
        # thrown an exception
        log.error("fetchTitle produced exception: %s", e)
        d.errback(e)
    else: 
        d.callback(titlestring)

    return d

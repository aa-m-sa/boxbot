# -*- coding: utf-8 -*-

"""
urltitle module
"""

import logging
log = logging.getLogger(__name__)

from twisted.internet import reactor, defer
from from bs4 import BeautifulSoup
import requests

def parseurl(maybeUrl):
    """
    See if maybeUrl is an url.

    Returns a twisted deferred.
    """


# -*- coding: utf-8 -*-

"""
Provides a rudimentary user command api.

* A decorator thingy that can be used in modules to register user commands.

* Dict based module - command hierarchy
"""

import logging

log = logging.getLogger(__name__)


allCommands = {}

def command(module, keywords):
    """Decorator that provides command interface for bot modules.

    Usage:
        from boxbot import command
        class ModuleMainClass():
            ...

            def __init__(self, bot...):
                ...
                bot.registerModule(moduleName, self)

            @command(moduleName, ['command-key', 'words'])
            def someCommand(self, cmgTokens, **kwargs):
                # do stuff channel patron requested
                pass

    :module: a name for module e.g. __name__
    :keywords: list of command strings; each word consists of string of
    non-whitespace (all text after first whitespace (if any) will be dropped
    silently)
    """
    def decorator(f):
        if module not in allCommands:
            allCommands[module] = {}
            log.debug('Created a new module hierarchy in allCommands: %s', module)
        for s in keywords:
            spl = s.split()
            allCommands[module][spl[0]] = f
            log.debug('Added a new command function: %s', f)
        return f
    return decorator

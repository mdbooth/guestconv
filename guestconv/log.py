# coding: utf-8
# guestconv
#
# Copyright (C) 2013 Red Hat Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import logging
import os

class FunctionWrappingHandler(logging.Handler):
    """A Handler that delegates the responsibility of
    writing a log message to another function."""
    def __init__(self, logFunc):
        logging.Handler.__init__(self)
        self._logFunc = logFunc

    def emit(self, record):
        msgStr = self.format(record)
        self._logFunc(record.levelno,msgStr)

def get_logger_object( loggerOrFunc):
    """Helper function to get a logging.Logger object that guestconv
    classes can cache locally.

    Three cases:
    * loggerOrFunc is a logging.Logger.  Then just return the logger.
    * loggerOrFunc is None.  Then return a new Logger that writes to
      stderr.  The threshold for messages is WARNING unless the
      environment variable GUESTCONV_LOG_LEVEL is defined.
    * loggerOrFunc is a function.  Return a new logger that wraps the
      function.  Note that function takes two arguments, an integer
      (the logging level e.g. logging.WARNING) and the log message
      string.
    """

    if isinstance(loggerOrFunc,logging.Logger):
        return loggerOrFunc

    # Intentionally not instantiating a logger object through
    # logging.getLogger(<name>), because we might get an old one we
    # already created and this could be especially bad if one wanted
    # to use a wrapped function but the other did not.
    logger = logging.Logger(u'guestconv')

    if loggerOrFunc is None:
        handler = logging.StreamHandler()
        logLevel = logging.WARNING
        if u'GUESTCONV_LOG_LEVEL' in os.environ:
            logLevel = os.environ[u'GUESTCONV_LOG_LEVEL'].upper()
    else:
        handler = FunctionWrappingHandler(loggerOrFunc)
        # always send it all logging messages along to the logging
        # callback function.  It's up to it whether to filter or not.
        logLevel = logging.NOTSET

    formatter = logging.Formatter(u'%(asctime)s - %(filename)s '+
                          u'%(funcName)s() - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logLevel)
    return logger

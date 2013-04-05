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


# guestconv.log.get_logger_object() is the main helper for getting
# logging objects and passing through to a logging callback function
# when necessary.  This is an illustrative script for the kind of
# behaviour to expect.

import guestconv
import guestconv.log

l1 = guestconv.log.get_logger_object(None)
l1.fatal("ouch!")
l2 = guestconv.log.get_logger_object(None)
# note it is good we are not seeing duplicate messages from l1 and l2
l2.warn("warning!!!!")
l1.debug('quiet')

# Note the threshold that determines whether the above messages print
# is defined by the environment variable, GUESTCONV_LOG_LEVEL

if l1 == l2:
    print "Uh oh, l1 and l2 seem to be the same"

l3 = guestconv.log.get_logger_object(l2)
if l3 != l2:
    print "Uh oh, did not get the same object back"


def logging_func_foo( level, msg ):
    print 'Level %d, Message %s' % (level, msg)

l3 = guestconv.log.get_logger_object(logging_func_foo)
# logging_func_foo() should correctly print all of these (ie,
# GUESTCONV_LOG_LEVEL does not make a difference when using a
# callback)
l3.info('an info message')
l3.debug('a debug message')
l3.log( 5, 'a less-than-debug message')

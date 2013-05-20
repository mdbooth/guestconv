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

import guestconv.exception

class BaseConverter(object):
    def __init__(self, h, target, root, db, logger):
        if target != 'rhev':
            raise guestconv.exception.UnsupportedConversion()

        self._h = h
        self._root = root
        self._db = db
        self._logger = guestconv.log.get_logger_object(logger)

    def inspect(self):
        # Child classes must implement this
        raise NotImplementedError("Implement me")

    def convert(self, bootloaders, devices):
        # Child classes must implement this
        raise NotImplementedError("Implement me")

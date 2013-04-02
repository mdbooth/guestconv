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

from guestconv.log import *

class RedHat(object):
    def __init__(self, h, target, root, logger):
        if target != 'rhev':
            raise guestconv.exception.UnsupportedConversion()

        self._h = h
        self._root = root
        self._logger = logger

        distro = h.inspect_get_distro(root)
        if (h.inspect_get_type(root) != 'linux' or
                h.inspect_get_distro(root) not in ('rhel', 'fedora')):
            raise guestconv.exception.UnsupportedConversion

    def _log(self, level, message):
        if self._logger is None:
            return

        self._logger(level, message)

    def inspect(self):
        bootloaders = {}
        info = {}
        devices = {}

        h = self._h
        root = self._root

        info['hostname'] = h.inspect_get_hostname(root)
        info['os'] = h.inspect_get_type(root)
        info['distribution'] = h.inspect_get_distro(root)
        info['version'] = {
            'major': h.inspect_get_major_version(root),
            'minor': h.inspect_get_minor_version(root)
        }

        self._log(DEBUG, 'Set info for %s' % info['hostname'])

        return bootloaders, info, devices

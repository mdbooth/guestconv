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

from guestconv.converters.base import BaseConverter

class RedHat(BaseConverter):
    def __init__(self, h, target, root, logger):
        super(RedHat,self).__init__(h, target, root, logger)
        distro = h.inspect_get_distro(root)
        if (h.inspect_get_type(root) != 'linux' or
                h.inspect_get_distro(root) not in ('rhel', 'fedora')):
            raise guestconv.exception.UnsupportedConversion

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

        self._logger.debug('Set info for %s' % info['hostname'])
        self._logger.debug('info dict: %s' % str(info))

        return bootloaders, info, devices

    def convert(self, bootloaders, devices):
        self._logger.info('Converting root %s' % self._root)

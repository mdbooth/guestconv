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

import guestfs
import lxml.etree as ET

import guestconv.converters
import guestconv.exception
import guestconv.db

from guestconv.log import *


class Converter(object):
    def __init__(self, db_paths, logger=None):
        self._h = guestfs.GuestFS()
        self._inspection = None
        self._config = guestconv.db.DB(db_paths)
        self._converters = {}
        self._logger = logger

    def __del__(self):
        self._h.close()

    def _log(self, level, message):
        if self._logger is None:
            return

        self._logger(level, message)

    def add_drive(self, path, hint=None):
        """Add the drive that has the virtual image that we want to
        convert.

        :param path: path to the image
        :param hint: TODO significance of hint?

        """
        if hint:
            self._h.add_drive(path, name=path)
        else:
            self._h.add_drive(path)
        # TODO verify that guestfs call succeeded

    def inspect(self, target):
        """Inspect the drive and record needed transformations in the
        XML document which is returned to the caller.  Gracefully
        handles multi-boot (meaning there are multiple "root"
        partitions and possibly multi-OS'es).

        :param target: string indicating the hypervisor.  One of... TODO
        :returns:  XML document (a string)

        """
        if self._inspection:
            return self._inspection

        h = self._h

        h.launch()
        root_devices = h.inspect_os()

        bootloaders = []
        roots = {}
        for device in root_devices:
            for klass in guestconv.converters.all:
                converter = None
                try:
                    converter = klass(h, target, device, self._logger)
                except guestconv.exception.UnsupportedConversion:
                    self._log(DEBUG, "Converter %s unsupported for root %s" % \
                              (converter, device))
                    next

                (root_bl, root_info, root_devices) = converter.inspect()

                self._converters[device] = converter

                bootloaders.extend(root_bl)
                roots[device] = {
                    'info': root_info,
                    'devices': root_devices
                }

        builder = ET.TreeBuilder()
        builder.start('guestconv', {})

        builder.start('boot', {})
        for bootloader in bootloaders:
            attrs = {
                'disk': bootloader['disk'],
                'type': bootloader['type']
            }
            replacement = bootloader['replacement']
            if replacement is not None:
                attrs['replacement'] = replacement
            builder.start('loader', attrs)

            options = bootloader['options']
            if options is not None:
                for option in options:
                    attrs = {
                        'disk': option['disk'],
                        'type': option['type'],
                        'name': option['name']
                    }
                    builder.start('loader_opt', attrs)
                    builder.end('loader_opt')

            builder.end('loader')
        builder.end('boot')

        for name, root in roots.iteritems():
            builder.start('root', {'name': name})

            builder.start('info', {})
            def build_info(i):
                for name, data in i.iteritems():
                    builder.start(name, {})
                    if isinstance(data, dict):
                        build_info(data)
                    else:
                        builder.data(str(data))
                    builder.end(name)
            build_info(root['info'])
            builder.end('info')

            builder.start('devices', {})
            for device in root['devices']:
                attrs = {
                    'type': root['type'],
                    'id': root['id'],
                    'driver': root['driver']
                }
                builder.start('device', attrs)
                options = device['options']
                if options is not None:
                    for option in options:
                        builder.start('driver', {})
                        builder.data(option)
                        builder.end('driver')
                builder.end('device')
            builder.end('devices')

            builder.end('root')

        builder.end('guestconv')

        xml = builder.close()
        self._inspection = ET.tostring(xml, encoding='utf8')

        return self._inspection

    def convert(self, desc):
        root = ET.fromstring(desc)

        bootloaders = []
        roots = {}

        for bootloader in root.xpath('/guestconv/boot/loader'):
            # XXX
            pass

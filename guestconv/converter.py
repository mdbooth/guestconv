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
import logging
import lxml.etree as ET

import guestconv.converters
import guestconv.exception
import guestconv.db

from guestconv.log import *

import os

class Converter(object):
    """A Converter is capable of converting (possibly
    multi-boot/multi-OS) disk image(s) to a target hypervisor.

    If no logger object is provided, log messages are written to
    stderr and the threshold of log messages logged is WARNING unless
    the environment variable GUESTCONV_LOG_LEVEL is defined (one of
    DEBUG,INFO,WARNING,ERROR,CRITICAL).

    :param db_paths: list of filenames (xml databases describing capabilities)
    :param logger: optional logging object
    """
    def __init__(self, db_paths, logger=None):
        self._h = guestfs.GuestFS()
        self._inspection = None
        self._config = guestconv.db.DB(db_paths)
        self._converters = {}
        if logger is None:
            self._logger = logging.getLogger(__name__)
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                u'%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
            logLevel = logging.WARNING
            if u'GUESTCONV_LOG_LEVEL' in os.environ:
                logLevel = os.environ[u'GUESTCONV_LOG_LEVEL'].upper()
            self._logger.setLevel(logLevel)
        else:
            self._logger = logger

    def __del__(self):
        self._h.close()

    def _log(self, level, message):
        if self._logger is None:
            return

        self._logger(level, message)

    def add_drive(self, path, hint=None):
        """Add the drive that has the virtual image that we want to
        convert.  Multiple drives may be added.  <-- TODO correct?

        :param path: path to the image
        :param hint: TODO significance of hint?

        """
        if hint:
            self._h.add_drive(path, name=path)
        else:
            self._h.add_drive(path)
        # TODO verify that guestfs call succeeded

    def inspect(self, target):
        """Inspect the drive, record needed transformations (to
        make the OS(es) bootable by the target hypervisor) in the XML
        document which is returned to the caller.  Gracefully handles
        multi-boot (meaning there are multiple "root" partitions and
        possibly multi-OS'es).

        This is a read-only operation.  <-- TODO correct?

        :param target: string indicating the hypervisor.  One of... TODO
        :returns:  XML document (a string)

        """
        if self._inspection:
            return self._inspection

        h = self._h

        h.launch()
        guestfs_roots = h.inspect_os()

        bootloaders = {}
        roots = {}
        for device in guestfs_roots:
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

                bootloaders.update(root_bl)
                roots[device] = {
                    'info': root_info,
                    'devices': root_devices
                }

        builder = ET.TreeBuilder()
        builder.start('guestconv', {})

        builder.start('boot', {})
        for disk, props in bootloaders.iteritems():
            attrs = {
                'disk': disk,
                'type': props['type'],
            }
            name = props['name']
            if name is not None:
                attrs['name'] = name
            replacement = props['replacement']
            if replacement is not None:
                attrs['replacement'] = replacement
            builder.start('loader', attrs)

            options = props['options']
            if options is not None:
                for option in options:
                    attrs = {
                        'type': option['type'],
                        'name': option['name']
                    }
                    builder.start('loader', attrs)
                    builder.end('loader')

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
        """Do the conversion indicated by desc, an XML document.  The
        virtual image will be modified in place.

        Note that desc may simply be the XML returned by inpsect(), or
        a modified version of it.

        :param desc:  XML document string
        :returns:  TODO

        """
        dom = ET.fromstring(desc)

        bootloaders = {}
        roots = {}

        for loader in dom.xpath('/guestconv/boot/loader'):
            disk = loader.get('disk')
            props = {
                'type': loader.get('type')
            }
            replacement = loader.get('replacement')
            if replacement is not None:
                props['replacement'] = replacement

            bootloaders[disk] = props

        for root in dom.xpath('/guestconv/root'):
            name = root.get('name')

            try:
                converter = self._converters[name]
            except KeyError:
                raise guestconv.exception.InvalidConversion \
                    ('root %s does not exist' % name)

            devices = []
            for device in root.xpath('device'):
                devices.append({
                    'type': device.get('type'),
                    'id': device.get('id'),
                    'driver': device.get('driver')
                })

            converter.convert(bootloaders, devices)

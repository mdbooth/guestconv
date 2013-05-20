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

from guestconv.exception import *
from guestconv.converters.grub import *
from guestconv.converters.base import BaseConverter
from guestconv.lang import _

class Debian(BaseConverter):
    def __init__(self, h, target, root, db, logger):
        super(Debian,self).__init__(h, target, root, db, logger)
        distro = h.inspect_get_distro(root)
        if (h.inspect_get_type(root) != u'linux' or
            distro not in (u'debian', u'ubuntu')):
            raise UnsupportedConversion()

    def inspect(self):
        info = {}
        options = {}

        h = self._h
        root = self._root

        info[u'hostname'] = h.inspect_get_hostname(root)
        info[u'os'] = h.inspect_get_type(root)
        info[u'distribution'] = h.inspect_get_distro(root)
        info[u'arch'] = h.inspect_get_arch(root)
        info[u'version'] = {
            u'major': h.inspect_get_major_version(root),
            u'minor': h.inspect_get_minor_version(root)
        }

        self._bootloader = self._inspect_bootloader()

        bl_disk, bl_props = self._bootloader.inspect()

        return {bl_disk: bl_props}, info, options

    def _inspect_bootloader(self):
        for bl in [GrubLegacy, Grub2EFI, Grub2BIOS]:
            try:
                return bl(self._h, self._root, self._logger)
            except BootLoaderNotFound:
                pass # Try the next one

        raise ConversionError(_(u"Didn't detect a bootloader for root %(root)s") %
                              {u'root': self._root})

    def convert(self, bootloaders, options):
        self._logger.info(_(u'Converting root %(name)s') %
                          {u'name': self._root})

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

"""Detect and manipulate configurations of various versions of grub"""

import re
from itertools import chain, ifilter

from guestconv.exception import *
from guestconv.converters.exception import *
from guestconv.lang import _
from guestconv.converters.util import *

def detect(h, root, converter, logger):
    '''Detect a grub bootloader, and return an appropriate object'''

    # Check all devices for an EFI boot partition
    for device in h.list_devices():
        try:
            guid = h.part_get_gpt_type(device, 1)
        except GuestFSException:
            # Not EFI if partition isn't GPT
            next

        if guid == u'C12A7328-F81F-11D2-BA4B-00A0C93EC93B':
            # Look for the EFI boot partition in mountpoints
            try:
                mp = h.mountpoints()[device + '1']
            except KeyError:
                logger.debug(u'Detected EFI bootloader with no mountpoint '
                             u'on disk {}'.format(device))
                next

            for cfg in h.glob_expand(u'{}/EFI/*/grub.*'.format(mp)):
                m = re.search(u'grub\.(conf|cfg)$')
                if m.group(1) == u'conf':
                    return GrubEFI(h, root, converter, logger, device, cfg)
                else:
                    return Grub2EFI(h, root, converter, logger, device, cfg)

    # Look for grub legacy config
    for cfg in [u'/boot/grub/grub.conf', u'/boot/grub/menu.lst']:
        if h.is_file_opts(cfg, followsymlinks=True):
            return GrubBIOS(h, root, converter, logger, cfg)

    # Look for grub2 config
    if h.is_file_opts(u'/boot/grub2/grub.cfg', followsymlinks=True):
        return Grub2BIOS(h, root, converter, logger)

    raise BootLoaderNotFound()


class GrubBase(object):
    '''Functions supported by grubby, and therefore common between grub legacy
    and grub2
    '''

    def __init__(self, h, root, converter, logger):
        self._h = h
        self._root = root
        self._converter = converter
        self._logger = logger
        self._disk = None

    def installed_on(self, disk):
        if disk == self._disk:
            self._logger.debug(u'Bootloader {} can convert {}'.
                               format(self.__class__, disk))
            return True

        self._logger.debug(u"Bootloader {} installed on {} can't convert {}".
                           format(self.__class__, self._disk, disk))
        return False

    def get_initrd(self, path):
        for line in h.command_lines([u'grubby', u'--info', path]):
            m = re.match(u'^initrd=(\S+)', line)
            if m is not None:
                return m.group(1)

        raise ConversionError(
            _(u"grubby didn't return an initrd for kernel %(kernel)s") %
            {u'kernel': path})


class Grub(GrubBase):
    '''Methods for inspecting and manipulating grub legacy'''

    def __init__(self, h, root, converter, logger, cfg):
        super(Grub, self).__init__(h, root, converter, logger)

        self._grub_conf = cfg

        # Find the path which needs to be prepended to paths in grub.conf to
        # make them absolute
        # Look for the most specific mount point discovered
        self._grub_fs = ''
        mounts = h.inspect_get_mountpoints(root)
        for path in [u'/boot/grub', u'/boot']:
            if path in mounts:
                self._grub_fs = path
                self._grub_device = mounts[path]
                break

        if self._grub_fs == '':
            self._grub_device = mounts[u'/']

        # We used to check that the augeas grub lens included our specific
        # grub.conf location, but augeas has done this by default for some time
        # now.

    def list_kernels(self):
        '''List all kernels from grub.conf in the order that grub would try
        them'''

        h = self._h
        grub_conf = self._grub_conf
        grub_fs = self._grub_fs

        def _default_first():
            '''Get a list of kernels with the default kernel, if any, first'''

            # Get a list of all kernels
            paths = h.aug_match(u'/files{}/title/kernel'.format(grub_conf))

            # Try to move the default kernel to the front of the list. This will
            # fail if there is no default, or if the default specifies a
            # non-existent kernel

            try:
                default_str = h.aug_get(u'/files{}/default'.format(grub_conf))
            except GuestFSException:
                return paths # We don't care if there is no default

            try:
                default_int = int(default_str)
            except ValueError:
                self._logger.info(_(u'{path} contains invalid default: '
                                    u'{default').
                                    format(path=grub_conf, default=default_str))
                return paths


            # Nothing to do if the default is already first in the list
            if default_int == 0:
                return paths

            # Grub indices are zero-based, augeas is 1-based
            default_path = (u'/files{}/title[{}]/kernel'.
                            format(grub_conf, default_int + 1))

            # Put the default at the beginning of the list
            return chain([default_path],
                         ifilter(lambda x: x != default_path, paths))

        paths = _default_first()

        # Fetch the value of all detected kernels, and sanity check them
        kernels = []
        checked = {}
        for path in paths:
            if path in checked:
                continue
            checked[path] = True

            kernel = grub_fs + h.aug_get(path)

            if h.is_file_opts(kernel, followsymlinks=True):
                kernels.append(kernel)
            else:
                self._logger.warn(_(u"grub refers to {kernel}, which doesn't "
                                    "exist").format(kernel=kernel))

        return kernels


class GrubBIOS(Grub):
    def __init__(self, h, root, converter, logger, cfg):
        super(GrubBIOS, self).__init__(h, root, converter, logger, cfg)

    def inspect(self):
        m = re.match(u'^/dev/([a-z]*)[0-9]*$', self._grub_device)
        disk = m.group(1)
        props = {
            u'type': u'BIOS',
            u'name': u'grub-bios'
        }

        return disk, props


class GrubEFI(Grub):
    def __init__(self, h, root, converter, logger, device, cfg):
        super(GrubEFI, self).__init__(h, root, converter, logger, cfg)

        self._disk = device

    def inspect(self):
        props = {
            u'type': u'EFI',
            u'name': u'grub-efi',
            u'replacement': {
                u'name': u'grub-bios',
                u'type': u'BIOS'
            }
        }

        return self._disk, props

    def convert(self, target):
        if target != 'grub-bios':
            raise ConversionError(_(u'Cannot convert grub-efi bootloader to '
                                    u'{target}').format(target=target))

        grub_conf = u'/boot/grub/grub.conf'

        h = self._h
        h.cp(self._grub_conf, grub_conf)
        h.ln_sf(grub_conf, u'/etc/grub.conf')

        # Reload to push up grub.conf in its new location
        h.aug_load()

        h.command([u'grub-install', self._grub_device])

        return GrubBIOS(self._h, self._root, self._converter, self._logger,
                        grub_conf)


class Grub2(GrubBase):
    def list_kernels(self):
        h = self._h

        kernels = []

        # Get the default kernel
        default = h.command([u'grubby', u'--default-kernel']).strip()
        if len(default) > 0:
            kernels.append(default)

        # This is how the grub2 config generator enumerates kernels
        for kernel in (h.glob_expand(u'/boot/kernel-*') +
                       h.glob_expand(u'/boot/vmlinuz-*') +
                       h.glob_expand(u'/vmlinuz-*')):
            if (kernel != default and
                   not re.match(u'\.(?:dpkg-.*|rpmsave|rpmnew)$', kernel)):
                kernels.append(kernel)

        return kernels


class Grub2BIOS(Grub2):
    def __init__(self, h, root, converter, logger):
        if not h.exists(u'/boot/grub2/grub.cfg'):
            raise BootLoaderNotFound()

        super(Grub2BIOS, self).__init__(h, root, converter, logger)

        # Find the grub device
        mounts = self._h.inspect_get_mountpoints(self._root)
        for path in [u'/boot/grub2', u'/boot', u'/']:
            if path in mounts:
                m = re.match(u'^/dev/([a-z]*)[0-9]*$', mounts[path])
                self._disk = m.group(1)
                break

    def inspect(self):
        props = {
            u'type': u'BIOS',
            u'name': u'grub2-bios'
        }

        return self._disk, props


class Grub2EFI(Grub2):
    def __init__(self, h, root, converter, logger):
        super(Grub2EFI, self).__init__(h, root, converter, logger)

        # Check all devices for an EFI boot partition
        for device in h.list_devices():
            try:
                guid = h.part_get_gpt_type(device, 1)
                if guid == u'C12A7328-F81F-11D2-BA4B-00A0C93EC93B':
                    self._disk = device
                    break
            except GuestFSException:
                # Not EFI if partition isn't GPT
                next

        # Check we found an EFI boot partition
        if self._disk is None:
            raise BootLoaderNotFound()

        # Look for the EFI boot partition in mountpoints
        try:
            mp = h.mountpoints()[device + '1']
        except KeyError:
            logger.debug(u'Detected EFI bootloader with no mountpoint')
            raise BootLoaderNotFound()

        self._cfg = None
        for path in h.find(mp):
            if re.search(u'/grub\.cfg$', path):
                self._cfg = mp + path
                break

        if self._cfg is None:
            logger.debug(u'Detected mounted EFI bootloader but no grub.cfg')
            raise BootLoaderNotFound()

    def inspect(self):
        props = {
            u'type': u'EFI',
            u'name': u'grub2-efi',
            u'replacement': {
                u'name': u'grub2-bios',
                u'type': u'BIOS'
            }
        }

        return self._disk, props

    def convert(self, target):
        if target != 'grub2-bios':
            raise ConversionError(_(u'Cannot convert grub2-efi bootloader to '
                                    u'{target}').format(target=target))

        # For grub2, we:
        #   Turn the EFI partition into a BIOS Boot Partition
        #   Remove the former EFI partition from fstab
        #   Install the non-EFI version of grub
        #   Install grub2 in the BIOS Boot Partition
        #   Regenerate grub.cfg
        h = self._h

        if not self._converter._install_capability('grub2-bios'):
            raise ConversionError(_(u'Failed to install bios version of grub2'))

        # Relabel the EFI boot partition as a BIOS boot partition
        h.part_set_gpt_type(self._disk, 1,
                            u'21686148-6449-6E6F-744E-656564454649')

        # Delete the fstab entry for the EFI boot partition
        for node in h.aug_match(u"/files/etc/fstab/*[file = '/boot/efi']"):
            h.aug_rm(node)

        try:
            h.aug_save()
        except GuestfsException as ex:
            augeas_error(h, ex)

        h.command([u'grub2-install', self._disk])
        h.command([u'grub2-mkconfig', u'-o', u'/boot/grub2/grub.cfg'])

        return Grub2BIOS(h, self._root, self._converter, self._logger)

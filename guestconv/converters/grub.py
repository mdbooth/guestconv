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

from guestconv.exception import *
from guestconv.lang import _

# libguestfs currently returns all exceptions as RuntimeError. We hope this
# might be improved in the future, but in the meantime we capture the intention
# with this placeholder
GuestFSException = RuntimeError

class BootLoaderNotFound(Exception): pass

def augeas_error(h, ex):
    msg = str(ex) + '\n'
    try:
        for error in h.aug_match(u'/augeas/files//error'):
            m = re.match(u'^/augeas/files(/.*)/error$', error)
            file_path = m.group(1)

            detail = {}
            for detail_path in h.aug_match(error + u'//*'):
                m = re.match(u'^%s/(.*)$' % error, detail_path)
                detail[m.group(1)] = h.aug_get(detail_path)

            msg += _(u'augeas error for %(path)s') % {u'path': file_path}
            if u'message' in detail:
                msg += ': %s' % detail[u'message']
            msg += '\n'

            if u'pos' in detail and u'line' in detail and u'char' in detail:
                msg += (_(u'error at line %(line)s, char %(char)s, file position %(pos)s') %
                        {u'line': detail[u'line'],
                         u'char': detail[u'char'],
                         u'pos': detail[u'pos']}) + '\n'

            if u'lens' in detail:
                msg += (_(u'augeas lens: %(lens)s') %
                        {u'lens': detail[u'lens']} + '\n')
    except GuestFSException as new:
        raise ConversionError(
                _(u'error generating augeas error: %(error)s') %
                {u'error': new} + '\n' +
                _(u'original error: %(error)s') % {u'error': ex})

    msg = msg.strip()

    if len(msg) > 0:
        raise ConversionError(msg)

    raise ex


# Functions supported by grubby, and therefore common between grub legacy and
# grub2
class Grub(object):
    def get_initrd(self, path):
        for line in h.command_lines([u'grubby', u'--info', path]):
            m = re.match(u'^initrd=(\S+)', line)
            if m is not None:
                return m.group(1)

        raise ConversionError(
            _(u"grubby didn't return an initrd for kernel %(kernel)s") %
            {u'kernel': path})


# Methods for inspecting and manipulating grub legacy
class GrubLegacy(Grub):
    def __init__(self, h, root, logger):
        self._h = h
        self._root = root
        self._logger = logger

        self._grub_conf = None
        for path in [u'/boot/grub/grub.conf', u'/boot/grub/menu.lst']:
            if h.exists(path):
                self._grub_conf = path
                break

        if self._grub_conf is None:
            raise BootLoaderNotFound()

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

    def inspect(self):
        m = re.match(u'^/dev/([a-z]*)[0-9]*$', self._grub_device)
        disk = m.group(1)
        props = {
            u'type': u'BIOS',
            u'name': u'grub-legacy'
        }

        return disk, props

    def list_kernels(self):
        h = self._h
        grub_conf = self._grub_conf
        grub_fs = self._grub_fs

        # List all kernels from grub.conf in the order that grub would try them

        paths = []
        # Try to add the default kernel to the front of the list. This will
        # fail if there is no default, or if the default specifies a
        # non-existent kernel.
        try:
            default = h.aug_get(u'/files%s/default' % grub_conf)
            paths.extend(
                h.aug_match(u'/files%s/title[%s]/kernel' % (grub_conf, default))
            )
        except GuestFSException:
            pass # We don't care

        # Add kernel paths from grub.conf in the order they are listed. This
        # will add the default kernel twice, but it doesn't matter.
        try:
            paths.extend(h.aug_match(u'/files%s/title/kernel' % grub_conf))
        except GuestFSException as ex:
            augeas_error(h, ex)

        # Fetch the value of all detected kernels, and sanity check them
        kernels = []
        checked = {}
        for path in paths:
            if path in checked:
                continue
            checked[path] = True

            try:
                kernel = grub_fs + h.aug_get(path)
            except GuestFSException as ex:
                augeas_error(h, ex)

            if h.exists(kernel):
                kernels.append(kernel)
            else:
                self._logger.warn(_(u"grub refers to %(kernel)s, which doesn't exist") %
                                  {u'kernel': kernel})

        return kernels


class Grub2(Grub):
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
    def __init__(self, h, root, logger):
        if not h.exists(u'/boot/grub2/grub.cfg'):
            raise BootLoaderNotFound()

        self._h = h
        self._root = root
        self._logger = root

    def inspect(self):
        # Find the grub device
        disk = None
        mounts = self._h.inspect_get_mountpoints(self._root)
        for path in [u'/boot/grub2', u'/boot', u'/']:
            if path in mounts:
                m = re.match(u'^/dev/([a-z]*)[0-9]*$', mounts[path])
                disk = m.group(1)
                break

        props = {
            u'type': u'BIOS',
            u'name': u'grub2-bios'
        }

        return disk, props


class Grub2EFI(Grub2):
    def __init__(self, h, root, logger):
        self._h = h
        self._root = root
        self._logger = logger

        self._disk = None
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
            u'replacement': u'grub2-bios',
            u'options': [
                {u'type': u'BIOS', u'name': u'grub2-bios'},
                {u'type': u'EFI', u'name': u'grub2-efi'},
            ]
        }

        return self._disk, props

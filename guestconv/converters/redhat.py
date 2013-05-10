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

import functools
from itertools import izip_longest

from guestconv.exception import *
from guestconv.converters.grub import *
from guestconv.converters.base import BaseConverter
from guestconv.lang import _

@functools.total_ordering
class Package(object):
    def __init__(self, name, epoch=None, version=None, release=None, arch=None):
        if name is None:
            raise ValueError(u'name argument may not be None')

        self.name = name
        self.epoch = epoch
        self.version = version
        self.release = release
        self.arch = arch

    def __str__(self):
        elems = []
        if self.epoch is not None:
            elems.append(epoch)
            elems.append(u':')
        elems.append(self.name)
        if self.version is not None:
            elems.append(u'-')
            elems.append(self.version)
        if self.release is not None:
            elems.append(u'-')
            elems.append(self.release)
        if self.arch is not None:
            elems.append(u'.')
            elems.append(self.arch)

        return ''.join(elems)

    def _cmp(self, other):
        def _splitver(v):
            """Split an rpm version string

            We split not only on non-alphanumeric characters, but also on
            the boundary of digits and letters. This corresponds to the
            behaviour of rpmvercmp because it does 2 types of iteration
            over a string. The first iteration skips non-alphanumeric
            characters. The second skips over either digits or letters
            only, according to the first character of a.

            Note that we can do this with a single split in perl, but
            python's split is broken for zero-width matches, and will
            never be fixed: http://bugs.python.org/issue3262"""

            if v is not None:
                pos = 0
                for m in re.finditer(u'(?<=\d)(?=[a-zA-Z])|'
                                     u'(?<=[a-zA-Z])(?=\d)|'
                                     u'(?:\W|_)+', v):
                    yield v[pos:m.start()]
                    pos = m.end()
                yield v[pos:]

        def _numstrcmp(a, b):
            # Check if both values can be coerced into an int
            try:
                ai = int(a)
                bi = int(b)
                a = ai
                b = bi
            except ValueError:
                # If either value can't be coerced to an int, we leave them
                # both as strings
                pass
            except TypeError:
                # If either value is None, leave them both alone
                pass

            if a < b:
                return -1
            if a > b:
                return 1
            return 0

        def _rpmvercmp(a, b):
            """Compare 2 rpm version/release numbers

            This is an implementation of rpmvercmp from rpm. Note that it is
            intended to be insanity-compatible with the original."""

            # Simple equality test
            if a == b:
                return 0

            # Split a and b into parts, and compare each part in turn
            # If 1 string is longer, but leading parts are equal, the longer
            # string is greater.
            for pa, pb in izip_longest(_splitver(a), _splitver(b)):
                c = _numstrcmp(pa, pb)
                if c != 0:
                    return c

            # If we got here, the strings differ only in non-alphanumeric
            # separators
            return 0

        if not isinstance(other, self.__class__):
            raise TypeError(u'Cannot compare Package to {other}'.\
                            format(other=other.__class__.__name__))

        if self.name != other.name or self.arch != other.arch:
            raise TypeError(u'Packages with different names or architectures '
                            u'are not comparable')

        # Treat empty epoch as zero
        e1 = self.epoch
        e2 = other.epoch
        if e1 is None:
            e1 = u'0'
        if e2 is None:
            e2 = u'0'

        # Compare epochs
        c = _numstrcmp(e1, e2)
        if c != 0:
            return c

        # Compare versions
        c = _rpmvercmp(self.version, other.version)
        if c != 0:
            return c

        # Treat empty release as the empty string
        r1 = self.release
        r2 = other.release
        if r1 is None:
            r1 = u''
        if r2 is None:
            r2 = u''

        # Compare releases
        return _rpmvercmp(r1, r2)

    def __eq__(self, other):
        return self._cmp(other) == 0

    def __lt__(self, other):
        return self._cmp(other) < 0


class RedHat(BaseConverter):
    def __init__(self, h, target, root, logger):
        super(RedHat,self).__init__(h, target, root, logger)
        distro = h.inspect_get_distro(root)
        if (h.inspect_get_type(root) != u'linux' or
                h.inspect_get_distro(root) not in (u'rhel', u'fedora')):
            raise UnsupportedConversion()

    def inspect(self):
        info = {}
        devices = {}

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

        return {bl_disk: bl_props}, info, devices

    def _inspect_bootloader(self):
        for bl in [GrubLegacy, Grub2EFI, Grub2BIOS]:
            try:
                return bl(self._h, self._root, self._logger)
            except BootLoaderNotFound:
                pass # Try the next one

        raise ConversionError(_(u"Didn't detect a bootloader for root %(root)s") %
                              {u'root': self._root})

    def convert(self, bootloaders, devices):
        self._logger.info(_(u'Converting root %(name)s') %
                          {u'name': self._root})

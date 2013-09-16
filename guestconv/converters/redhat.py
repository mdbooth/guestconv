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

import errno
import functools
import os.path
import re
import rpm

from copy import copy
from itertools import chain, izip_longest

from guestconv.exception import *
from guestconv.converters.exception import *
import guestconv.converters.grub
from guestconv.converters.base import BaseConverter
from guestconv.converters.util import *
from guestconv.lang import _

RHEL_BASED = (u'rhel', u'centos', u'scientificlinux', u'redhat-based')

@functools.total_ordering
class Package(object):
    class InvalidEVR(GuestConvException): pass

    def __init__(self, name, epoch=None, version=None, release=None, arch=None,
                 evr=None):
        if name is None:
            raise ValueError(u'name argument may not be None')

        self.name = name
        self.arch = arch

        if evr is not None:
            m = re.match(ur'(?:(\d+):)?([^-]+)(?:-(\S+))?$', evr)
            if m is None:
                raise Package.InvalidEVR()

            self.epoch = m.group(1)
            self.version = m.group(2)
            self.release = m.group(3)
        else:
            self.epoch = epoch
            self.version = version
            self.release = release

    def __str__(self):
        elems = []
        if self.epoch is not None:
            elems.append(self.epoch)
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
                for m in re.finditer(ur'(?<=\d)(?=[a-zA-Z])|'
                                     ur'(?<=[a-zA-Z])(?=\d)|'
                                     ur'(?:\W|_)+', v):
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

        if (self.name != other.name or
            (self.arch is not None and other.arch is not None and
            (self.arch != other.arch))):
            raise TypeError(u'Cannot compare packages {a.name}.{a.arch} and '
                            u'{b.name}.{b.arch}. Comparable packages must have '
                            u'the same name and architecture.'.
                            format(a=self, b=other))

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
    def __init__(self, h, root, guest, db, logger):
        super(RedHat, self).__init__(h, root, guest, db, logger)
        distro = h.inspect_get_distro(root)
        if (h.inspect_get_type(root) != u'linux' or
            h.inspect_get_distro(root) not in chain([u'fedora'], RHEL_BASED)):
            raise UnsupportedConversion()

    def _get_installed(self, name, arch=None):
        if arch is None:
            search = name
        else:
            search = u'{}.{}'.format(name, arch)

        rpmcmd = [u'rpm', u'-q', u'--qf',
                  ur'%{EPOCH} %{VERSION} %{RELEASE} %{ARCH}\n', search]

        try:
            output = self._h.command_lines(rpmcmd)
        except GuestFSException:
            # RPM command returned non-zero. This might be because there was
            # actually an error, or might just be because the package isn't
            # installed.
            # Unfortunately, rpm sent its error to stdout instead of stderr,
            # and command_lines only gives us stderr in $@. To get round this
            # we execute the command again, sending all output to stdout and
            # ignoring failure. If the output contains 'not installed', we'll
            # assume it's not a real error.

            cmd = (u'LANG=C ' +
                   u' '.join([u"'"+i+u"'" for i in rpmcmd]) + u' 2>&1 ||:')
            error = self._h.sh(cmd)

            if re.search(ur'not installed', error):
                return

            raise ConversionError(
                _(u'Error running {command} in guest: {msg}').
                format(command=cmd, msg=error))

        for line in output:
            m = re.match(ur'(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$', line)
            if m is None:
                raise ConversionError(
                    _(u'Unexpected output from rpm: {output}').
                    format(output='\n'.join(output)))

            epoch = m.group(1)
            version = m.group(2)
            release = m.group(3)
            arch = m.group(4)

            if epoch == '(none)':
                epoch = None

            yield Package(name, epoch, version, release, arch)

    def _cap_missing_deps(self, name):
        h = self._h
        root = self._root
        db = self._db

        arch = h.inspect_get_arch(root)
        missing = []
        cap = db.match_capability(name, arch, h, root)
        if cap is None:
            self._logger.debug(u'No {} capability found for this root'.
                               format(name))
            return []

        for (pkg, params) in cap.iteritems():
            try:
                target = Package(pkg, evr=params[u'minversion'])
            except Package.InvalidEVR:
                self._logger.info(_(u'Ignoring invalid minversion for package '
                                    u'{name} in virtio capability: {version}').
                                  format(name=pkg,
                                         version=params[u'minversion']))
                target = Package(pkg)

            need = not params[u'ifinstalled']
            for installed in self._get_installed(pkg):
                if installed < target:
                    need = True
                if installed >= target:
                    need = False
                    continue
            if need:
                missing.append(target)

        return missing

    def inspect(self):
        h = self._h
        root = self._root

        info = {
            u'hostname': h.inspect_get_hostname(root),
            u'os': h.inspect_get_type(root),
            u'distribution': h.inspect_get_distro(root),
            u'arch': h.inspect_get_arch(root),
            u'version': {
                u'major': h.inspect_get_major_version(root),
                u'minor': h.inspect_get_minor_version(root)
            }
        }

        # Drivers which are always available
        graphics = []
        network = [
            (u'e1000', u'Intel E1000'),
            (u'rtl8139', u'Realtek 8139')
        ]
        block = [
            (u'ide-hd', u'IDE'),
            (u'scsi-hd', u'SCSI')
        ]
        console = [
            (u'vc', _(u'Kernel virtual console')),
            (u'serial', _(u'Serial console'))
        ]

        options = [
            (u'graphics', _(u'Graphics driver'), graphics),
            (u'network', _(u'Network driver'), network),
            (u'block', _(u'Block device driver'), block),
            (u'console', _(u'System Console'), console)
        ]


        def _missing_deps(name, missing):
            l = u', '.join([str(i) for i in missing])
            self._logger.info(_(u'Missing dependencies for {name}: {missing}')
                              .format(name=name, missing=l))

        virtio_deps = self._cap_missing_deps(u'virtio')
        if len(virtio_deps) == 0:
            network.append((u'virtio-net', u'VirtIO'))
            block.append((u'virtio-blk', u'VirtIO'))
            console.append((u'virtio-serial', _(u'VirtIO Serial')))
        else:
            _missing_deps(u'virtio', virtio_deps)

        cirrus_deps = self._cap_missing_deps(u'cirrus')
        if len(cirrus_deps) == 0:
            graphics.append((u'cirrus-vga', u'Cirrus'))
        else:
            _missing_deps(u'cirrus', cirrus_deps)

        qxl_deps = self._cap_missing_deps(u'qxl')
        if len(qxl_deps) == 0:
            graphics.append((u'qxl-vga', u'Spice'))
        else:
            _missing_deps(u'qxl', qxl_deps)

        try:
            self._bootloader = guestconv.converters.grub.detect(
                h, root, self, self._logger)
        except BootLoaderNotFound:
            raise ConversionError(_(u"Didn't detect a bootloader for root "
                                    u'{root}').format(root=self._root))

        bl_disk, bl_props = self._bootloader.inspect()

        return {bl_disk: bl_props}, info, options


        raise ConversionError(_(u"Didn't detect a bootloader for root %(root)s") %
                              {u'root': self._root})

    def convert(self, bootloaders, options):
        self._logger.info(_(u'Converting root %(name)s') %
                          {u'name': self._root})

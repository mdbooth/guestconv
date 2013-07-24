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


class GuestNetworking(object):
    """Execute a block of code with guest networking configured"""

    def __init__(self, h):
        self._h = h
        self._old_resolv_conf = None

    def __enter__(self):
        h = self._h
        if h.exists(u'/etc/resolv.conf'):
            self._old_resolv_conf = h.mktemp(u'/etc/resolv.conf.XXXXXX')
            h.mv(u'/etc/resolv.conf', self._old_resolv_conf)
            h.write_file(u'/etc/resolv.conf', u'nameserver 169.254.2.3', 0)

    def __exit__(self, type, value, tb):
        if self._old_resolv_conf is not None:
            self._h.mv(self._old_resolv_conf, u'/etc/resolv.conf')

        return False


class RPMInstaller(object):
    def __init__(self, h, root, logger):
        self._h = h
        self._root = root
        self._logger = logger

    def get_installed(self, name, arch=None):
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
                   u' '.join(map(lambda x: u"'"+x+u"'", rpmcmd)) +
                   u' 2>&1 ||:')
            error = self._h.sh(cmd)

            if re.search(ur'not installed', error):
                return

            raise ConversionError(
                _(u'Error running {command} in guest: {msg}').
                format(command=cmd, msg=error))

        for line in output:
            m = re.match(ur'^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$', line)
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


class Up2dateInstaller(RPMInstaller):
    @classmethod
    def supports(klass, h, root):
        if (h.exists(u'/usr/bin/up2date') and
                h.exists(u'/etc/sysconfig/rhn/systemid')):
            return True

    def __init__(self, h, root, logger):
        super(Up2dateInstaller, self).__init__(h, root, logger)


class YumInstaller(RPMInstaller):
    class NoPackage(GuestConvException): pass

    INSTALL = 0
    UPGRADE = 1
    LIST = 2

    @classmethod
    def supports(klass, h, root):
        if h.exists(u'/usr/bin/yum'):
            return True

    def __init__(self, h, root, logger):
        super(YumInstaller, self).__init__(h, root, logger)

        # Old versions of yum without --showduplicates won't install or list any
        # package version other than the latest one
        self._old_packages = False
        for line in h.command_lines([u'/usr/bin/yum', u'--help']):
            if re.search(ur'--showduplicates', line):
                self._old_packages = True
                break

        if not self._old_packages:
            logger.info(_(u'The version of YUM installed in this guest only '
                          u'supports the installation of the latest version '
                          u'of a package. Guestconv will not be able to match '
                          u'version numbers of installed packages during '
                          u'conversion.'))

    def _yum_cmd(self, package, mode):
        cmdline = [u'LANG=C /usr/bin/yum -y']
        if mode == YumInstaller.INSTALL:
            cmdline.append(u'install')
        elif mode == YumInstaller.UPGRADE:
            cmdline.append(u'upgrade')
        else:
            cmdline.append(u'list')

        cmdline.append(str(package))

        try:
            with GuestNetworking(self._h):
                output = self._h.sh_lines(" ".join(cmdline))
        except GuestFSException as ex:
            self._logger.debug(u'Yum command failed with: {error}'.
                               format(error=ex.message))
            raise YumInstaller.NoPackage()

        for line in output:
            if (mode == YumInstaller.INSTALL and
                re.search(ur'(?:^No package|^Nothing to do)', line)):
                raise YumInstaller.NoPackage()
            if mode == YumInstaller.UPGRADE and re.search(ur'^No Packages'):
                raise YumInstaller.NoPackage()

        return output

    def check_available(self, pkgs):
        for i in pkgs:
            if self._old_packages:
                self._logger.info(_(u'Checking package {pkg} is available via '
                                    u'YUM').format(pkg=str(i)))
                try:
                    self._yum_cmd(i, YumInstaller.LIST)
                    return True
                except YumInstaller.NoPackage:
                    return False
            else:
                # We just want to lookup name.arch
                name_arch = Package(i.name, arch=i.arch)
                self._logger.info(_(u'Checking for latest version of {pkg} '
                                    u'available via YUM').
                                  format(pkg=str(name_arch)))
                output = self._yum_cmd(name_arch, YumInstaller.LIST)

                for line in output:
                    # Look for output lines starting with package name
                    # containing version and source repo
                    m = re.match(ur'{}\s+(\S+)\s+\S+\s*$'.
                                 format(re.escape(str(name_arch))), line)
                    if m is None:
                        continue

                    try:
                        found = Package(i.name, evr=m.group(1))
                    except Package.InvalidEVR:
                        self._logger.debug(u"{}: doesn't look like evr".
                                           format(m.group(1)))
                        continue

                    # Check if this package is new enough
                    self._logger.debug(u'Package {pkg} is available'.
                                       format(pkg=str(found)))
                    if found >= i:
                        return True
                return False


class LocalInstaller(RPMInstaller):
    def __init__(self, h, root, db, logger):
        super(LocalInstaller, self).__init__(h, root, logger)
        self._db = db

    def _read_local_rpm(self, path):
        # Read the rpm header from the local file
        hdr = None
        try:
            with open(path, 'rb') as rpm_fd:
                ts = rpm.TransactionSet()
                # Don't check package signatures before installation, which will
                # fail unless we have the signing key for the target OS
                # installed locally. We implicitly trust these packages.
                ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)
                hdr = ts.hdrFromFdno(rpm_fd)

                return Package(hdr[u'NAME'], hdr[u'EPOCH'], hdr[u'VERSION'],
                               hdr[u'RELEASE'], hdr[u'ARCH'])
        except IOError as e:
            # Display an additional warning to the user for any error other
            # than file missing
            if e.errno != errno.ENOENT:
                self._logger.warn(_(u'Unable to open local file '
                                    u'{path}: {error}').
                                    format(path=path, error=e.message))
        except rpm.error as e:
            self._logger.warn(_(u'Unable to read rpm package header from '
                                u'{path}').format(path=path))

        return None

    def _report_missing_app(self, name, arch, missing):
        h = self._h
        root = self._root

        os = h.inspect_get_type(root)
        distro = h.inspect_get_distro(root)
        version = u'{}.{}'.format(h.inspect_get_major_version(root),
                                  h.inspect_get_minor_version(root))

        self._logger.warn(_(u"Didn't find {name} app for os={os} "
                            u'distro={distro} version={version} '
                            u'arch={arch}').
                            format(name=name, os=os, distro=distro,
                                   version=version, arch=arch))

        missing.append(u'app:'+name)

    def _resolve_required_deps(self, names, required, missing, arch=None,
                               is_subarch=False, visited=[]):
        h = self._h
        root = self._root

        if arch is None:
            arch = h.inspect_get_arch(self._root)

        for name in names:
            # Don't get stuck in a loop
            canon_name = name+'.'+arch
            if canon_name in visited:
                continue
            visited.append(canon_name)

            # Lookup local path and dependencies from the db
            path, deps = self._db.match_app(name, arch, h, root)
            if path is None:
                # Ignore failed matches for subarches
                if is_subarch:
                    continue

                self._report_missing_app(name, arch, missing)
                continue

            # If we're checking a subarch, we don't actually want to install the
            # package. However, we have to upgrade it if there's already an
            # older version installed, otherwise we'll end up with a version
            # mis-match between architectures, which normally leads to a
            # conflict.
            #
            # If we aren't checking a subarch, we want to ensure that this
            # package unless a newer version is already installed.
            need = True

            # Read NEVRA from the local rpm
            pkg = self._read_local_rpm(path)

            # Check if we need to install the package
            if pkg is None:
                # We don't know if we need the package or not if it's
                # missing. For the purposes of reporting to the user we
                # treat it as if we did.
                missing.append(path)
            else:
                found_older = False
                for installed in self.get_installed(pkg.name, pkg.arch):
                    # No need to do anything if there's already a newer version
                    # installed
                    if pkg <= installed:
                        need = False
                        break

                    # For subarch, we're looking for something which needs to be
                    # upgraded
                    if is_subarch and pkg > installed:
                        found_older = True
                        break
                if is_subarch and not found_older:
                    need = False

            if need:
                required.append(path)
                self._resolve_required_deps(deps, required, missing, arch,
                                            False, visited)

                # For x86_64 packages except kernel packages, also check if
                # there is any i386 or i686 version installed. If there is,
                # check if it needs to be upgraded
                kernel_names = [u'kernel', u'kernel-smp', u'kernel-hugemem',
                                u'kernel-largesmp']
                if arch == u'x86_64' and name not in kernel_names:
                    self._resolve_required_deps([name], required, missing,
                                                u'i386', True, visited)

    def check_available(self, pkgs):
        missing = []
        required = []
        self._resolve_required_deps(map(lambda pkg: pkg.name, pkgs), required, missing)

        if len(missing) > 0:
            self._logger.warn(
                _(u'The following files referenced in the configuration are '
                  u'required, but missing: {list}').
                format(list=u' '.join(missing)))
            return False

        return True


class Installer(object):
    NETWORK_INSTALLERS = [YumInstaller]

    def __init__(self, h, root, db, logger):
        self._h = h
        self._root = root
        self._db = db
        self._logger = logger

        self._installer = None

        for c in Installer.NETWORK_INSTALLERS:
            if c.supports(h, root):
                self._installer = c(h, root, logger)

        if self._installer is None:
            self._installer = LocalInstaller(h, root, db, logger)

    def get_installed(self, name, arch=None):
        return self._installer.get_installed(name, arch)

    def check_available(self, pkgs):
        self._logger.debug(u'Checking availability of: {}'.
                           format(', '.join(map(lambda pkg: str(pkg), pkgs))))

        if self._installer.check_available(pkgs):
            return True

        if self._installer.__class__ in Installer.NETWORK_INSTALLERS:
            self._logger.debug(u'Falling back to local installer')

            self._installer = LocalInstaller(self._h, self._root,
                                             self._db, self._logger)
            return self.check_available(pkgs)

        return False


class RedHat(BaseConverter):
    def __init__(self, h, root, guest, db, logger):
        super(RedHat, self).__init__(h, root, guest, db, logger)
        distro = h.inspect_get_distro(root)
        if (h.inspect_get_type(root) != u'linux' or
                h.inspect_get_distro(root) not in [u'fedora'] + RHEL_BASED):
            raise UnsupportedConversion()

    def _check_capability(self, name, installer):
        h = self._h
        root = self._root
        db = self._db

        arch = h.inspect_get_arch(root)
        check = []
        cap = db.match_capability(name, arch, h, root)
        if cap is None:
            self._logger.debug(u'No {} capability found for this root'.
                               format(name))
            return False

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
            for installed in installer.get_installed(pkg):
                if installed < target:
                    need = True
                if installed >= target:
                    need = False
                    continue
            if need:
                check.append(target)

        # Success if we've got nothing to check
        if len(check) == 0:
            return True

        return installer.check_available(check)


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

        installer = Installer(h, root, self._db, self._logger)

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

        if self._check_capability(u'virtio', installer):
            network.append((u'virtio-net', u'VirtIO'))
            block.append((u'virtio-blk', u'VirtIO'))
            console.append((u'virtio-serial', _(u'VirtIO Serial')))

        if self._check_capability(u'cirrus', installer):
            graphics.append((u'cirrus-vga', u'Cirrus'))

        if self._check_capability(u'qxl', installer):
            graphics.append((u'qxl-vga', u'Spice'))

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

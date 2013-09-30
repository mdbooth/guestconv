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

    @classmethod
    def from_guestfs_app(app):
        return Package(app[u'app2_name'],
                       epoch=str(app[u'app2_epoch']),
                       version=str(app[u'app2_version']),
                       release=str(app[u'app2_release']),
                       arch=str(app[u'app2_arch']))

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


def _remove_applications(h, pkgs):
    try:
        h.command([u'rpm', u'-e'] + list(pkgs))
    except GuestFSException as ex:
        self._logger.warn(_u(u'Failed to remove packages: {pkgs}').
                          format(u', '.join(pkg_names)))
        return False
    return True


class Hypervisor(object):
    NONE = 0
    INSTALLED = 1
    AVAILABLE = 2

    class NotAvailable(GuestConvException): pass

    def __init__(self, key, description, h, root, logger, apps):
        self.key = key
        self.description = description

        self._h = h
        self._root = root
        self._logger = logger

        if self._is_installed(apps):
            self.status = Hypervisor.INSTALLED
        elif self._is_available():
            self.status = Hypervisor.AVAILABLE
        else:
            self.status = Hypervisor.NONE

    def remove(self):
        if self.status != Hypervisor.INSTALLED:
            return
        else:
            self._remove()

    def install(self):
        if self.status == Hypervisor.INSTALLED:
            return
        elif self.status != Hypervisor.AVAILABLE:
            raise Hypervisor.NotAvailable()

        self._install()

    def is_available(self):
        return self.status in (Hypervisor.INSTALLED, Hypervisor.AVAILABLE)

    # Stubs

    def _is_installed(self, apps): return False
    def _is_available(self): return True
    def _remove(self): pass
    def _install(self): pass


class HVKVM(Hypervisor):
    def __init__(self, h, root, logger, apps):
        super(HVKVM, self).__init__(u'kvm', u'KVM', h, root, logger, apps)


class HVXenFV(Hypervisor):
    def __init__(self, h, root, logger, apps):
        super(HVXenFV, self).__init__(u'xenfv', _(u'Xen Fully Virtualised'),
                                      h, root, logger, apps)


def _xenpv_is_available(h, root):
    '''Determine whether the guest distro's vanilla kernel supports xen'''

    distro = h.inspect_get_distro(root)
    version = h.inspect_get_major_version(root)

    # Not 100% sure when Fedora kernels started supporting Xen, but 16
    # definitely did and hopefully nobody's using anything older than that
    # any more anyway
    return ((distro == u'fedora' and version >= 16) or

    # RHEL kernels have supported Xen since RHEL 6
            (distro in RHEL_BASED and version >= 6))


class HVXenPV(Hypervisor):
    def __init__(self, h, root, logger, apps):
        super(HVXenPV, self).__init__(u'xenpv', _(u'Xen Paravirtualised'),
                                      h, root, logger, apps)

    def _is_installed(self, apps):
        probe = re.compile(ur'kmod-xenpv(?:-.*)?$')
        self._xen = [str(Package.from_guestfs_app(i)) for i in apps
                     if probe.match(i[u'app2_name'])]

        return len(self._xen) > 0

    def _is_available(self):
        return _xenpv_is_available(self._h, self._root)

    def _remove(self):
        h = self._h

        if len(self._xen) == 0:
            return

        _remove_applications(h, self._xen)

        # kmod-xenpv modules may have been manually copied to other kernels.
        # Hunt them down and destroy them

        for xenpv in [i for i in h.find(u'/lib/modules')
                      if i.endswith(u'/xenpv')]:
            xenpv = u'/lib/modules' + xenpv

            if not h.is_dir(xenpv):
                continue

            # Check it's not owned by an installed application
            try:
                h.command([u'rpm', u'-qf', xenpv])
                continue
            except GuestFSException:
                pass

            h.rm_rf(xenpv)

        # rc.local may contain an insmod or modprobe of the xen-vbd driver
        if not h.is_file(u'/etc/rc.local'):
            return

        rc_local = h.read_lines(u'/etc/rc.local')
        probe = re.compile(ur'\b(?:insmod|modprobe)\b.*\bxen-vbd\b')
        rc_local_len = 0
        for i in range(len(rc_local)):
            if probe.search(rc_local[i]):
                rc_local[i] = u'# ' + rc_local[i]
            rc_local_len += len(rc_local) + 1
        h.write_file(u'/etc/rc.local', '\n'.join(rc_local) + '\n', rc_local_len)


class HVVBox(Hypervisor):
    def __init__(self, h, root, logger, apps):
        super(HVVBox, self).__init__(u'vbox', u'VirtualBox',
                                     h, root, logger, apps)

    def _is_installed(self, apps):
        h = self._h

        probe = re.compile(ur'virtualbox-guest-additions(?:-.*)$')
        self._vbox_apps = [str(Package.from_guestfs_app(i)) for i in apps
                           if probe.match(i[u'app2_name'])]

        self._vbox_uninstall = None
        config = u'/var/lib/VBoxGuestAdditions/config'
        if h.is_file(config):
            prefix = u'INSTALL_DIR'
            for line in h.read_lines(config):
                if line.startswith(prefix):
                    install_dir = line[len(prefix)::]
                    uninstall = install_dir + u'/uninstall.sh'
                    if h.is_file(uninstall):
                        self._vbox_uninstall = uninstall
                    else:
                        self._logger.warn(_(u'VirtualBox config at {path} says '
                                            u'INSTALL_DIR={installdir}, but '
                                            u"{uninstall} doesn't exist").
                                          format(path=config,
                                                 installdir=install_dir,
                                                 uninstall=uninstall))
                    break

        return len(self._vbox_apps) > 0 or self._vbox_uninstall is not None

    def _remove(self):
        h = self._h

        if len(self._vbox_apps) > 0:
            _remove_applications(h, self._vbox_apps)

        if self._vbox_uninstall is not None:
            try:
                h.command([self._vbox_uninstall])
                h.aug_load()
            except GuestFSException as ex:
                self._logger.warn(_(u'VirtualBox Guest Additions '
                                    u'were detected, but '
                                    u'uninstallation failed. The '
                                    u'error message was: {error}').
                                  format(error=ex.message))


class HVVMware(Hypervisor):
    def __init__(self, h, root, logger, apps):
        super(HVVMware, self).__init__(u'vmware', u'VMware',
                                       h, root, logger, apps)

    def _is_installed(self, apps):
        h = self._h

        self._vmw_repos = h.aug_match(u'/files/etc/yum.repos.d/*/*'
                ur"[baseurl =~ regexp('https?://([^/]+\.)?vmware\.com/.*')]")

        self._vmw_remove = []
        self._vmw_libs = []

        for app in apps:
            name = app[u'app2_name']
            if name.startswith(u'vmware-tools-libraries-'):
                self._vmw_libs.append(app)
            elif (name.startswith(u'vmware-tools-') or name == 'VMwareTools' or
                  name.startswith(u'kmod-vmware-tools-') or
                  name == u'VMwareTools'):
                self._vmw_remove.append(str(Package.from_guestfs_app(app)))

        return (len(self._vmw_repos) > 0 or
                len(self._vmw_remove) > 0 or
                len(self._vmw_libs) > 0)

    def _remove(self):
        h = self._h

        for repo in self._vmw_repos:
            h.aug_set(repo + u'/enabled', 0)
            try:
                h.aug_save()
            except GuestFSException as ex:
                augeas_error(h, ex)

        remove = False

        if len(self._vmw_libs) > 0:
            # It's important that we did aug_save() above, or resolvedep might
            # return the same vmware packages we're trying to get rid of
            libs = self._remove_libs()
        else:
            libs = []

        if len(self._vmw_remove) > 0 or len(libs) > 0:
            _remove_applications(h, chain(self._vmw_remove, libs))

        # VMwareTools may have been installed from tarball, in which case the
        # above won't detect it. Look for the uninstall tool, and run it if
        # it's present.
        #
        # Note that it's important we do this early in the conversion process,
        # as this uninstallation script naively overwrites configuration files
        # with versions it cached prior to installation.
        vmwaretools = u'/usr/bin/vmware-uninstall-tools.pl'
        if h.is_file(vmwaretools):
            try:
                h.command([vmwaretools])
            except GuestfsException as ex:
                self._logger.warn(_(u'VMware Tools was detected, but '
                                    u'uninstallation failed: {error}').
                                  format(error = ex.message))
            h.aug_load()

    def _remove_libs(self):
        h = self._h

        replaced = []

        with Network(h):
            for lib in self._vmw_libs:
                nevra = str(Package.from_guestfs_app(lib))
                name = lib[u'app2_name']

                # Get the list of provides for the library package.
                try:
                    provides = set([i.strip() for i in
                                    h.command_lines([u'rpm', u'-q',
                                                     u'--provides', nevra])

                                    # The packages explicitly provide
                                    # themselves.  Filter this out
                                    if name not in i])
                except GuestfsException as ex:
                    self._logger.warn(_(u'Error getting rpm provides for '
                                        u'{package}: {error}').
                                      format(package = nevra,
                                             error = ex.message))
                    continue

                # Install the dependencies with yum. We use yum explicitly
                # here, as up2date wouldn't work anyway and local install is
                # impractical due to the large number of required
                # dependencies out of our control.
                try:
                    alts = set([i.strip() for i in
                                h.command_lines(list(chain([u'yum', u'-q',
                                                            u'resolvedep'],
                                                           provides)))])
                except GuestfsException as ex:
                    self._logger.warn(
                        _(u'Error resolving depencies for '
                          u'{packages}: {error}').
                        format(packages = u', '.join(list(provides)),
                               error = ex.message))
                    continue

                if len(alts) > 0:
                    try:
                        h.command(u'yum', u'install', u'-y', list(alts))
                    except GuestfsException as ex:
                        self._logger.warn(
                            _(u'Error installing replacement packages for '
                              u'{package} ({replacements}): {error}').
                            format(package = nevra,
                                   replacements = u', '.join(list(alts)),
                                   error = ex.message))
                        continue

                replaced.append(nevra)

        return replaced


class HVCitrixFV(Hypervisor):
    def __init__(self, h, root, logger, apps):
        super(HVCitrixFV, self).__init__(u'citrixfv',
                                         _(u'Citrix Fully Virtualised'),
                                         h, root, logger, apps)

    def _is_installed(self, apps):
        h = self._h

        probe = re.compile(ur'xe-guest-utilities(?:-.*)$')
        self._citrix_utils = [str(Package.from_guestfs_app(i))
                              for i in apps
                              if probe.match(i[u'app2_name'])]

        return len(self._citrix_utils) > 0


class HVCitrixPV(Hypervisor):
    def __init__(self, h, root, logger, apps):
        super(HVCitrixPV, self).__init__(u'citrixpv',
                                         _(u'Citrix Paravirtualised'),
                                         h, root, logger, apps)

    def _is_installed(self, apps):
        h = self._h

        probe = re.compile(ur'xe-guest-utilities(?:-.*)$')
        self._citrix_utils = [str(Package.from_guestfs_app(i))
                              for i in apps
                              if probe.match(i[u'app2_name'])]

        return len(self._citrix_utils) > 0

    def _is_available(self):
        return _xenpv_is_available(self._h, self._root)

    def _remove(self):
        h = self._h

        _remove_applications(self._citrix_utils)

        # Installing these guest utilities automatically unconfigures ttys in
        # /etc/inittab if the system uses it. We need to put them back.

        # The entries in question are named 1-6, and will normally be active in
        # runlevels 2-5. They will be gettys. We could be extremely prescriptive
        # here, but allow for a reasonable amount of variation just in case.
        inittab = re.compile(ur'([1-6]):([2-5]+):respawn:(.*)')

        updated = 0
        for path in h.aug_match(u'/files/etc/inittab/#comment'):
            comment = h.aug_get(path)

            m = inittab.match(comment)
            if m is None:
                continue

            name = m.group(1)
            runlevels = m.group(2)
            process = m.group(3)

            if u'getty' not in process:
                continue

            # Create a new entry immediately after the comment
            h.aug_insert(path, name, 0)
            for field, value in [(u'runlevels', runlevels),
                                 (u'action', u'respawn'),
                                 (u'process', process)]:
                h.aug_set(u'/files/etc/inittab/{name}/{field}'.
                          format(name = name, field = field), value)

            # Create a variable to point to the comment node so we can delete it
            # later. If we deleted it here it would invalidate subsequent
            # comment paths returned by aug_match.
            h.aug_defvar(u'delete{}'.format(updated), path)

            updated += 1

        # Delete all replaced comments
        for i in range(updated):
            h.aug_rm(ur'$delete{i}'.format(i=i))

        try:
            h.aug_save()
        except GuestfsException as ex:
            augeas_error(h, ex)


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

        # Initialise supported drivers
        options = [
            (u'hypervisor', _(u'Hypervisor support'), []),
            (u'graphics', _(u'Graphics driver'), []),
            (u'network', _(u'Network driver'), [
                (u'e1000', u'Intel E1000'),
                (u'rtl8139', u'Realtek 8139')
            ]),
            (u'block', _(u'Block device driver'), [
                (u'ide-hd', u'IDE'),
                (u'scsi-hd', u'SCSI')
            ]),
            (u'console', _(u'System Console'), [
                (u'vc', _(u'Kernel virtual console')),
                (u'serial', _(u'Serial console'))
            ])
        ]

        drivers = {}
        for name, desc, values in options:
            drivers[name] = values

        def _missing_deps(name, missing):
            '''Utility function for reporting missing dependencies'''
            l = u', '.join([str(i) for i in missing])
            self._logger.info(_(u'Missing dependencies for {name}: {missing}')
                              .format(name=name, missing=l))

        # Detect supported hypervisors
        self._hypervisors = {}
        apps = h.inspect_list_applications2(root)
        for klass in [HVKVM,
                      HVXenPV, HVXenFV,
                      HVVBox,
                      HVVMware,
                      HVCitrixFV, HVCitrixPV]:
            hv = klass(h, root, self._logger, apps)
            if hv.is_available():
                self._hypervisors[hv.key] = klass
                drivers[u'hypervisor'].append((hv.key, hv.description))

        # Detect supported graphics hardware
        for driver, desc in [(u'qxl-vga', u'Spice'),
                             (u'cirrus-vga', u'Cirrus')]:
            deps = self._cap_missing_deps(driver)
            if len(deps) == 0:
                drivers[u'graphics'].append((driver, desc))
            else:
                _missing_deps(driver, deps)

        # Detect VirtIO
        virtio_deps = self._cap_missing_deps(u'virtio')
        if len(virtio_deps) == 0:
            drivers[u'network'].append((u'virtio-net', u'VirtIO'))
            drivers[u'block'].append((u'virtio-blk', u'VirtIO'))
            drivers[u'console'].append((u'virtio-serial', _(u'VirtIO Serial')))
        else:
            _missing_deps(u'virtio', virtio_deps)

        # Info section of inspection
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

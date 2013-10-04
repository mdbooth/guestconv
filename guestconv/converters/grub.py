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
from itertools import chain, ifilter, imap

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
                    return GrubEFI(device, h, root, converter, logger, cfg)
                else:
                    return Grub2EFI(device, h, root, converter, logger, cfg)

    # Look for grub legacy config
    for cfg in [u'/boot/grub/grub.conf', u'/boot/grub/menu.lst']:
        if h.is_file_opts(cfg, followsymlinks=True):
            return GrubBIOS(h, root, converter, logger, cfg)

    # Look for grub2 config
    GRUB2_CFG = u'/boot/grub2/grub.cfg'
    if h.is_file_opts(GRUB2_CFG, followsymlinks=True):
        return Grub2BIOS(h, root, converter, logger, GRUB2_CFG)

    raise BootLoaderNotFound()


def _find_boot(h, root):
    mounts = h.inspect_get_mountpoints(root)

    def _get_device(mp):
        part = mounts[mp]
        m = re.match(u'/dev/([a-z]*)[0-9]*$', part)
        if m is None:
            raise Exception(u'Unexpected guestfs partition {}'.format(part))
        return m.group(1)

    BOOT = u'/boot'
    if BOOT in mounts:
        return (_get_device(BOOT), BOOT)
    else:
        return (_get_device(u'/'), u'')


class GrubBase(object):
    '''Functions supported by grubby, and therefore common between grub legacy
    and grub2
    '''

    def __init__(self, name, device, fs_prefix,
                 h, root, converter, logger, cfg):
        self.name = name
        self.device = device

        self._fs_prefix = fs_prefix
        self._h = h
        self._root = root
        self._converter = converter
        self._logger = logger
        self._cfg = cfg

    def installed_on(self, device):
        if disk == self.device:
            self._logger.debug(u'Bootloader {} can convert {}'.
                               format(self.__class__, device))
            return True

        self._logger.debug(u"Bootloader {} installed on {} can't convert {}".
                           format(self.__class__, self.device, device))
        return False

    def get_initrd(self, path):
        for line in h.command_lines([u'grubby', u'--info', path]):
            m = re.match(u'^initrd=(\S+)', line)
            if m is not None:
                return m.group(1)

        raise ConversionError(
            _(u"grubby didn't return an initrd for kernel %(kernel)s") %
            {u'kernel': path})

    def _iter_kernels(self, default, all_kernels):
        '''Return all kernels with the default kernel first, duplicates and
        non-existent kernels removed, and all grub paths expanded to system
        paths'''

        kernels = all_kernels

        if default is not None:
            # Put the default at the beginning of the kernel list
            kernels = chain([default],
                            ifilter(lambda x: x != default, kernels))

        # Prepend the grub filesystem to paths if necessary
        if self._fs_prefix != '':
            kernels = imap(lambda x: self._fs_prefix + x, kernels)

        # Check that the returned kernel paths exist, and remove duplicates
        seen = set()
        def _check_and_uniq(path):
          if path in seen:
              return False

          seen.add(path)

          if not self._h.is_file_opts(path, followsymlinks=True):
              self._logger.warn(_(u"grub refers to {kernel}, which doesn't "
                                  "exist").format(kernel=path))
              return False

          return True

        return ifilter(_check_and_uniq, kernels)


class Grub(GrubBase):
    '''Methods for inspecting and manipulating grub legacy'''

    def iter_kernels(self):
        '''Return all kernels from grub.conf in the order that grub would try
        them'''

        h = self._h
        grub_conf = self._cfg

        def _get_default():
            '''Return the grub path of the default kernel, or None if there is
            no valid default kernel'''

            try:
                default_str = h.aug_get(u'/files{}/default'.format(grub_conf))
            except GuestFSException:
                return None # We don't care if there is no default

            try:
                default_int = int(default_str)
            except ValueError:
                self._logger.info(_(u'{path} contains invalid default: '
                                    u'{default').
                                    format(path=grub_conf, default=default_str))
                return None

            # Grub indices are zero-based, augeas is 1-based
            default_aug = (u'/files{}/title[{}]/kernel'.
                            format(grub_conf, default_int + 1))

            try:
                return h.aug_get(default_aug)
            except GuestFSException:
                self._logger.info(_(u'grub refers to default kernel {index}, '
                                    u'which doesn\'t exist').
                                  format(index=default_int))
                return None

        # Fetch the grub paths of all kernels in grub config
        all_kernels = imap(
            lambda x: h.aug_get(x),
            h.aug_match(u'/files{}/title/kernel'.format(grub_conf))
        )

        return self._iter_kernels(_get_default(), all_kernels)


class GrubBIOS(Grub):
    def __init__(self, h, root, converter, logger, cfg):

        # Find the path which needs to be prepended to paths in the grub config
        # to make them absolute
        (device, prefix) = _find_boot(h, root)

        super(GrubBIOS, self).__init__(u'grub-bios', device, prefix,
                                       h, root, converter, logger, cfg)

    def inspect(self):
        return {
            u'type': u'BIOS',
            u'name': self.name
        }


class GrubEFI(Grub):
    def __init__(self, device, h, root, converter, logger, cfg):
        super(GrubEFI, self).__init__(u'grub-efi', device,
                                      h, root, converter, logger, cfg)

    def inspect(self):
        return {
            u'type': u'EFI',
            u'name': self.name,
            u'replacement': {
                u'type': u'BIOS',
                u'name': u'grub-bios'
            }
        }

    def convert(self, target):
        if target != 'grub-bios':
            raise ConversionError(_(u'Cannot convert grub-efi bootloader to '
                                    u'{target}').format(target=target))

        grub_conf = u'/boot/grub/grub.conf'

        h = self._h
        h.cp(self._cfg, grub_conf)
        h.ln_sf(grub_conf, u'/etc/grub.conf')

        # Reload to push up grub.conf in its new location
        h.aug_load()

        h.command([u'grub-install', self.device])

        return GrubBIOS(self._h, self._root, self._converter, self._logger,
                        grub_conf)


class Grub2(GrubBase):
    def iter_kernels(self):
        '''Return all kernels from grub.conf in the order that grub would try
        them'''

        h = self._h

        def _list_menuentries():
            '''Return title and kernel for each menuentry in grub config, in
            order'''

            lines = iter(h.read_lines(self._cfg))
            for line in lines:
                # Is this a menu entry
                m = re.match(u"\s*menuentry\s+(?:'([^']*)')?", line)
                if m is None:
                    continue

                # Try to find a title
                title = m.group(1) # May be None

                # Try to find an open curly
                while re.search(u'{\s*$', line) is None:
                    try:
                        line = lines.next()
                    except StopIteration:
                        self._logger.warn(_(u'Unexpected EOF in {path}: '
                                            u'menuentry with no \'{\''))
                        return

                # line is now the line containing the close curly.
                # This for loop will continue to iterate starting at the line
                # following the close curly
                kernel = None
                for line in lines:
                    m = re.match(u'\s*linux\s+(\S+)\s', line)
                    if m is None:
                        if re.search(u'}\s*$', line):
                            break    
                        else:
                            continue

                    kernel = m.group(1)

                # We're now at either a close curly or EOF
                # title and kernel could both be None
                yield (title, kernel)

        # Scan the grub config looking for how the default entry is determined
        # We do this heuristically, because the way it really works is utterly
        # insane.
        #
        # N.B. We used to use the guest's installed grubby here, but older
        # versions of grubby were broken and didn't return the correct kernel.
        # As we would have to re-implement this for those older guests anyway,
        # we simply dispense with grubby entirely.
        #
        # If grub.cfg was written by grub2-mkconfig, it will probably contain
        # the following section:
        #
        # if [ "${next_entry}" ] ; then
        #    set default="${next_entry}"
        #    set next_entry=
        #    save_env next_entry
        #    set boot_once=true
        # else
        #    set default="${saved_entry}"
        # fi
        #
        # In this case, the default entry is read from grubenv, and is either
        # next_entry or saved_entry.
        #
        # However, many configurations seem to have this replaced with a simple:
        #
        # set default="0"
        #
        # In this case, grubenv is ignored, although the saved_entry in there
        # always seems to contain a bogus menuentry title anyway, which means
        # it's ignored. I am currently assuming that grubby is responsible for
        # this, although I can't be sure.
        #
        # The upstream grub source contains a 00-header which looks like it
        # would write the following:
        #
        # if cmostest $GRUB_BUTTON_CMOS_ADDRESS ; then
        #   set default="${GRUB_DEFAULT_BUTTON}"
        # else
        #   set default="${GRUB_DEFAULT}"
        # fi
        #
        # Where GRUB*_BUTTON will expand to either a numeric index, a title or,
        # more likely '${saved_entry}', which will again be read from grubenv.
        #
        # The following does not attempt to parse if statements as that would
        # require parsing shell syntax in a config file, which is utter
        # insanity. Instead, we look for the last 'set default=' in the config
        # file which isn't ${next_entry}. The reason for this is that next_entry
        # is only a temporary boot configuration. This is obviously not strictly
        # correct, but will handle all of the above cases. If any user is
        # inclined to do anything different, they're presumably already used to
        # everything being broken.
        def _get_default():
            def _resolve_default(default):
                # Is default an index or a menuentry title?
                try:
                    default_int = int(default)

                    # Get the kernel from the default'th menuentry
                    i = 0
                    for title, kernel in _list_menuentries():
                        if i == default_int:
                            return kernel
                        i += 1

                    self._logger.warn(_(u'Default kernel with index {index} '
                                        u'not found').format(index=default_int))
                except ValueError:
                    # Not an integer: find the menuentry with title == default
                    for title, kernel in _list_menuentries():
                        if title == default:
                            return kernel

                    self._logger.warn(_(u'Default kernel \'{title}\' not '
                                        u'found').format(title=default))

                return None

            # Find the last default in grub config
            default = None
            for line in h.read_lines(self._cfg):
                m = re.match(u'\s*set\s+default\s*=\s*"(.*)"', line)
                if m is None:
                    continue

                value = m.group(1)
                # Ignore ${next_entry}, as it's only a temporary boot config
                if value == u'${next_entry}':
                    continue

                default = value

            # If the default is the magic ${saved_entry}, look up the actual
            # value from grubenv
            SAVED = u'${saved_entry}'
            if default == SAVED:
                GRUBENV = u'/boot/grub2/grubenv'
                if not h.is_file_opts(GRUBENV, followsymlinks=True):
                    self._logger.warn(_(u'Grub 2 configuration lists default '
                                        u'boot option as \'{value}\', but '
                                        u'{path} does not exist')
                                      .format(value=SAVED, path=GRUBENV))
                    return None

                for line in h.read_lines(GRUBENV):
                    line.strip()
                    m = re.match(u'saved_entry=(.*)', line)
                    if m is not None:
                        return _resolve_default(m.group(1))

                self._logger.warn(_(u'Grub 2 configuration lists default boot '
                                    u'option as \'{value}\', but {path} does '
                                    u'not contain a \'{name}\' entry')
                                  .format(value=SAVED, path=GRUBENV,
                                          name=u'saved_entry'))
                return None

            return _resolve_default(default)

        # Fetch all kernels from grub config
        all_kernels = imap(lambda (title, kernel): kernel, _list_menuentries())

        # Filter out empty entries
        all_kernels = ifilter(lambda x: x is not None, all_kernels)

        return self._iter_kernels(_get_default(), all_kernels)


class Grub2BIOS(Grub2):
    def __init__(self, h, root, converter, logger, cfg):
        # Find the grub device
        device = None

        (device, prefix) = _find_boot(h, root)

        super(Grub2BIOS, self).__init__(u'grub2-bios', device, prefix,
                                        h, root, converter, logger, cfg)

    def inspect(self):
        return {
            u'type': u'BIOS',
            u'name': self.name
        }


class Grub2EFI(Grub2):
    def __init__(self, h, root, converter, logger, cfg):
        (bootfs_device, prefix) = _find_boot(h, root)

        # Check all devices for an EFI boot partition
        def _find_boot_device():
            for i in h.list_devices():
                try:
                    guid = h.part_get_gpt_type(i, 1)
                    if guid == u'C12A7328-F81F-11D2-BA4B-00A0C93EC93B':
                        return i
                except GuestFSException:
                    # Not EFI if partition isn't GPT
                    next

            raise BootLoaderNotFound()
        device = _find_boot_device()

        # Look for the EFI boot partition in mountpoints
        try:
            mp = h.mountpoints()[device + '1']
        except KeyError:
            logger.debug(u'Detected EFI bootloader with no mountpoint')
            raise BootLoaderNotFound()

        super(Grub2EFI, self).__init__(u'grub2-efi', device, prefix,
                                       h, root, converter, logger, cfg)

    def inspect(self):
        return {
            u'type': u'EFI',
            u'name': self.name,
            u'replacement': {
                u'type': u'BIOS',
                u'name': u'grub2-bios'
            }
        }

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
        h.part_set_gpt_type(self.device, 1,
                            u'21686148-6449-6E6F-744E-656564454649')

        # Delete the fstab entry for the EFI boot partition
        for node in h.aug_match(u"/files/etc/fstab/*[file = '/boot/efi']"):
            h.aug_rm(node)

        try:
            h.aug_save()
        except GuestfsException as ex:
            augeas_error(h, ex)

        GRUB2_BIOS_CFG = u'/boot/grub2/grub.cfg'

        h.command([u'grub2-install', self.device])
        h.command([u'grub2-mkconfig', u'-o', GRUB2_BIOS_CFG])

        return Grub2BIOS(h, self._root, self._converter, self._logger,
                         GRUB2_BIOS_CFG)

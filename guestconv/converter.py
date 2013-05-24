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
import guestconv.log

class RootMounted(object):

    """Execute a block of code with a specific libguestfs root mounted.

    Mount a root which was previously detected by inspection in the libguestfs
    handle, and initialise augeas in that root. Unmount the root on exit.

    :h: The libguestfs handle.
    :root: The libguestfs root to mount.

    """

    def __init__(self, h, root):
        self._h = h
        self._root = root

    def __enter__(self):
        h = self._h
        root = self._root
        mounts = sorted(h.inspect_get_mountpoints(root).iteritems(),
                        key=lambda entry: len(entry[0]))
        for mountpoint, device in mounts:
            h.mount_options('', device, mountpoint)

        h.aug_init('/', 1)

        return h

    def __exit__(self, type, value, tb):
        h = self._h
        h.umount_all()
        return False


class Converter(object):

    """Convert a guest's disk images(s) to run on a target hypervisor.

    A logging.Logger object *or* function may be passed in.  If a
    function is given, the function will receive all log messages
    (filtering of the messages is the caller's responsibility).  The
    function takes exactly two arguments: the first being an integer
    logging level (aligning with the constants in the python logging
    module, e.g., DEBUG=10, INFO=20, etc.) and the second being the
    log message itself.  Note that behind the scenes the function is
    wrapped in a handler and we still create a logging.Logger, but the
    caller does not need to worry about that (see guestconv/log.py for
    the implementation).

    If no logger object is provided, log messages are written to
    stderr and the threshold of log messages logged is WARNING unless
    the environment variable GUESTCONV_LOG_LEVEL is defined (one of
    NOTSET,DEBUG,INFO,WARNING,ERROR,CRITICAL).

    :param target: string indicating the hypervisor.
    :param db_paths: list of filenames (xml databases describing capabilities)
    :param logger: optional logging.Logger object or just a function

    """

    def __init__(self, target, db_paths, logger=None):
        self._h = guestfs.GuestFS(python_return_dict=True)
        self._h.set_network(True)
        self._inspection = None
        self._db = guestconv.db.DB(db_paths)
        self._target = target
        self._converters = {}
        self._logger = guestconv.log.get_logger_object(logger)
        # a less-than DEBUG logging message (since 10 == DEBUG)
        self._logger.log( 5 , u'Converter __init_() completed' )

    def __del__(self):
        """Close the libguestfs handle when garbage collected."""

        self._h.close()

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

    def inspect(self):
        """Inspect the guest image(s) and return conversion options.

        Inspect the drive, record needed transformations (to
        make the OS(es) bootable by the target hypervisor) in the XML
        document which is returned to the caller.  Gracefully handles
        multi-boot (meaning there are multiple "root" partitions and
        possibly multi-OS'es).

        This is a read-only operation.

        :returns:  XML document (a string)

        """
        if self._inspection:
            return self._inspection

        h = self._h

        h.launch()
        guestfs_roots = h.inspect_os()

        bootloaders = {}
        roots = {}

        builder = ET.TreeBuilder()
        builder.start(u'guestconv', {})

        for root in guestfs_roots:
            for klass in guestconv.converters.all:
                converter = None
                try:
                    converter = klass(h, self._target, root,
                                      self._db, self._logger)
                except guestconv.exception.UnsupportedConversion:
                    self._logger.debug(
                        u'Converter %s unsupported for root %s' % \
                              (converter, root))
                    continue

                with RootMounted(h, root):
                    (root_bl, root_info, root_options) = converter.inspect()

                self._converters[root] = converter

                bootloaders.update(root_bl)

                builder.start(u'root', {u'name': root})

                builder.start(u'info', {})
                def build_info(i):
                    for name, data in i.iteritems():
                        builder.start(name, {})
                        if isinstance(data, dict):
                            build_info(data)
                        else:
                            builder.data(str(data))
                        builder.end(name)
                build_info(root_info)
                builder.end(u'info')

                builder.start(u'options', {})
                for option in root_options:
                    attrs = {
                        u'name': option[0],
                        u'description': option[1],
                    }
                    builder.start(u'option', attrs)
                    for val_name, val_desc in option[2]:
                        builder.start(u'value', {u'description': val_desc})
                        builder.data(val_name)
                        builder.end(u'value')
                    builder.end(u'option')
                builder.end(u'options')

                builder.end(u'root')

                # We only want 1 converter to run
                break

        builder.start(u'boot', {})
        for disk, props in bootloaders.iteritems():
            attrs = {
                u'disk': disk,
                u'type': props[u'type'],
            }
            name = props[u'name']
            if name is not None:
                attrs[u'name'] = name
            if u'replacement' in props:
                attrs[u'replacement'] = props[u'replacement']
            builder.start(u'loader', attrs)

            if u'options' in props:
                for option in props[u'options']:
                    attrs = {
                        u'type': option[u'type'],
                        u'name': option[u'name']
                    }
                    builder.start(u'loader', attrs)
                    builder.end(u'loader')

            builder.end(u'loader')
        builder.end(u'boot')

        builder.end(u'guestconv')

        xml = builder.close()
        self._inspection = ET.tostring(xml, encoding='utf8')

        return self._inspection

    def convert(self, desc):
        """Convert the guest image(s).

        Do the conversion indicated by desc, an XML document.  The virtual image
        will be modified in place. Note that desc may simply be the XML returned
        by inspect(), or a modified version of it.

        :param desc:  XML document string
        :returns:  TODO

        """
        dom = ET.fromstring(desc)

        bootloaders = {}
        roots = {}

        for loader in dom.xpath(u'/guestconv/boot/loader'):
            disk = loader.get(u'disk')
            props = {
                u'type': loader.get(u'type')
            }
            replacement = loader.get(u'replacement')
            if replacement is not None:
                props[u'replacement'] = replacement

            bootloaders[disk] = props

        for root in dom.xpath(u'/guestconv/root'):
            name = root.get(u'name')

            try:
                converter = self._converters[name]
            except KeyError:
                raise guestconv.exception.InvalidConversion \
                    (_(u'root %(root)s specified in desc does not exist') %
                     {u'root': name})

            devices = []
            for device in root.xpath(u'device'):
                devices.append({
                    u'type': device.get(u'type'),
                    u'id': device.get(u'id'),
                    u'driver': device.get(u'driver')
                })

            with RootMounted(self._h, name):
                converter.convert(bootloaders, devices)

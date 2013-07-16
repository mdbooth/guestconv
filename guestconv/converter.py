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
from urlparse import urlparse

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

    """Convert a guest's disk images(s) to run on a new hypervisor.

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

    :param db_paths: list of filenames (xml databases describing capabilities)
    :param logger: optional logging.Logger object or just a function

    """

    def __init__(self, guest, db_paths, logger=None):
        self._h = guestfs.GuestFS(python_return_dict=True)
        self._h.set_network(True)
        self._inspection = None
        self._db = guestconv.db.DB(db_paths)
        self._converters = {}
        self._logger = guestconv.log.get_logger_object(logger)

        try:
            desc = ET.fromstring(guest)
        except lxml.etree.ParseError as ex:
            raise ValueError(_(u'Invalid guest XML: {message}').
                             format(message=ex.message))

        def _get_single_value(name):
            for v in desc.xpath(u'/guestconv/{name}[1]'.format(name=name)):
                return v.text
            return None

        def _get_single_int(name):
            v = _get_single_value(name)
            if v is None:
                return None
            try:
                return int(v)
            except ValueError:
                raise ValueError(_(u'Invalid guest XML: value for {name} '
                                   u'({value}) is not a valid integer').
                                 format(name=name, value=v))

        controllers = []
        self._guest = {
            u'cpus': _get_single_int(u'cpus'),
            u'memory': _get_single_int(u'memory'),
            u'arch': _get_single_value(u'arch'),
            u'controllers': controllers
        }

        # a = 1
        # z = 26
        # aa = 27
        # zz = 702
        # aaa = 703
        def _index_to_disk_name(i, name=u''):
            if i == 0:
                return name

            mod = i % 26
            if mod == 0:
                mod = 26

            # ord(u'a') - 1 = 96
            return _index_to_disk_name((i-mod)/26, chr(96+mod)+name)

        # Disk and controller index counters
        guestfs_d = 0
        ide_c = 0
        ide_d = 0
        scsi_d = 0
        cciss_c = 0
        cciss_d = 0

        for c in desc.xpath(u'/guestconv/controller'):
            typ = c.get(u'type')

            disks = []
            controllers.append({
                u'type': typ,
                u'disks': disks
            })

            for d in c.xpath(u'disk'):
                format = d.get(u'format')
                url = urlparse(d.text)

                hint = None
                if typ == u'ide':
                    ide_d += 1
                    hint = u'ide' + _index_to_disk_name(ide_c*4 + ide_d)
                elif typ == u'scsi':
                    scsi_d += 1
                    hint = u'scsi' + _index_to_disk_name(scsi_d)
                elif typ == u'cciss':
                    hint = u'cciss/c{c}d{d}'.format(c=cciss_c, d=cciss_d)
                    cciss_d += 1

                protocol = url.scheme
                if protocol == u'':
                    protocol = u'file'

                server = url.netloc
                if server == u'':
                    server = None

                path = url.path
                if path == u'':
                    path = None

                guestfs_d += 1
                disks.append({
                    u'guestfs': u'sd' + _index_to_disk_name(guestfs_d),
                    u'format': format,
                    u'protocol': protocol,
                    u'server': server,
                    u'path': path,
                    u'hint': hint
                })

                self._h.add_drive_opts(path, protocol=protocol, server=server,
                                       format=format, name=hint)

            if typ == u'ide':
                ide_c += 1
                ide_d = 0
            elif typ == u'cciss':
                cciss_c += 1
                cciss_d = 0

        # a less-than DEBUG logging message (since 10 == DEBUG)
        self._logger.log( 5 , u'Converter __init_() completed' )

    def inspect(self):
        """Inspect the guest image(s) and return conversion options.

        Inspect the drive, and return available transformations as an XML
        document.

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
                    converter = klass(h, root, self._guest,
                                      self._db, self._logger)
                except guestconv.exception.UnsupportedConversion:
                    self._logger.debug(
                        u'Converter {} unsupported for root {}'
                        .format(klass.__name__, root))
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

        try:
            dom = ET.fromstring(desc)
        except lxml.etree.ParseError as ex:
            raise ValueError(_(u'Invalid conversion description: {message}').
                             format(message=ex.message))

        bootloaders = {}
        roots = {}

        for loader in dom.xpath(u'/guestconv/boot/loader'):
            disk = loader.get(u'disk')
            replacement = None
            for replacement_e in loader.iterchildren():
                replacement = replacement_e.text
                break
            bootloaders[disk] = replacement

        for root in dom.xpath(u'/guestconv/root'):
            rootname = root.get(u'name')

            try:
                converter = self._converters[rootname]
            except KeyError:
                raise guestconv.exception.InvalidConversion \
                    (_(u'root {root} specified in desc does not exist').
                     format(root=rootname))

            options = {}
            for option in root.xpath(u'options/option'):
                optname = option.get(u'name')

                value = None
                for value_e in option.iterchildren():
                    value = value_e.text
                    break

                if value is None:
                    raise guestconv.exception.InvalidConversion \
                        (_(u'option {option} in root {root} does not have a '
                           u'value').format(option=optname, root=rootname))

                options[optname] = value

            with RootMounted(self._h, name):
                converter.convert(bootloaders, options)

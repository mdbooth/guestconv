#!/usr/bin/python
#
# test/run.py load unit test suits and run them
#
# (C) Copyright 2013 Red Hat Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License, Version 2,
# as published by the Free Software Foundation
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import env

import errno
import glob
import guestfs
import itertools
import jinja2
import os
import os.path
import re
import subprocess
import sys
import tempfile
import unittest

from urlparse import urlparse

import lxml.etree as ET

import ksbuilder
import guestconv
import guestconv.converters.redhat as redhat

from guestconv.converter import Converter
from guestconv.converter import RootMounted
from images import *

# requires root privs:
OZ_BIN        = '/usr/bin/oz-install'
VIRT_INST_BIN = '/usr/bin/virt-install'
VIRSH_BIN     = '/usr/bin/virsh'
QEMU_IMG_BIN  = '/usr/bin/qemu-img'
SSH_BIN       = '/usr/bin/ssh'
LIBVIRT_LEASES_FILE = '/var/lib/libvirt/dnsmasq/default.leases'

TDL_DIR = os.path.join(env.topdir, u'test', u'data', u'tdls')
KS_DIR = os.path.join(env.topdir, u'test', u'data', u'ks')

jinja = jinja2.Environment(
    loader=jinja2.FileSystemLoader(env.topdir)
)

def run_cmd(cmd):
    out = tempfile.TemporaryFile()
    popen = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT)
    status = popen.wait()
    if status != 0:
        out.seek(0)
        raise RuntimeError('Command returned status {status}: {cmd}: {output}'.
                           format(status=status, cmd=' '.join(cmd),
                                  output=out.read().strip()))

    out.seek(0)
    return out.read().strip()


def logger(level, msg):
    try:
        log_level = int(os.environ['TEST_LOG_LEVEL'])
    except KeyError, ValueError:
        return

    if level >= log_level:
        print msg


class CmpXMLNoOrderingError(RuntimeError):
    def __init__(self, msg, depth):
        self.depth = depth
        super(CmpXMLNoOrderingError, self).__init__(msg)


def cmpXMLNoOrdering(x1, x2):
    """Compare 2 XML documents, ignoring the ordering of attributes and
    elements, and whitespace surrounding text nodes"""

    def _format_node(n):
        attrs = itertools.imap(lambda x: u'{key}="{value}"'
                                         .format(key=x[0], value=x[1]),
                               n.attrib.iteritems())
        return u'<{name} {attrs}>'.format(name=n.tag, attrs=u' '.join(attrs))

    def cmpNode(n1, n2, depth=1):
        if n1.tag != n2.tag:
            raise CmpXMLNoOrderingError(u'Element names differ: {}, {}'
                                        .format(n1.tag, n2.tag), depth)

        if n1.attrib != n2.attrib:
            raise CmpXMLNoOrderingError(
                u'Attributes of element {} differ: {}, {}'
                .format(_format_node(n1), n1.attrib, n2.attrib),
                depth)

        if n1.text is None:
            n1.text = ''
        else:
            n1.text = n1.text.strip()
        if n2.text is None:
            n2.text = ''
        else:
            n2.text = n2.text.strip()

        if n1.text != n2.text:
            raise CmpXMLNoOrderingError(
                u'Text of element {} differs: "{}" != "{}"'
                .format(_format_node(n1), n1.text, n2.text), depth + 1)

        def cmpChildren(n1, n2, depth):
            c1 = set(n1.getchildren())
            c2 = set(n2.getchildren())

            if len(c1) != len(c2):
                raise CmpXMLNoOrderingError(
                    u'Elements have different number of children: {}'
                    .format(_format_node(n1)),
                    depth)

            if len(c1) == 0:
                return True

            def _find_in_set(n, s, depth):
                deepest = None
                for i in s:
                    try:
                        if cmpNode(n, i, depth):
                            s.remove(i)
                            return
                    except CmpXMLNoOrderingError as err:
                        if deepest is None or err.depth > deepest.depth:
                            deepest = err
                raise deepest

            for i in c1:
                _find_in_set(i, c2, depth)
            return True

        return cmpChildren(n1, n2, depth + 1)

    return cmpNode(ET.fromstring(x1), ET.fromstring(x2))


def make_image_test(name, img, expected_root=None, expected_options=None,
                    *extra_methods):
    """Test inspection of an image"""

    def setUp(self):
        self.img = image_for(img)
        self.img.converter.inspect()

    def testInspect(self):
        inspected = ET.fromstring(self.img.converter.inspect())

        root = inspected.xpath(u"/guestconv/root[@name='{root}']"
                               .format(root=expected_root))
        self.assertEqual(len(root), 1,
                        u'Expected to find root: {expected}\n{xml}'
                        .format(expected=expected_root,
                                xml=ET.tostring(inspected)))
        root = root[0]

        options = root.xpath(u'options')
        self.assertEqual(len(options), 1,
                        u'No options in returned inspection xml')
        options = options[0]

        for name in expected_options:
            values = expected_options[name]

            option = options.xpath(u"option[@name='{}']".format(name))
            self.assertEqual(len(option), 1, u'No {} option'.format(name))
            option = option[0]

            for value in values:
                v = option.xpath(u"value[. = '{}']".format(value))
                self.assertEqual(len(v), 1,
                                u'value {} not found for option {}'.
                                format(value, name))

    methods = { 'setUp': setUp }
    if expected_root is not None and expected_options is not None:
        methods['testInspect'] = testInspect

    for method_set in extra_methods:
        methods.update(method_set)

    return unittest.skipUnless(os.path.exists(img),
                               '{img} does not exist'.format(img=img))(
        type(name, (unittest.TestCase,), methods))

def _render_template(path, params):
    jtpl = jinja.get_template(os.path.relpath(path, env.topdir))

    # Create a temporary file containing the rendered template
    rendered = tempfile.NamedTemporaryFile(prefix='gc.')
    rendered.write(jtpl.render(**params))

    # Ensure we've flushed the contents
    rendered.flush()
    os.fsync(rendered)

    return rendered

class TestTDLTemplate:
    def __init__(self, template):
        self.template = template
        self.name = os.path.basename(template).replace('.tdl.tpl', '')
        pass

    # render a tdl from this template
    def render(self, params={}):
        tdlf = _render_template(self.template, params)

        # Store a reference to the temporary file in the returned TestTDL to
        # ensure they are garbage collected together
        tdl = TestTDL(tdlf.name, self.name)
        tdl._tempfile = tdlf

        return tdl


class TestTDL:
    def __init__(self, tdl, name):
        self.tdl = tdl
        self.name = name
        pass

    # build the tdl into an image
    def build(self):
        # Ensure the image directory exists
        try:
            os.makedirs(IMG_DIR)
        except OSError as ex:
            if ex.errno == errno.EEXIST and os.path.isdir(IMG_DIR):
                pass
            else:
                raise ex

        img = os.path.join(IMG_DIR, self.name+'.img')
        if os.path.exists(img):
            print "image %s exists, skipping creation" % img

        else:
            print "building image %s" % img
            run_cmd([OZ_BIN, '-t', '3600', '-s', img, '-d3', '-u',
                             os.path.join(TDL_DIR, self.tdl)])

        return img
 

class TestImage:
    def launch(self):
        install = [VIRT_INST_BIN, '--connect', 'qemu:///system',
                                  '--name', self.name, '--ram', '1024',
                                  '--vcpus', '1', '--accelerate',
                                  '--boot', 'hd', '--import']

        for ovl in self._ovls:
            install.append('--disk')
            install.append(ovl.name)

        run_cmd(install)

        return TestInstance(name, self)

    def guestfs_handle(self):
        h = guestfs.GuestFS(python_return_dict=True)
        for ovl in self._ovls:
            h.add_drive(ovl.name)
        return h

    def __init__(self, name, *images):
        self.name = name

        # We store a reference to the overlays to ensure they aren't garbage
        # collected before the TestImage
        self._ovls = []

        guest = ET.fromstring('''
        <guestconv>
            <cpus>1</cpus>
            <memory>1073741824</memory>
            <arch>x86_64</arch>
            <controller type='scsi'/>
        </guestconv>
        ''')

        (controller,) = guest.xpath('/guestconv/controller')

        # Create a qcow2 overlay for each image and add it to the converter
        for img in images:
            ovl = tempfile.NamedTemporaryFile(prefix='guestconv-test.')
            run_cmd([QEMU_IMG_BIN, 'create', '-f', 'qcow2',
                                   '-o', 'backing_file='+img, ovl.name])
            self._ovls.append(ovl)

            disk = controller.makeelement('disk', attrib={'format': 'qcow2'})
            disk.text='file://{}'.format(os.path.abspath(ovl.name))
            controller.append(disk)

        self.converter = Converter(ET.tostring(guest),
                                   ['%s/conf/guestconv.db' % env.topdir],
                                   logger)


class TestInstance:
    def __init__(self, name, image):
        self.name  = name
        self.image = image

        # retrieve instance mac
        self.xml = run_cmd([VIRSH_BIN, '-c', 'qemu:///system',
                                       'dumpxml', name])
        xmldoc = ET.fromstring(self.xml)
        self.mac = xmldoc.find('./devices/interface/mac')
        self.mac = self.mac.get('address')

        # retrieve instance ip
        with open(LIBVIRT_LEASES_FILE, 'r') as leases:
            for line in leases:
              m = re.match("[^\s]*\s*%s\s*([^\s]*).*" % self.mac, line)
              if m:
                self.ip = m.group(1)
                break

    def ssh_cmd(self, cmd):
        run_cmd([SSH_BIN, '-i', 'test/data/key',
                  "-o", "ServerAliveInterval=30",
                  "-o", "StrictHostKeyChecking=no",
                  "-o", "UserKnownHostsFile=/dev/null",
                  "-o", "PasswordAuthentication=no",
                  ("guest@%s" % self.ip), cmd])


def image_for(image):
    return TestImage(image.replace('.img', ''), image)


def build_tdl(name):
    tdl = os.path.join(TDL_DIR, name+'.tdl')
    TestTDL(tdl, name).build()


def build_tpl(name, props):
    tpl_path = os.path.join(TDL_DIR, name+'.tdl.tpl')
    tpl = TestTDLTemplate(tpl_path)
    tpl.render(props).build()

def read_props(path, defaults={}):
    props = defaults

    try:
        with open(path) as f:
            for line in f:
                key, value = line.strip().split('=')
                props[key] = value
    except IOError as ex:
        if ex.errno != errno.ENOENT:
            raise

    return props

def build_ks(name, props):
    props_path = os.path.join(KS_DIR, name + u'.props')
    props_rendered = _render_template(props_path, props)

    ks_props = read_props(props_rendered.name)

    # Filter out and ignore unknown properties
    args = dict((k, v) for k, v in ks_props.items()
                if k in [u'ks', u'iso', u'url',
                         u'image_size', u'os_variant', u'loader'])

    # Ensure manadatory properties are present
    if u'ks' not in args:
        raise RuntimeError(u'{path} does not define ks'
                           .format(path=props_path))

    # Can't have both iso and url
    if u'iso' in args and u'url' in args:
        raise RuntimeError(u'{path} defines both iso and url'
                           .format(path=props_path))

    # ks is relative to KS_DIR, and is a template
    ks = _render_template(os.path.join(KS_DIR, args[u'ks']), props)
    args[u'ks'] = ks.name

    if u'iso' in args:
        # Fetch iso from iso_repository
        iso = urlparse(args[u'iso'])
        if iso.scheme != u'file':
            raise RuntimeError(u'Only support installation from local iso')
        args[u'iso'] = iso.path

        ksbuilder.build_iso(name, **args)
    elif u'url' in args:
        ksbuilder.build_url(name, **args)
    else:
        raise RuntimeError(u'{path} must specify either iso or url'
                           .format(path=props_path))

if __name__ == '__main__':
    tdls = map(lambda x: os.path.basename(x).replace('.tdl', ''),
               glob.glob(os.path.join(TDL_DIR, '*.tdl')))
    tpls = map(lambda x: os.path.basename(x).replace('.tdl.tpl', ''),
               glob.glob(os.path.join(TDL_DIR, '*.tdl.tpl')))
    ks = map(lambda x: os.path.basename(x).replace('.props', ''),
             glob.glob(os.path.join(KS_DIR, '*.props')))

    cmd = sys.argv[1]

    if cmd == 'list':
        for i in itertools.chain(tdls, tpls, ks):
            print i

    elif cmd == 'build':
        tgt = sys.argv[2]
        props = read_props(os.path.join(env.topdir, u'test/local.props'),
            {
                'fedora_mirror': 'http://download.fedoraproject.org/pub/fedora/linux',
                'ubuntu_mirror': 'http://mirrors.us.kernel.org/ubuntu-releases',
                'iso_repository': 'file://'
            }
        )

        for arg in sys.argv[3:]:
            key, value = arg.split('=')
            props[key] = value

        if tgt == 'all':
            for i in tdls:
                build_tdl(i)
            for i in tpls:
                build_tpl(i, props)

        elif tgt in tdls:
            build_tdl(tgt)

        elif tgt in tpls:
            build_tpl(tgt, props)

        elif tgt in ks:
            build_ks(tgt, props)

        else:
            print "Target {} doesn't exist".format(tgt)
            sys.exit(1)

    else:
        print "Invalid command: {}".format(cmd)

    sys.exit(0)

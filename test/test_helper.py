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

import xml.etree.ElementTree as et

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

TDL_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                       'data', 'tdls')

jinja = jinja2.Environment(
    loader=jinja2.FileSystemLoader('{}/test/data/tdls'.format(env.topdir))
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

class TestTDLTemplate:
    defaults = {
        'fedora_mirror': 'http://download.fedoraproject.org/pub/fedora/linux',
        'ubuntu_mirror': 'http://mirrors.us.kernel.org/ubuntu-releases',
        'iso_repository': 'file://'
    }

    def __init__(self, template):
        self.template = os.path.basename(template)
        self.name = self.template.replace('.tdl.tpl', '')
        pass

    # render a tdl from this template
    def render(self, params={}):
        print "rendering template {}".format(self.template)
        jtpl = jinja.get_template(self.template)

        # Merge passed-in params with defaults, with passed-in taking precedence
        render_args = dict(itertools.chain(TestTDLTemplate.defaults.items(),
                                           params.items()))

        # Create a temporary file containing the rendered tdl
        # Note bufsize=0 required to ensure data is written before oz tries to
        # read it
        tdlf = tempfile.NamedTemporaryFile(prefix='guestconv-test.', bufsize=0)
        tdlf.write(jtpl.render(**render_args))

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
            run_cmd([OZ_BIN, '-t', '3600', '-s', img, '-d3',
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

    def inspect(self):
        return self.converter.inspect()

    def list_kernels(self):
        with RootMounted(self.converter._h, '/dev/VolGroup00/LogVol00'):
            grub = redhat.Grub2BIOS(
                self.converter._h, '/dev/VolGroup00/LogVol00', logger)
            return grub.list_kernels()

    def __init__(self, name, *images):
        self.name = name
        self.converter = Converter('rhev',
                                   ['%s/conf/guestconv.db' % env.topdir],
                                   logger)

        # We store a reference to the overlays to ensure they aren't garbage
        # collected before the TestImage
        self._ovls = []

        # Create a qcow2 overlay for each image and add it to the converter
        for img in images:
            ovl = tempfile.NamedTemporaryFile(prefix='guestconv-test.')
            run_cmd([QEMU_IMG_BIN, 'create', '-f', 'qcow2',
                                   '-o', 'backing_file='+img, ovl.name])
            self._ovls.append(ovl)

            self.converter.add_drive(ovl.name)


class TestInstance:
    def __init__(self, name, image):
        self.name  = name
        self.image = image

        # retrieve instance mac
        self.xml = run_cmd([VIRSH_BIN, '-c', 'qemu:///system',
                                       'dumpxml', name])
        xmldoc = et.fromstring(self.xml)
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


class TestHelper:
    @classmethod
    def image_for(cls, image):
        name = image.replace('.img', '')
        return TestImage(name, image)

def build_tdl(name):
    tdl = os.path.join(TDL_DIR, name+'.tdl')
    TestTDL(tdl, name).build()

def build_tpl(name, params):
    tpl_path = os.path.join(TDL_DIR, name+'.tdl.tpl')
    tpl = TestTDLTemplate(tpl_path)
    tpl.render(params).build()

if __name__ == '__main__':
    tdls = map(lambda x: os.path.basename(x).replace('.tdl', ''),
               glob.glob(os.path.join(TDL_DIR, '*.tdl')))
    tpls = map(lambda x: os.path.basename(x).replace('.tdl.tpl', ''),
               glob.glob(os.path.join(TDL_DIR, '*.tdl.tpl')))

    cmd = sys.argv[1]

    if cmd == 'list':
        for i in itertools.chain(tdls, tpls):
            print i

    elif cmd == 'build':
        tgt = sys.argv[2]
        params = {}
        for arg in sys.argv[3:]:
            key, value = arg.split('=')
            params[key] = value

        if tgt == 'all':
            for i in tdls:
                build_tdl(i)
            for i in tpls:
                build_tpl(i, params)

        elif tgt in tdls:
            build_tdl(tgt)

        elif tgt in tpls:
            build_tpl(tgt, params)

        else:
            print "Target {} doesn't exist".format(tgt)
            sys.exit(1)

    else:
        print "Invalid command: {}".format(cmd)

    sys.exit(0)

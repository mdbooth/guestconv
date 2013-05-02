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

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))

import errno
import glob
import os.path
import re
import tempfile
import subprocess
import jinja2

import xml.etree.ElementTree as et

import guestconv
from guestconv.converter import Converter
from guestconv.converter import RootMounted
import guestconv.converters.redhat
from images import *

topdir = os.path.join(os.path.dirname(__file__), os.pardir)

# requires root privs:
OZ_BIN        = '/usr/bin/oz-install'
VIRT_INST_BIN = '/usr/bin/virt-install'
VIRSH_BIN     = '/usr/bin/virsh'
QEMU_IMG_BIN  = '/usr/bin/qemu-img'
SSH_BIN       = '/usr/bin/ssh'
LIBVIRT_LEASES_FILE = '/var/lib/libvirt/dnsmasq/default.leases'

TDL_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data', 'tdls')

jinja = jinja2.Environment(loader=jinja2.FileSystemLoader('test/data/tdls'))

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
    # In general, we're not interested in log output during test runs
    pass

class TestTDLTemplate:
    default_args = { 'name' : 'template_tdl',
                     'description' : 'template tdl',
                     'os' : { 'name' : 'Fedora',
                              'version' : '17',
                              'arch'    : 'x86_64',
                              'install_url' : 'http://download.fedoraproject.org/pub/fedora/linux/releases/17/Fedora/x86_64/os/'
                    }}

    def __init__(self, template):
        self.template = os.path.basename(template)
        self.tdl = os.path.join(IMG_DIR, self.template.replace(".tpl", ""))
        pass

    # render a tdl from this template
    def render(self, **kwargs):
        print "rendering template %s to tdl %s" % (self.template, self.tdl)
        jtpl = jinja.get_template(self.template)
        render_args = dict(TestTDLTemplate.default_args.items() + kwargs.items())
        tdl = jtpl.render(**render_args)
        with open(self.tdl, 'w') as tdlf:
            tdlf.write(tdl)

        # TODO write to template file
        return TestTDL(self.tdl)

class TestTDL:
    def __init__(self, tdl):
        self.tdl = tdl
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

        image = os.path.splitext(self.tdl)[0]
        image = os.path.split(image)[-1]
        image = os.path.join(IMG_DIR, image + ".img")
        if os.path.exists(image):
            print "image %s exists, skipping creation" % image

        else:
            print "building image %s" % image
            run_cmd([OZ_BIN, '-t', '3600', '-s', image, '-d3',
                             os.path.join(TDL_DIR, self.tdl)])

        return image
 

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

    def inspect(self):
        return self.converter.inspect()

    def list_kernels(self):
        with RootMounted(self.converter._h, '/dev/VolGroup00/LogVol00'):
            grub = guestconv.converters.redhat.Grub2BIOS(
                self.converter._h, '/dev/VolGroup00/LogVol00', logger)
            return grub.list_kernels()

    def __init__(self, name, *images):
        self.name = name
        self.converter = Converter('rhev', ['%s/conf/guestconv.db' % topdir],
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

if __name__ == '__main__':
    if not os.path.isfile(OZ_BIN) or not os.access(OZ_BIN, os.X_OK):
        print "oz not found, skipping image generation"
        sys.exit(1)

    for tdlf in glob.glob(os.path.join(TDL_DIR, '*.tdl')):
        TestTDL(tdlf).build()

    for tdlf in glob.glob(os.path.join(TDL_DIR, '*.tpl')):
        TestTDLTemplate(tdlf).render().build()

    sys.exit(0)

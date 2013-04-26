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

import errno
import os
import os.path
import re
import tempfile
import subprocess

import guestconv

import xml.etree.ElementTree as et
from guestconv.converter import Converter
from guestconv.converter import RootMounted
import guestconv.converters.redhat

topdir = os.path.join(os.path.dirname(__file__), os.pardir)

# requires root privs:
OZ_BIN        = '/usr/bin/oz-install'
VIRT_INST_BIN = '/usr/bin/virt-install'
VIRSH_BIN     = '/usr/bin/virsh'
QEMU_IMG_BIN  = '/usr/bin/qemu-img'
SSH_BIN       = '/usr/bin/ssh'
LIBVIRT_LEASES_FILE = '/var/lib/libvirt/dnsmasq/default.leases'

TDL_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data', 'tdls')
IMG_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data', 'images')

def run_cmd(cmd):
    stdoutf = tempfile.TemporaryFile()
    popen = subprocess.Popen(cmd, stdout=stdoutf, stderr=stdoutf)
    popen.wait()
    stdoutf.seek(0)
    stdout = stdoutf.read()
    stdoutf.close()
    return stdout

def build_tdl(tdl):
    # Ensure the image directory exists
    try:
        os.makedirs(IMG_DIR)
    except OSError as ex:
        if ex.errno == errno.EEXIST and os.path.isdir(IMG_DIR):
            pass
        else:
            raise ex

    image   = os.path.join(IMG_DIR, tdl.replace("tdl", "img"))
    if os.path.exists(image):
        print "image %s exists, skipping creation" % image
        return TestImage('rhev', image)

    print run_cmd([OZ_BIN, "-t", "3600", "-s", image, os.path.join(TDL_DIR, tdl)])

    return TestImage('rhev', image)

def logger(level, msg):
    print msg

class TestImage:
    def close(self):
        if self.drive:
            self.drive.close()

    def open(self):
        if self.drive_name:
            self.converter.add_drive(self.drive_name)

    def snapshot(self, name):
        stdout = run_cmd([QEMU_IMG_BIN, 'snapshot', '-c', name, self.drive_name])
        path,snapshot = os.path.split(self.drive_name)
        snapshot = name + '-' + snapshot
        img = os.path.join(path, snapshot)
        return TestImage('rhev', img)

    def launch(self):
        # TODO destroy domain if already running (or skip) ?
        name = os.path.split(self.drive_name)[-1].replace(".img", "");
        stdout = run_cmd([VIRT_INST_BIN, '--connect', 'qemu:///system',
                                         '--name', name, '--ram', '1024',
                                         '--vcpus', '1', '--disk', self.drive_name,
                                         '--accelerate', '--boot', 'hd', '--noautoconsole'])
        return TestInstance(name, self)

    def inspect(self):
        return self.converter.inspect()

    def list_kernels(self):
        with RootMounted(self.converter._h, '/dev/VolGroup00/LogVol00'):
            grub = guestconv.converters.redhat.Grub2BIOS(
                self.converter._h, '/dev/VolGroup00/LogVol00', logger)
            return grub.list_kernels()

    def __init__(self, target, image=None):
        self.converter = Converter(target, ['%s/conf/guestconv.db' % topdir],
                                   logger)
        if image == None:
            self.drive = tempfile.NamedTemporaryFile()
            self.drive_name = self.drive.name

        else:
            self.drive = None
            self.drive_name = image

class TestInstance:
    def __init__(self, name, image):
        self.name  = name
        self.image = image

        # retrieve instance mac
        self.xml = run_cmd([VIRSH_BIN, 'dumpxml', name])
        xmldoc = et.fromstring(self.xml)
        self.mac = xmldoc.find('./devices/interface/mac')
        self.mac = self.mac.get('address')

        # retrieve instance ip
        leases = open(LIBVIRT_LEASES_FILE, "r")
        for line in leases:
          m = re.match("[^\s]*\s*%s\s*([^\s]*).*" % self.mac, line)
          if m:
            self.ip = m.group(1)
            break
        leases.close()

    def ssh_cmd(self, cmd):
        run_cmd([SSH_BIN, '-i', 'test/data/key',
                  "-o", "ServerAliveInterval=30",
                  "-o", "StrictHostKeyChecking=no",
                  "-o", "UserKnownHostsFile=/dev/null",
                  "-o", "PasswordAuthentication=no",
                  ("guest@%s" % self.ip), cmd])

class TestHelper:
  images    = []

  @classmethod
  def has_image(cls, image):
      return cls.image_for(image) != None

  @classmethod
  def image_for(cls, image):
      for img in cls.images:
          if img.drive == image:
              return img
      return None

  @classmethod
  def init(cls):
      if not os.path.isfile(OZ_BIN) or not os.access(OZ_BIN, os.X_OK):
          print "oz not found, skipping image generation"
          return

      # build tdls
      for tdl in os.listdir(TDL_DIR):
          cls.images.append(build_tdl(tdl))

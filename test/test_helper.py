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
import tempfile
import subprocess

import guestconv

from guestconv.converter import Converter
import guestconv.converters.redhat

topdir = os.path.join(os.path.dirname(__file__), os.pardir)

OZ_BIN  = '/usr/bin/oz-install'
TDL_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data', 'tdls')
IMG_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data', 'images')

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
    stdoutf = tempfile.TemporaryFile()
    # requires root privs:
    popen   = subprocess.Popen([OZ_BIN, "-s", image, os.path.join(TDL_DIR, tdl)], stdout=stdoutf, stderr=stdoutf)
    popen.wait()
    stdoutf.seek(0)
    stdout = stdoutf.read()
    stdoutf.close()
    print stdout
    # TODO analyze stdout/stderr/exitcode for errors

    return TestImage('rhev', image)

def logger(level, msg):
    print msg

class TestImage:
    def close(self):
        if self.drive:
            if type(self.drive) is not str:
                self.drive.close()

    def open(self):
        if self.drive:
            if type(self.drive) is str:
                self.converter.add_drive(self.drive)
                self.converter._h.add_drive_opts(self.drive, format="raw", readonly=0)
                self.converter._h.launch()
            else:
                self.converter.add_drive(self.drive.name)

    # def snapshot(self): TODO

    def inspect(self):
        return self.converter.inspect()

    def list_kernels(self):
        # TODO parameterize
        self.converter._h.mount('/dev/VolGroup00/LogVol00', '/')
        self.converter._h.mount('/dev/vdb2', '/boot')
        grub = guestconv.converters.redhat.Grub2BIOS(self.converter._h, '/dev/VolGroup00/LogVol00', logger)
        return grub.list_kernels()

    def __init__(self, target, image=None):
        self.converter = Converter(target, ['%s/conf/guestconv.db' % topdir],
                                   logger)
        if image == None:
            self.drive = tempfile.NamedTemporaryFile()
        else:
            self.drive = image

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

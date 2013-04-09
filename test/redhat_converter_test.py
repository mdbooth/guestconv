# test/redhat_converter_test.py unit test suite for
# guestconv redhat converter operations
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
import unittest

from guestconv.converter import Converter
import guestconv.converters.redhat

IMG_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data', 'images')
F17IMG  = os.path.join(IMG_DIR, 'f17x86_64.img')

def logger(level, msg):
    print msg

class GrubTest(unittest.TestCase):
    def setUp(self):
        self.c = Converter(['conf/guestconv.db'], logger)

    @unittest.skipUnless(os.path.exists(F17IMG), "image does not exist")
    def testGrubListKernels(self):
        self.c.add_drive(F17IMG)
        self.c._h.add_drive_opts(F17IMG, format = "raw", readonly = 0)
        self.c._h.launch()
        self.c._h.mount('/dev/VolGroup00/LogVol00', '/')
        self.c._h.mount('/dev/vdb2', '/boot')
        grub = guestconv.converters.redhat.Grub2BIOS(self.c._h, '/dev/VolGroup00/LogVol00', logger)
        kernels = grub.list_kernels()
        self.assertEqual(1, len(kernels))
        self.assertEqual("/boot/vmlinuz-3.3.4-5.fc17.x86_64", kernels[0])

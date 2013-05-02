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

from test_helper import TestHelper
from images import *

class GrubTest(unittest.TestCase):
    def setUp(self):
        self.img = TestHelper.image_for(F17IMG)

    @unittest.skipUnless(TestHelper.has_image(F17IMG), "image does not exist")
    def testListKernels(self):
        self.img.inspect()
        kernels = self.img.list_kernels()
        self.assertEqual(1, len(kernels))
        self.assertEqual("/boot/vmlinuz-3.3.4-5.fc17.x86_64", kernels[0])

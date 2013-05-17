# test/debian_coverter_test.py unit test suite for
# guestconv debian converter operations
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

import os.path
import unittest
import guestconv

from test_helper import TestHelper
from images import *

@unittest.skipUnless(os.path.exists(UBUNTU_1210_64_IMG), "image does not exist")
class GrubTest(unittest.TestCase):
    def setUp(self):
        self.img = TestHelper.image_for(UBUNTU_1210_64_IMG)

    def testNoBootloader(self):
        self.assertRaises(guestconv.exception.ConversionError, self.img.inspect)

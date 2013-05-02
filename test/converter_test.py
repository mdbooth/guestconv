# test/converter_test.py unit test suite for guestconv convert operation
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
import tempfile
from xml.dom import minidom

from test_helper import TestHelper
from images import *

class ConverterTest(unittest.TestCase):
    def setUp(self):
        self.img = TestHelper.image_for(F17IMG)
        self.img.open()

    def tearDown(self):
        self.img.close()

    def testInspect(self):
        xml = self.img.inspect()
        xmldoc = minidom.parseString(xml)
        self.assertEqual(1, xmldoc.getElementsByTagName('guestconv').length)

    def testReentrantInspect(self):
        # we should just get the same object back if inspect multiple times
        xml1 = self.img.inspect()
        xml2 = self.img.inspect()
        self.assertTrue(xml1 is xml2)

    def testConvert(self):
        # self.c.convert('TODO')
        self.assertTrue(1 == 1)

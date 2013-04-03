# test/inspecttest.py unit test suite for guestconv inspect operation
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

from guestconv.converter import Converter

def logger(level, msg):
    print msg

class ConverterTest(unittest.TestCase):
    def setUp(self):
        self.c = Converter(['conf/guestconv.db'], logger)
        self.drive = tempfile.NamedTemporaryFile()
        self.c.add_drive(self.drive.name)

    def tearDown(self):
        self.drive.close()

    def testInspect(self):
        xml = self.c.inspect('rhev')
        xmldoc = minidom.parseString(xml)
        self.assertEqual(1, xmldoc.getElementsByTagName('guestconv').length)

    def testConvert(self):
        # self.c.convert('TODO')
        self.assertTrue(1 == 1)

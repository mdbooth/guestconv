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

import os
import unittest
from xml.dom import minidom

from guestconv.converter import Converter

def logger(level, msg):
    print msg

class ConverterTest(unittest.TestCase):
    def setUp(self):
        self.c = Converter(['conf/guestconv.db'], logger)
        #self.c.add_drive("TODO")

    def testInspect(self):
        xml = self.c.inspect('rhev')
        xmldoc = minidom.parseString(xml)
        self.assertEqual(1, xmldoc.getElementsByTagName('guestconv').length)

    def testConvert(self):
        # self.c.convert('TODO')
        self.assertTrue(1 == 1)

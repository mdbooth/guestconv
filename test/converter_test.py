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

from redhat_converter_test import Fedora17Image
from test_helper import cmpXMLNoOrdering

class ConverterTest(Fedora17Image):
    def testInspect(self):
        output = self.img.converter.inspect()
        expected = '''
<guestconv>
  <root name="/dev/VolGroup00/LogVol00">
    <info>
      <arch>x86_64</arch>
      <distribution>fedora</distribution>
      <hostname>unknown</hostname>
      <os>linux</os>
      <version>
        <major>17</major>
        <minor>0</minor>
      </version>
    </info>
    <options>
      <option name="graphics" description="Graphics driver">
        <value description="Cirrus">cirrus-vga</value>
        <value description="Spice">qxl-vga</value>
      </option>
      <option name="network" description="Network driver">
        <value description="Intel E1000">e1000</value>
        <value description="Realtek 8139">rtl8139</value>
        <value description="VirtIO">virtio-net</value>
      </option>
      <option name="block" description="Block device driver">
        <value description="IDE">ide-hd</value>
        <value description="SCSI">scsi-hd</value>
        <value description="VirtIO">virtio-blk</value>
      </option>
      <option name="console" description="System Console">
        <value description="Kernel virtual console">vc</value>
        <value description="Serial console">serial</value>
        <value description="VirtIO Serial">virtio-serial</value>
      </option>
    </options>
  </root>
  <boot>
    <loader disk="sda" type="BIOS" name="grub2-bios"/>
  </boot>
</guestconv>
        '''

        self.assertTrue(cmpXMLNoOrdering(output, expected))

    def testReentrantInspect(self):
        # we should just get the same object back if inspect multiple times
        xml1 = self.img.converter.inspect()
        xml2 = self.img.converter.inspect()
        self.assertTrue(xml1 is xml2)

    def testConvert(self):
        # self.c.convert('TODO')
        self.assertTrue(1 == 1)

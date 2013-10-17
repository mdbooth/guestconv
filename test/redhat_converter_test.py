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

from itertools import izip
import unittest

import test_helper
from images import *

import guestconv.converter as converter

#
# Tests
#

# Grub2 tested by Fedora19
# GrubLegacy tested by RHEL52_64
#
# Full XML tested by Fedora19
#
# Identity of inspect() tested by Fedora19

def make_grub_tests(root, kernels):
    def testListKernels(self):
        with converter.RootMounted(self.img.converter._h, root):
            for g, k in izip(
                self.img.converter._converters[root]._bootloader.iter_kernels(),
                kernels
            ):
                self.assertRegexpMatches(g, k)

    return {u'testListKernels': testListKernels}

def make_xml_test(expected):
    def testXML(self):
        output = self.img.converter.inspect()
        try:
            test_helper.cmpXMLNoOrdering(output, expected)
        except test_helper.CmpXMLNoOrderingError as err:
            self.fail(u'XML differs from expected: {}: {}'
                      .format(err.message, output))

    return {u'testXML': testXML}

def make_inspect_identity_test():
    def testInspectIdentity(self):
        xml1 = self.img.converter.inspect()
        xml2 = self.img.converter.inspect()
        self.assertIs(xml1, xml2)

    return {u'testInspectIdentity': testInspectIdentity}

Fedora_19_64_Test = test_helper.make_image_test(
    'Fedora_19_64_Test',
    FEDORA_19_64_IMG,
    u'/dev/VolGroup00/LogVol00',
    {
        u'graphics': [],
        u'network': [u'e1000', u'rtl8139'],
        u'block': [u'ide-hd', u'scsi-hd'],
        u'console': [u'vc', u'serial']
    },
    make_grub_tests(
        u'/dev/VolGroup00/LogVol00',
        [u'/boot/vmlinuz-3.9.5-301.fc19.x86_64',
         u'/boot/vmlinuz-0-rescue-[0-9a-f]*']
    ),
    make_xml_test(u'''
<guestconv>
  <root name="/dev/VolGroup00/LogVol00">
    <info>
      <arch>x86_64</arch>
      <distribution>fedora</distribution>
      <hostname>localhost.localdomain</hostname>
      <os>linux</os>
      <version>
        <major>19</major>
        <minor>0</minor>
      </version>
    </info>
    <options>
      <option description="Hypervisor support" name="hypervisor">
        <value description="KVM">kvm</value>
        <value description="Xen Paravirtualised">xenpv</value>
        <value description="Xen Fully Virtualised">xenfv</value>
        <value description="VirtualBox">vbox</value>
        <value description="VMware">vmware</value>
        <value description="Citrix Fully Virtualised">citrixfv</value>
        <value description="Citrix Paravirtualised">citrixpv</value>
      </option>
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
    '''),
    make_inspect_identity_test()
)

Fedora_19_64_EFI_Test = test_helper.make_image_test(
    'Fedora_19_64_EFI_Test',
    FEDORA_19_64_EFI_IMG,
    u'/dev/fedora/root',
    {
        u'graphics': [],
        u'network': [u'e1000', u'rtl8139'],
        u'block': [u'ide-hd', u'scsi-hd'],
        u'console': [u'vc', u'serial']
    },
    make_grub_tests(
        u'/dev/fedora/root',
        [u'/boot/vmlinuz-3.9.5-301.fc19.x86_64',
         u'/boot/vmlinuz-0-rescue-[0-9a-f]*']
    ),
    make_xml_test(u'''
<guestconv>
  <root name="/dev/fedora/root">
    <info>
      <arch>x86_64</arch>
      <distribution>fedora</distribution>
      <hostname>localhost.localdomain</hostname>
      <os>linux</os>
      <version>
        <major>19</major>
        <minor>0</minor>
      </version>
    </info>
    <options>
      <option description="Hypervisor support" name="hypervisor">
        <value description="KVM">kvm</value>
        <value description="Xen Paravirtualised">xenpv</value>
        <value description="Xen Fully Virtualised">xenfv</value>
        <value description="VirtualBox">vbox</value>
        <value description="VMware">vmware</value>
        <value description="Citrix Fully Virtualised">citrixfv</value>
        <value description="Citrix Paravirtualised">citrixpv</value>
      </option>
      <option name="graphics" description="Graphics driver"/>
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
    <loader disk="sda" name="grub2-efi" type="EFI">
      <replacement name="grub2-bios" type="BIOS"/>
    </loader>
  </boot>
</guestconv>
    ''')
)

RHEL_46_32_Test = test_helper.make_image_test(
    'RHEL_46_32_Test',
    RHEL46_32_IMG,
    u'/dev/VolGroup00/LogVol00',
    {
        u'graphics': [],
        u'network': [u'e1000', u'rtl8139'],
        u'block': [u'ide-hd', u'scsi-hd'],
        u'console': [u'vc', u'serial']
    }
)

RHEL_52_64_Test = test_helper.make_image_test(
    'RHEL_52_64_Test',
    RHEL52_64_IMG,
    u'/dev/VolGroup00/LogVol00',
    {
        u'graphics': [],
        u'network': [u'e1000', u'rtl8139'],
        u'block': [u'ide-hd', u'scsi-hd'],
        u'console': [u'vc', u'serial']
    },
    make_grub_tests(u'/dev/VolGroup00/LogVol00',
                    [u'/boot/vmlinuz-2.6.18-92.el5'])
)

all_tests = unittest.TestSuite((
    unittest.makeSuite(Fedora_19_64_Test),
    unittest.makeSuite(Fedora_19_64_EFI_Test),
    unittest.makeSuite(RHEL_46_32_Test),
    unittest.makeSuite(RHEL_52_64_Test)
))

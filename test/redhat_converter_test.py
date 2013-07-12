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

import env

import unittest
import re
import lxml.etree as ET

import test_helper
from images import *

import guestconv.db as db
import guestconv.converters.redhat as redhat
import guestconv.converter as converter
import guestconv.log as log

TestHelper = test_helper.TestHelper

#
# Base classes
#

RHEL_5_X86_64_SYSTEMID = os.path.join(DATA_DIR, 'systemid-rhel-5-x86_64')

@unittest.skipUnless(os.path.exists(RHEL52_64_IMG), "image does not exist")
@unittest.skipUnless(os.path.exists(RHEL_5_X86_64_SYSTEMID),
                     "systemid file does not exist")
@unittest.skipIf('GUESTCONV_NONETWORK' in os.environ, 'no network')
class RHEL52_64_Yum(unittest.TestCase):
    def setUp(self):
        self.img = TestHelper.image_for(RHEL52_64_IMG)
        h = self.img.guestfs_handle()
        h.launch()
        h.inspect_os()
        with converter.RootMounted(h, '/dev/VolGroup00/LogVol00'):
            h.upload(RHEL_5_X86_64_SYSTEMID, '/etc/sysconfig/rhn/systemid')
        h.close()


@unittest.skipUnless(os.path.exists(FEDORA_17_64_IMG), "image does not exist")
@unittest.skipIf('GUESTCONV_NONETWORK' in os.environ, 'no network')
class Fedora17Image(unittest.TestCase):
    def setUp(self):
        self.img = TestHelper.image_for(FEDORA_17_64_IMG)

        props = test_helper.get_local_props()
        if u'fedora_mirror' in props:
            h = self.img.guestfs_handle()
            h.launch()
            h.inspect_os()
            with converter.RootMounted(h, '/dev/VolGroup00/LogVol00'):
                h.aug_init(u'/', 0)

                mirror = props[u'fedora_mirror']

                h.aug_rm(u'/files/etc/yum.repos.d/fedora.repo'
                         u'/fedora/mirrorlist')
                h.aug_set(u'/files/etc/yum.repos.d/fedora.repo/fedora/baseurl',
                    u'{}/releases/$releasever/Everything/$basearch/os/'.
                    format(mirror))

                h.aug_rm(u'/files/etc/yum.repos.d/fedora-updates.repo'
                         u'/updates/mirrorlist')
                h.aug_set(u'/files/etc/yum.repos.d/fedora-updates.repo'
                          u'/updates/baseurl',
                          u'{}/updates/$releasever/$basearch/'.format(mirror))

                h.aug_save()
            h.close()


#
# Tests
#

class GrubTest(Fedora17Image):
    def testListKernels(self):
        img = self.img

        img.converter.inspect()
        with converter.RootMounted(img.converter._h,
                                   '/dev/VolGroup00/LogVol00'):
            kernels = (img.converter._converters['/dev/VolGroup00/LogVol00'].
                                     _bootloader.list_kernels())

        self.assertEqual(1, len(kernels))
        self.assertEqual('/boot/vmlinuz-3.3.4-5.fc17.x86_64', kernels[0])


@unittest.skipUnless(os.path.exists(RHEL46_32_IMG), "image does not exist")
class RHEL46_32_LocalInstallTest(unittest.TestCase):
    def setUp(self):
        self.img = TestHelper.image_for(RHEL46_32_IMG)

    def testCheckAvailable(self):
        """Check a kernel package is available via LocalInstaller"""
        img = self.img
        img.converter.inspect()
        with converter.RootMounted(img.converter._h,
                                   '/dev/VolGroup00/LogVol00'):
            c = img.converter
            installer = redhat.LocalInstaller(
                c._h, '/dev/VolGroup00/LogVol00',
                db.DB(['{}/conf/guestconv.db'.format(env.topdir)]),
                log.get_logger_object(test_helper.logger)
            )

            kernel = redhat.Package('kernel',
                                    version='2.6.9', release='89.EL',
                                    arch='i686')
            self.assertTrue(installer.check_available([kernel]))

    def testInspect(self):
        """Check we've got the expected options"""
        inspected = ET.fromstring(self.img.converter.inspect())

        expected = {
            u'graphics': [],
            u'network': [u'e1000', u'rtl8139'],
            u'block': [u'ide-hd', u'scsi-hd'],
            u'console': [u'vc', u'serial']
        }

        options = inspected.xpath(u'/guestconv'
                                  u"/root[@name='/dev/VolGroup00/LogVol00']"
                                  u'/options')
        self.assertTrue(len(options) == 1,
                        u'No options in returned inspection xml')
        options = options[0]

        for name in expected:
            values = expected[name]

            option = options.xpath(u"option[@name='{}']".format(name))
            self.assertTrue(len(option) == 1, u'No {} option'.format(name))
            option = option[0]

            for value in values:
                v = option.xpath(u"value[. = '{}']".format(value))
                self.assertTrue(len(v) == 1,
                                u'value {} not found for option {}'.
                                format(value, name))


@unittest.skipUnless(os.path.exists(RHEL52_64_IMG), "image does not exist")
class RHEL52_64_LocalInstallTest(unittest.TestCase):
    def setUp(self):
        self.img = TestHelper.image_for(RHEL52_64_IMG)

    def testCheckAvailable(self):
        img = self.img
        img.converter.inspect()
        with converter.RootMounted(img.converter._h,
                                   '/dev/VolGroup00/LogVol00'):
            c = img.converter
            installer = redhat.LocalInstaller(
                c._h, '/dev/VolGroup00/LogVol00',
                db.DB(['{}/conf/guestconv.db'.format(env.topdir)]),
                log.get_logger_object(test_helper.logger)
            )

            kernel = redhat.Package('kernel',
                                    version='2.6.18', release='128.el5',
                                    arch='x86_64')
            self.assertTrue(installer.check_available([kernel]))

    def testInstallerCheckAvailableFallback(self):
        img = self.img
        img.converter.inspect()
        with converter.RootMounted(img.converter._h,
                                   '/dev/VolGroup00/LogVol00'):
            c = img.converter
            installer = redhat.Installer(
                c._h, '/dev/VolGroup00/LogVol00',
                db.DB(['{}/conf/guestconv.db'.format(env.topdir)]),
                log.get_logger_object(test_helper.logger)
            )

            kernel = redhat.Package('kernel',
                                    version='2.6.18', release='128.el5',
                                    arch='x86_64')
            self.assertTrue(installer.check_available([kernel]))

class RHEL52_64_YumInstallTest(RHEL52_64_Yum):
    def testCheckAvailable(self):
        img = self.img
        img.converter.inspect()
        with converter.RootMounted(img.converter._h,
                                   '/dev/VolGroup00/LogVol00'):
            c = img.converter
            installer = redhat.YumInstaller(
                c._h, '/dev/VolGroup00/LogVol00',
                log.get_logger_object(test_helper.logger)
            )

            kernel = redhat.Package('kernel',
                                    version='2.6.18', release='128.el5',
                                    arch='x86_64')
            self.assertTrue(installer.check_available([kernel]))

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

import test_helper
from images import *

import guestconv.db as db
import guestconv.converters.redhat as redhat
import guestconv.converter as converter
import guestconv.log as log

TestHelper = test_helper.TestHelper

class GrubTest(unittest.TestCase):
    def setUp(self):
        self.img = TestHelper.image_for(F17IMG)

    @unittest.skipUnless(os.path.exists(F17IMG), "image does not exist")
    def testListKernels(self):
        self.img.inspect()
        kernels = self.img.list_kernels()
        self.assertEqual(1, len(kernels))
        self.assertEqual("/boot/vmlinuz-3.3.4-5.fc17.x86_64", kernels[0])

class RHEL46_32_LocalInstallTest(unittest.TestCase):
    def setUp(self):
        self.img = TestHelper.image_for(RHEL46_32_IMG)

    @unittest.skipUnless(os.path.exists(RHEL46_32_IMG), "image does not exist")
    def testCheckAvailable(self):
        img = self.img
        img.inspect()
        with converter.RootMounted(img.converter._h,
                                   '/dev/VolGroup00/LogVol00'):
            c = img.converter
            installer = redhat.LocalInstaller(
                c._h, '/dev/VolGroup00/LogVol00',
                db.DB(['{}/conf/guestconv.db'.format(env.topdir)]),
                log.get_logger_object(test_helper.logger)
            )

            kernel = redhat.Package('kernel', None, '2.6.9', '89.EL',
                                    'i686')
            self.assertTrue(installer.check_available([kernel]))

class RHEL52_64_LocalInstallTest(unittest.TestCase):
    def setUp(self):
        self.img = TestHelper.image_for(RHEL52_64_IMG)

    @unittest.skipUnless(os.path.exists(RHEL52_64_IMG), "image does not exist")
    def testCheckAvailable(self):
        img = self.img
        img.inspect()
        with converter.RootMounted(img.converter._h,
                                   '/dev/VolGroup00/LogVol00'):
            c = img.converter
            installer = redhat.LocalInstaller(
                c._h, '/dev/VolGroup00/LogVol00',
                db.DB(['{}/conf/guestconv.db'.format(env.topdir)]),
                log.get_logger_object(test_helper.logger)
            )

            kernel = redhat.Package('kernel', None, '2.6.18', '128.el5',
                                    'x86_64')
            self.assertTrue(installer.check_available([kernel]))

RHEL_5_X86_64_SYSTEMID = os.path.join(DATA_DIR, 'systemid-rhel-5-x86_64')

@unittest.skipUnless(os.path.exists(RHEL_5_X86_64_SYSTEMID),
                     "systemid file does not exist")
class RHEL52_64_YumInstallTest(unittest.TestCase):
    def setUp(self):
        self.img = TestHelper.image_for(RHEL52_64_IMG)
        h = self.img.guestfs_handle()
        h.launch()
        h.inspect_os()
        with converter.RootMounted(h, '/dev/VolGroup00/LogVol00'):
            h.upload(RHEL_5_X86_64_SYSTEMID, '/etc/sysconfig/rhn/systemid')
        h.close()

    @unittest.skipUnless(os.path.exists(RHEL52_64_IMG), "image does not exist")
    def testCheckAvailable(self):
        img = self.img
        img.inspect()
        with converter.RootMounted(img.converter._h,
                                   '/dev/VolGroup00/LogVol00'):
            c = img.converter
            installer = redhat.YumInstaller(
                c._h, '/dev/VolGroup00/LogVol00',
                log.get_logger_object(test_helper.logger)
            )

            kernel = redhat.Package('kernel', None, '2.6.18', '128.el5',
                                    'x86_64')
            self.assertTrue(installer.check_available([kernel]))

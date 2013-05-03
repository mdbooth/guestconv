# coding: utf-8
# guestconv
#
# Copyright (C) 2013 Red Hat Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import env

import guestfs
import unittest

import guestconv.db

import rhel_stub

class DBParseErrorTestCase(unittest.TestCase):
    def runTest(self):
        with self.assertRaises(guestconv.db.DBParseError):
            guestconv.db.DB(['%s/test/data/db/parse-error.db' % env.topdir])


class DBLookupTestCase(rhel_stub.RHELStubTestCase):
    @classmethod
    def setUpClass(cls):
        super(DBLookupTestCase, cls).setUpClass()

        cls._h = guestfs.GuestFS()
        cls._h.add_drive(cls._img.name, name='/dev/sda')
        cls._h.launch()
        roots = cls._h.inspect_os()
        cls._root = roots[0]

    @classmethod
    def tearDownClass(cls):
        cls._h = None

        super(DBLookupTestCase, cls).tearDownClass()

    def setUp(self):
        super(DBLookupTestCase, self).setUp()

        self.db = guestconv.db.DB(['%s/test/data/db/override.db' % env.topdir,
                                   '%s/conf/guestconv.db' % env.topdir])

    
    def tearDown(self):
        self.db = None

        super(DBLookupTestCase, self).tearDown()

    def testCapabilityMatch(self):
        h = self.__class__._h
        root = self.__class__._root

        cap = self.db.match_capability('virtio', 'x86_64', h, root)
        expected = {
            'kernel': {'minversion': '2.6.18-128.el5', 'ifinstalled': False},
            'lvm2': {'minversion': '2.02.40-6.el5', 'ifinstalled': False},
            'selinux-policy-targeted':
                {'minversion': '2.4.6-203.el5', 'ifinstalled': True}
        }
        self.assertEqual(expected, cap)

    def testCapabilityOverride(self):
        h = self.__class__._h
        root = self.__class__._root

        cap = self.db.match_capability('cirrus', 'x86_64', h, root)
        expected = {
            'foo': {'minversion': None, 'ifinstalled': False}
        }
        self.assertEqual(expected, cap)

    def testCapabilityNoMatch(self):
        h = self.__class__._h
        root = self.__class__._root

        cap = self.db.match_capability('foo', 'x86_64', h, root)
        self.assertIsNone(cap)

    def testAppMatch(self):
        h = self.__class__._h
        root = self.__class__._root

        path, deps = self.db.match_app('kernel', 'x86_64', h, root)
        self.assertEqual(path, '/var/lib/guestconv/software/rhel/5/kernel-2.6.18-128.el5.x86_64.rpm')
        self.assertEqual(deps, ['ecryptfs-utils'])

    def testAppNoMatch(self):
        h = self.__class__._h
        root = self.__class__._root

        path, deps = self.db.match_app('foo', 'x86_64', h, root)
        self.assertIsNone(path)
        self.assertIsNone(deps)

    def testAppMatchNoPathRoot(self):
        h = self.__class__._h
        root = self.__class__._root

        path, deps = self.db.match_app('bar', 'x86_64', h, root)
        self.assertEqual('bar_path', path)
        self.assertEqual([], deps)


class DBTestSuite(unittest.TestSuite):
    def __init__(self):
        self.addTest(DBParseErrorTestCase())
        self.addTest(DBLookupTestCase("testCapabilityMatch"))
        self.addTest(DBLookupTestCase("testCapabilityOverride"))
        self.addTest(DBLookupTestCase("testCapabilityNoMatch"))
        self.addTest(DBLookupTestCase("testAppMatch"))
        self.addTest(DBLookupTestCase("testAppNoMatch"))
        self.addTest(DBLookupTestCase("testAppMatchNoPathRoot"))


if __name__ == "__main__":
    unittest.main()

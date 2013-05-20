# test/rpm_package.py unit test suite for
# guestconv internal rpm package handling
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

import operator
import unittest

from guestconv.converters.redhat import Package

class RpmPackageTest(unittest.TestCase):
    def testConstruction(self):
        # Full construction
        p = Package('foo', '1', '1.2', '3', 'i686')
        self.assertEqual(str(p), '1:foo-1.2-3.i686')

        # Partial construction: name and arch
        p = Package('foo', arch='i686')
        self.assertEqual(str(p), 'foo.i686')

        # Partial construction: name, version
        p = Package('foo', version='1.2')
        self.assertEqual(str(p), 'foo-1.2')

    def testEq(self):
        # Packages with different names are not comparable
        a = Package('foo')
        b = Package('bar')
        self.assertRaises(TypeError, operator.eq, (a, b))

        # Only names set
        b = Package('foo')
        self.assertEqual(a, b)

        # Arch set
        a.arch = 'x86_64'
        self.assertRaises(TypeError, operator.eq, (a, b))

        b.arch = 'x86_64'
        self.assertEqual(a, b)

        # Version set
        a.version = '2.23.9'
        self.assertNotEqual(a, b)
        self.assertNotEqual(b, a)

        b.version = '2.23.9'
        self.assertEqual(a, b)

        # Release set
        a.release = '14_4.fc18'
        self.assertNotEqual(a, b)
        self.assertNotEqual(b, a)

        b.release = '14_4.fc18'
        self.assertEqual(a, b)

        # Epoch set
        a.epoch = '1'
        self.assertNotEqual(a, b)
        self.assertNotEqual(b, a)

        b.epoch = '1'
        self.assertEqual(a, b)

    def testOrdering(self):
        a = Package('foo')
        b = Package('foo')

        self.assertFalse(a > b)
        self.assertFalse(a < b)
        self.assertTrue(a >= b)
        self.assertTrue(a <= b)

        # A has version, b doesn't
        a.version = '2.23.9_fc18'
        self.assertTrue(a > b)
        self.assertTrue(a >= b)
        self.assertFalse(a < b)
        self.assertFalse(a <= b)
        self.assertFalse(b > a)
        self.assertFalse(b >= a)
        self.assertTrue(b < a)
        self.assertTrue(b <= a)

        # A and b have equal versions
        b.version = '2.23.9_fc18'
        self.assertFalse(a > b)
        self.assertTrue(a >= b)
        self.assertFalse(a < b)
        self.assertTrue(a <= b)
        self.assertFalse(b > a)
        self.assertTrue(b >= a)
        self.assertFalse(b < a)
        self.assertTrue(b <= a)

        # A has greater minor version
        a.version = '2.23.10_fc18'
        self.assertTrue(a > b)
        self.assertTrue(a >= b)
        self.assertFalse(a < b)
        self.assertFalse(a <= b)
        self.assertFalse(b > a)
        self.assertFalse(b >= a)
        self.assertTrue(b < a)
        self.assertTrue(b <= a)

        # A has longer version, with equal prefix
        a.version = '2.23.9_fc18.foo'
        self.assertTrue(a > b)
        self.assertTrue(a >= b)
        self.assertFalse(a < b)
        self.assertFalse(a <= b)
        self.assertFalse(b > a)
        self.assertFalse(b >= a)
        self.assertTrue(b < a)
        self.assertTrue(b <= a)

        # A and B differ only in text
        b.version = '2.23.9_fc18.bar'
        self.assertTrue(a > b)
        self.assertTrue(a >= b)
        self.assertFalse(a < b)
        self.assertFalse(a <= b)
        self.assertFalse(b > a)
        self.assertFalse(b >= a)
        self.assertTrue(b < a)
        self.assertTrue(b <= a)

        # version has only a single component
        a.version = '2'
        b.version = '1'
        self.assertTrue(a > b)
        self.assertTrue(a >= b)
        self.assertFalse(a < b)
        self.assertFalse(a <= b)
        self.assertFalse(b > a)
        self.assertFalse(b >= a)
        self.assertTrue(b < a)
        self.assertTrue(b <= a)

        # A has release, b doesn't
        a.version = '1'
        a.release = '2'
        self.assertTrue(a > b)
        self.assertTrue(a >= b)
        self.assertFalse(a < b)
        self.assertFalse(a <= b)
        self.assertFalse(b > a)
        self.assertFalse(b >= a)
        self.assertTrue(b < a)
        self.assertTrue(b <= a)

        # A has epoch greater than B
        b.release = '2'
        a.epoch = '1'
        self.assertTrue(a > b)
        self.assertTrue(a >= b)
        self.assertFalse(a < b)
        self.assertFalse(a <= b)
        self.assertFalse(b > a)
        self.assertFalse(b >= a)
        self.assertTrue(b < a)
        self.assertTrue(b <= a)

#!/usr/bin/python
#
# test/run.py load unit test suits and run them
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

import unittest

import os.path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))

import db
import rpm_package

import debian_converter_test
import redhat_converter_test

suite = unittest.TestSuite((
    db.all_tests,
    rpm_package.all_tests,
    redhat_converter_test.all_tests,
    debian_converter_test.all_tests
))

unittest.TextTestRunner(verbosity=2).run(suite)

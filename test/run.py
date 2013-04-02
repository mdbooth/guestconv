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

import unittest

import sys
sys.path.append("../guestconv/")

import guestconv
import guestconv

import convertertest

if __name__ == '__main__':
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(convertertest.ConverterTest))
    unittest.TextTestRunner(verbosity=2).run(suite)

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

import os
import os.path
import sys
import subprocess
import tempfile
sys.path.append("../guestconv/")

import guestconv
import guestconv

import convertertest
import redhat_converter_test

TDL_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data', 'tdls')
IMG_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data', 'images')

def build_tdl(tdl):
    image   = os.path.join(IMG_DIR, tdl.replace("tdl", "img"))
    if os.path.exists(image):
        return
    stdoutf = tempfile.TemporaryFile()
    # requires root privs:
    popen   = subprocess.Popen(["oz-install", "-s", image, os.path.join(TDL_DIR, tdl)], stdout=stdoutf, stderr=stdoutf)
    popen.wait()
    stdoutf.seek(0)
    stdout = stdoutf.read()
    stdoutf.close()
    print stdout
    # TODO analyze stdout/stderr/exitcode for errors

    return image

def build_tdls():
    for tdl in os.listdir(TDL_DIR):
        build_tdl(tdl)

if __name__ == '__main__':
    build_tdls()
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(convertertest.ConverterTest))
    suite.addTest(unittest.makeSuite(redhat_converter_test.GrubTest))
    unittest.TextTestRunner(verbosity=2).run(suite)

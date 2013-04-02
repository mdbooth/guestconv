#!/usr/bin/python
#
# guestconv
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
from distutils.core import setup

data_files = [("/etc", ["conf/guestconv.db"]),
              ('/usr/share/guestconv/',
               ['examples/example.py', 'examples/example.sh', 'examples/root.xml'])]

setup(name='guestconv',
	version='0.1',
	description='guest filesystem converter',
	url='http://',
	packages=['guestconv', 'guestconv.converters'],
	data_files=data_files,
	scripts=[])

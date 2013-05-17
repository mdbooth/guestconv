# test/images.py
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

import os.path

DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
IMG_DIR = os.path.join(DATA_DIR, 'images')

FEDORA_17_64_IMG = os.path.join(IMG_DIR, 'fedora-17-x86_64.img')
UBUNTU_1210_64_IMG = os.path.join(IMG_DIR, 'ubuntu-12.10-x86_64.img')

RHEL46_32_IMG = os.path.join(IMG_DIR, 'rhel-4.6-i386.img')
RHEL52_64_IMG = os.path.join(IMG_DIR, 'rhel-5.2-x86_64.img')

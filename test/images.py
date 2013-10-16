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

DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), u'data')
IMG_DIR = os.path.join(DATA_DIR, u'images')

FEDORA_19_64_IMG = os.path.join(IMG_DIR, u'fedora-19-x86_64.img')
FEDORA_19_64_EFI_IMG = os.path.join(IMG_DIR, u'fedora-19-x86_64-efi.img')
UBUNTU_1210_64_IMG = os.path.join(IMG_DIR, u'ubuntu-12.10-x86_64.img')

RHEL46_32_IMG = os.path.join(IMG_DIR, u'rhel-4.6-i386.img')
RHEL52_64_IMG = os.path.join(IMG_DIR, u'rhel-5.2-x86_64.img')
RHEL60_64_EFI_IMG = os.path.join(IMG_DIR, u'rhel-6.0-x86_64-efi.img')

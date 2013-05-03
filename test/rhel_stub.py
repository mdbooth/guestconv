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
import tempfile
import unittest

class RHELStubTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._img = tempfile.NamedTemporaryFile(prefix='guestconv-test.')
        cls._img.truncate(512*1024*1024)

        h = guestfs.GuestFS()
        h.add_drive(cls._img.name)
        h.launch()

        # Create 2 partitions
        h.part_init('/dev/sda', 'mbr')
        h.part_add('/dev/sda', 'p', 64, 524287)
        h.part_add('/dev/sda', 'p', 524288, -64)

        # Initialise LVM
        h.pvcreate('/dev/sda2')
        h.vgcreate('VG', ['/dev/sda2'])
        h.lvcreate('Root', 'VG', 32)

        # Create phony root filesystem
        h.mkfs('ext2', '/dev/VG/Root', blocksize=4096)
        h.set_label('/dev/VG/Root', 'ROOT')
        h.mount('/dev/VG/Root', '/')

        # Create phony /boot filesystem
        h.mkfs('ext2', '/dev/sda1', blocksize=4096)
        h.set_label('/dev/sda1', 'BOOT')
        h.mkdir('/boot')
        h.mount('/dev/sda1', '/boot')

        # Create enough OS to fool libguestfs inspection
        for i in ['/bin', '/etc', '/etc/sysconfig', '/usr', '/var/lib/rpm']:
           h.mkdir_p(i)

        h.write('/etc/shadow', 'root::15440:0:99999:7:::\n')
        h.chmod(0, '/etc/shadow')

        h.lsetxattr('security.selinux', 'system_u:object_r:shadow_t:s0', 30,
                    '/etc/shadow')

        h.write('/etc/fstab', '''
LABEL=BOOT /boot ext2 default 0 0
LABEL=ROOT / btrfs subvol=root 0 0
LABEL=ROOT /home btrfs subvol=home 0 0
''')

        h.write('/etc/redhat-release',
                'Red Hat Enterprise Linux Server release 5.0 (Phony)')

        h.write('/etc/sysconfig/network', 'HOSTNAME=rhel-test.example.com\n')

        h.upload('%s/test/data/stub-image/rhel-name.db' % env.topdir,
                 '/var/lib/rpm/Name')
        h.upload('%s/test/data/stub-image/rhel-packages.db' % env.topdir,
                 '/var/lib/rpm/Packages')

        h.upload('%s/test/data/stub-image/bin-x86_64-dynamic' % env.topdir,
                 '/bin/ls')

        h.mkdir('/boot/grub')
        h.touch('/boot/grub/grub.conf')

    @classmethod
    def tearDownClass(cls):
        cls._img.close()

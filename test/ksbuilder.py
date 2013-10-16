# test/builder.py
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

from subprocess import call

import libvirt
import os.path
import random
import string
import sys
import tempfile
import time

from urlparse import urlparse

class ISOMounted(object):
    '''Execute a block of code with an ISO image locally mounted.

    :iso: The path to an iso image.
    '''

    def __init__(self, iso):
        self.iso = iso

        if u'LIBGUESTFS_ROOT' in os.environ:
            root = os.environ[u'LIBGUESTFS_ROOT']

            self._guestmount = [os.path.join(root, u'run'),
                                os.path.join(root, u'fuse', u'guestmount')]
            self._guestunmount = [os.path.join(root, u'run'),
                                  os.path.join(root, u'fuse', u'guestunmount')]
        else:
            self._guestmount = [u'guestmount']
            self._guestunmount = [u'guestunmount']

    def __enter__(self):
        self.mountdir = tempfile.mkdtemp()

        retval = call(self._guestmount + [u'--ro', u'-a', self.iso,
                                          u'-m', u'/dev/sda', self.mountdir],
                      stdout = sys.stdout, stderr = sys.stderr)
        if retval != 0:
            raise RuntimeError(u'Failed to guestmount {}'.format(self.iso))

        return self.mountdir

    def __exit__(self, typ, value, tb):
        retval = call(self._guestunmount + [self.mountdir],
                      stdout = sys.stdout, stderr = sys.stderr)
        if retval != 0:
            raise RuntimeError(u'Failed guestunmount {}'.
                                   format(self.iso))

        os.rmdir(self.mountdir)

        return False

class SuppressLibvirtErrors(object):
    def __enter__(self):
        def _libvirt_ignore_error_func(user, error):
            pass

        libvirt.registerErrorHandler(_libvirt_ignore_error_func, None)

    def __exit__(self, typ, value, tb):
        libvirt.registerErrorHandler(None, None)
        return False

# Usage of this function is still racy, but I don't believe it's possible to fix
# this and still use virt-install, and it's not a security problem
def gen_libvirt(conn, name):
    def gen_suffix():
        return ''.join(random.choice(string.ascii_lowercase) for i in range(6))

    # Try up to 1000 times to find an unused name
    with SuppressLibvirtErrors():
        for i in range(1000):
            name = u'{}.{}'.format(name, gen_suffix())
            try:
                conn.lookupByName(name)
            except libvirt.libvirtError:
                return name

def build_iso(name, ks, iso, image_size=3, os_variant=None, loader=None):
    with ISOMounted(iso) as mp:
        return build_url(name, ks, mp, image_size, os_variant, loader,
                         [u'--disk', iso + u',format=raw,device=cdrom'])

def build_url(name, ks, url, image_size=3, os_variant=None, loader=None,
              vi_extra=[]):
    conn = libvirt.open(None)
    if conn == None:
        raise RuntimeError(u'Failed top open libvirt connection')

    lvname = gen_libvirt(conn, name)

    img_path = os.path.join(env.topdir, u'test/data/images', name + u'.img')
    vi = [
        u'virt-install',
        u'--name', lvname,
        u'--ram', u'1024',
        u'--disk', u'{path},format=raw,size={size}'
                   .format(path=img_path, size=image_size),
        u'--initrd-inject', ks,
        u'--extra-args', u'ks=file:/{ks} console=tty0 console=ttyS0,115200'
                         .format(ks=os.path.basename(ks)),
        u'--location', url,
        u'--graphics', u'none',
        u'--noreboot'
    ]
    if loader is not None:
        vi.extend([u'--boot', u'loader={}'.format(loader)])
    if os_variant is not None:
        vi.extend([u'--os-variant', os_variant])
    vi.extend(vi_extra)

    # Run virt-install
    print u'Running: {}'.format(u' '.join(vi))
    retval = call(vi, stdout = sys.stdout, stderr = sys.stderr)
    if retval != 0:
        raise RuntimeError(u'virt-install failed')

    # We're only interested in the disk image
    domain = conn.lookupByName(lvname)
    domain.undefine()

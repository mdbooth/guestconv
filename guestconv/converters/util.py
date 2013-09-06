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

"""Internal functions useful to more than 1 converter"""

__all__ = [u'augeas_error', u'Network']

import re

from guestconv.exception import *
from guestconv.converters.exception import *

def augeas_error(h, ex):
    msg = [str(ex)]
    try:
        for error in h.aug_match(u'/augeas/files//error'):
            m = re.match(u'^/augeas/files(/.*)/error$', error)
            file_path = m.group(1)

            detail = {}
            for detail_path in h.aug_match(error + u'//*'):
                m = re.match(u'^%s/(.*)$' % error, detail_path)
                detail[m.group(1)] = h.aug_get(detail_path)

            if u'message' in detail:
                msg.append(_(u'augeas error for {path}: {message}').\
                           format(path=file_path, message=detail[u'message']))
            else:
                msg.append(_(u'augeas error for {path}').format(path=file_path))

            if u'pos' in detail and u'line' in detail and u'char' in detail:
                msg.append(_(u'error at line {detail[line]}, '
                             u'char {detail[char]}, '
                             u'file position {detail[pos]}').\
                           format(detail=detail))

            if u'lens' in detail:
                msg.append(_(u'augeas lens: {lens}').\
                           format(lens=detail[u'lens']))
    except GuestFSException as new:
        raise ConversionError(
            _(u'error generating augeas error: {error}').
                format(error=new.message) + u'\n' +
            _(u'original error: {error}').format(error=ex.message))

    msg = msg.strip()

    if len(msg) > 1:
        raise ConversionError(u'\n'.join(msg))

    raise ex

resolv = u'/etc/resolv.conf'
resolv_bak = u'/etc/resolv.conf.v2vtmp'
class Network(object):
    '''Execute a block of code with networking configured in the guest'''

    def __init__(self, h):
        self._h = h

    def __enter__(self):
        h = self._h

        # Backup: don't care if it's a file
        self._resolv_bak = h.exists(resolv_bak)

        if self._resolv_bak:
            h.mv(resolv, resolv_bak)

        h.write_file(resolv, u'nameserver 169.254.2.3', 0)

    def __exit__(self, typ, value, tb):
        h = self._h

        if self._resolv_bak:
            h.mv(resolv_bak, resolv)
        else:
            h.rm(resolv)

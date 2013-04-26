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

import os.path
import lxml.etree as ET
from itertools import product

from guestconv.lang import _

class DBParseError(Exception): pass


class DB(object):

    """A database of additional software required during conversion.

    During the conversion process, it may be necessary to install new software
    to enable certain functionality. The software required will be different for
    different operation systems. This class allows that information to be
    abstracted into a separate XML document.

    Several XML documents can be specified. They are searched for a match in
    order, meaning a match in an earlier document overrides a match in a later
    document.

    :db_paths: A list containing the paths to DB XML documents.

    """

    def __init__(self, db_paths):
        self._trees = []
        for path in db_paths:
            try:
                self._trees.append(ET.parse(path))
            except ET.ParseError as e:
                raise DBParseError(_(u'Parse error in %(path)s: %(error)s') % \
                                   {u'path': path, u'error': e.message})

    def _match_element(self, type_, name, arch, h, root):
        def queries():
            def _match_queries(os, distro, major, minor):
                def _match_query(os, distro, major, minor, arch):
                    query = []
                    query.append(u'/guestconv/{type}[@name="{name}" and '
                                 u'@os="{os}" and '.
                                 format(type=type_, name=name, os=os))
                    if distro is None:
                        query.append(u'not(@distro)')
                    else:
                        query.append(u'@distro="{}"'.format(distro))
                    query.append(u' and ')
                    if major is None:
                        query.append(u'not(@major)')
                    else:
                        query.append(u'@major="{}"'.format(major))
                    query.append(' and ')
                    if minor is None:
                        query.append(u'not(@minor)')
                    else:
                        query.append(u'@minor="{}"'.format(minor))
                    query.append(u' and ')
                    if arch is None:
                        query.append(u'not(@arch)')
                    else:
                        query.append(u'@arch="{}"'.format(arch))
                    query.append(u'][1]')

                    return u''.join(query)

                if arch is not None:
                    yield _match_query(os, distro, major, minor, arch)
                yield _match_query(os, distro, major, minor, None)

            os     = h.inspect_get_type(root)
            distro = h.inspect_get_distro(root)
            major  = h.inspect_get_major_version(root)
            minor  = h.inspect_get_minor_version(root)

            if major is not None:
                if minor is not None:
                    for i in _match_queries(os, distro, major, minor):
                        yield i
                for i in _match_queries(os, distro, major, None):
                    yield i
            if distro is not None:
                for i in _match_queries(os, distro, None, None):
                    yield i
            for i in _match_queries(os, None, None, None):
                yield i

        for tree, query in product(self._trees, queries()):
            elements = tree.xpath(query)
            if len(elements) > 0:
                path_root = None
                path_roots = tree.xpath(u'/guestconv/path-root[1]')
                if len(path_roots) > 0:
                    path_root = path_roots[0].text.strip()
                return (elements[0], path_root)
        return (None, None)

    def match_capability(self, name, arch, h, root):
        """Match the capability with name and arch for the given root."""
        cap, dummy = self._match_element(u'capability', name, arch, h, root)
        if cap is None:
            return None

        out = {}
        for dep in cap.xpath(u'dep'):
            props = {}

            name = dep.get(u'name')
            minversion = dep.get(u'minversion')
            ifinstalled = dep.get(u'ifinstalled')

            name.strip()
            if minversion:
                minversion.strip()
            if ifinstalled:
                ifinstalled.strip()

            props[u'minversion'] = minversion
            props[u'ifinstalled'] = ifinstalled in (u'1', u'yes')
            out[name] = props

        return out

    def match_app(self, name, arch, h, root):
        """Match the app with name and arch for the given root."""
        app, path_root = self._match_element(u'app', name, arch, h, root)
        if app is None:
            return (None, None)

        paths = app.xpath(u'path[1]')
        if len(paths) == 0:
            raise DBParseError(_(u'app {name} for root {root} is missing '
                                 u'a path element').
                               format(name=name, root=root))
        if path_root:
            path = os.path.join(path_root, paths[0].text.strip())
        else:
            path = paths[0].text.strip()

        deps = []
        for dep in app.xpath(u'dep'):
            deps.append(dep.text.strip())

        return (path, deps)

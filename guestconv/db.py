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
        def _match_queries(os, distro, major, minor):
            def _match_query(os, distro, major, minor, arch):
                query = u'/guestconv/%s[@name="%s" and @os="%s" and ' % \
                        (type_, name, os)
                if distro is None:
                    query += u'not(@distro)'
                else:
                    query += u'@distro="%s"' % distro
                query += u' and '
                if major is None:
                    query += u'not(@major)'
                else:
                    query += u'@major="%s"' % major
                query += ' and '
                if minor is None:
                    query += u'not(@minor)'
                else:
                    query += u'@minor="%s"' % minor
                query += u' and '
                if arch is None:
                    query += u'not(@arch)'
                else:
                    query += u'@arch="%s"' % arch
                query += u'][1]'

                return query

            queries = []
            if arch is not None:
                queries.append(_match_query(os, distro, major, minor, arch))
            queries.append(_match_query(os, distro, major, minor, None))
            return queries

        os     = h.inspect_get_type(root)
        distro = h.inspect_get_distro(root)
        major  = h.inspect_get_major_version(root)
        minor  = h.inspect_get_minor_version(root)

        queries = []
        if major is not None:
            if minor is not None:
                queries.extend(_match_queries(os, distro, major, minor))
            queries.extend(_match_queries(os, distro, major, None))
        if distro is not None:
            queries.extend(_match_queries(os, distro, None, None))
        queries.extend(_match_queries(os, None, None, None))

        for tree in self._trees:
            for query in queries:
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
        (cap, dummy) = self._match_element(u'capability', name, arch, h, root)
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
            props[u'ifinstalled'] = ifinstalled in ('1', 'yes')
            out[name] = props

        return out

    def match_app(self, name, arch, h, root):
        "Match the app with name and arch for the given root."""
        (app, path_root) = self._match_element(u'app', name, arch, h, root)
        if app is None:
            return (None, None)

        paths = app.xpath(u'path[1]')
        if len(paths) == 0:
            raise DBParseError(_(u'app %(name)s for root %(root)s is missing a path element') %
                               {u'name': name, u'root': root})
        if path_root:
            path = os.path.join(path_root, paths[0].text.strip())
        else:
            path = paths[0].text.strip()

        deps = []
        for dep in app.xpath(u'dep'):
            deps.append(dep.text.strip())

        return (path, deps)

# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

# pylint: disable=invalid-name,missing-docstring

from __future__ import absolute_import, division, print_function, unicode_literals
import unittest
from resources.lib import playurl
from resources.lib.playurl import _drop_query_param, repair_play_url


class TestDropQueryParam(unittest.TestCase):
    def test_drop_middle(self):
        self.assertEqual(
            _drop_query_param('plugin://x/history?index=34&silent=true&foo=1', 'silent'),
            'plugin://x/history?index=34&foo=1')

    def test_drop_last(self):
        self.assertEqual(
            _drop_query_param('plugin://x/history?index=34&silent=true', 'silent'),
            'plugin://x/history?index=34')

    def test_drop_only(self):
        self.assertEqual(
            _drop_query_param('plugin://x/history?silent=true', 'silent'),
            'plugin://x/history')

    def test_drop_missing(self):
        url = 'plugin://x/history?index=34'
        self.assertEqual(_drop_query_param(url, 'silent'), url)

    def test_drop_similar_name_kept(self):
        url = 'plugin://x/history?silentx=true&index=1'
        self.assertEqual(_drop_query_param(url, 'silent'), url)


class TestRepairPlayUrl(unittest.TestCase):
    def test_elementum_silent_history_repaired(self):
        url = ('plugin://plugin.video.elementum/history?index=34'
               '&infohash=af16756a79393f1576a32ba1d4714175dbd67675&silent=true')
        repaired, changed = repair_play_url(url)
        self.assertTrue(changed)
        self.assertEqual(repaired, ('plugin://plugin.video.elementum/history?index=34'
                                    '&infohash=af16756a79393f1576a32ba1d4714175dbd67675'))
        self.assertNotIn('silent', repaired)

    def test_elementum_history_without_silent_untouched(self):
        url = 'plugin://plugin.video.elementum/history?index=34&infohash=af16'
        self.assertEqual(repair_play_url(url), (url, False))

    def test_elementum_non_history_untouched(self):
        url = 'plugin://plugin.video.elementum/play?uri=%2Ftmp%2Fx.torrent&silent=true'
        self.assertEqual(repair_play_url(url), (url, False))

    def test_other_addon_untouched(self):
        url = 'plugin://plugin.video.other/history?index=2&silent=true'
        self.assertEqual(repair_play_url(url), (url, False))

    def test_empty(self):
        self.assertEqual(repair_play_url(''), ('', False))
        self.assertEqual(repair_play_url(None), (None, False))

    def test_rules_are_pure(self):
        for rule in playurl.REPAIR_RULES:
            self.assertEqual(rule('not a url'), 'not a url')

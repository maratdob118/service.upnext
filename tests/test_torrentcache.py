# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

# pylint: disable=invalid-name,missing-docstring

from __future__ import absolute_import, division, print_function, unicode_literals
import os
import tempfile
import time
import unittest
from resources.lib import torrentcache
from resources.lib.torrentcache import (
    _prune_cache,
    cache_torrent_file,
    parse_elementum_history_url,
    restore_torrent_file,
)

HASH = 'fc96a7e70049cf5e0ace272f8b4ff6f5c4ef18df'


class TestParseElementumHistoryUrl(unittest.TestCase):
    def test_index_and_infohash(self):
        url = ('plugin://plugin.video.elementum/history?index=21&infohash=' + HASH)
        self.assertEqual(parse_elementum_history_url(url), (HASH, 21))

    def test_param_order(self):
        url = ('plugin://plugin.video.elementum/history?infohash=' + HASH
               + '&index=3&silent=true')
        self.assertEqual(parse_elementum_history_url(url), (HASH, 3))

    def test_no_index(self):
        url = 'plugin://plugin.video.elementum/history?infohash=' + HASH
        self.assertEqual(parse_elementum_history_url(url), (HASH, None))

    def test_other_paths_ignored(self):
        self.assertEqual(
            parse_elementum_history_url('plugin://plugin.video.elementum/play?uri=x'),
            (None, None))
        self.assertEqual(
            parse_elementum_history_url('plugin://plugin.video.other/history?index=1'),
            (None, None))
        self.assertEqual(parse_elementum_history_url(''), (None, None))
        self.assertEqual(parse_elementum_history_url(None), (None, None))


class TestTorrentCacheRoundtrip(unittest.TestCase):
    def _dirs(self, tmp):
        temp_dir = os.path.join(tmp, 'temp')
        cache_dir = os.path.join(tmp, 'cache')
        os.makedirs(temp_dir)
        return temp_dir, cache_dir

    def test_cache_and_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir, cache_dir = self._dirs(tmp)
            source = os.path.join(temp_dir, HASH + '.torrent')
            with open(source, 'wb') as handle:
                handle.write(b'd8:announce35:http://tracker/xzitseeds0e')
            self.assertTrue(cache_torrent_file(HASH, temp_dir, cache_dir))
            os.remove(source)
            self.assertTrue(restore_torrent_file(HASH, temp_dir, cache_dir))
            with open(source, 'rb') as handle:
                self.assertTrue(handle.read().startswith(b'd8:announce'))

    def test_restore_present_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir, cache_dir = self._dirs(tmp)
            source = os.path.join(temp_dir, HASH + '.torrent')
            with open(source, 'wb') as handle:
                handle.write(b'data')
            self.assertTrue(restore_torrent_file(HASH, temp_dir, cache_dir))

    def test_restore_without_cache_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir, cache_dir = self._dirs(tmp)
            self.assertFalse(restore_torrent_file(HASH, temp_dir, cache_dir))

    def test_cache_missing_source_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir, cache_dir = self._dirs(tmp)
            self.assertFalse(cache_torrent_file(HASH, temp_dir, cache_dir))

    def test_prune_keeps_newest(self):
        with tempfile.TemporaryDirectory() as tmp:
            _temp_dir, cache_dir = self._dirs(tmp)
            os.makedirs(cache_dir)
            now = time.time()
            for num in range(5):
                path = os.path.join(cache_dir, 'h%d.torrent' % num)
                with open(path, 'wb') as handle:
                    handle.write(b'x')
                stamp = now - (5 - num)
                os.utime(path, (stamp, stamp))
            _prune_cache(cache_dir, 2)
            self.assertEqual(sorted(os.listdir(cache_dir)),
                             ['h3.torrent', 'h4.torrent'])

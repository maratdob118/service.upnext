# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

"""Keep Elementum .torrent files available across episode switches.

Elementum deletes the cached .torrent file (plus fast-resume data) as
soon as the current episode ends - but the next episode of the same
season pack lives in the very same torrent. The following autoplay then
fails with an unplayable item because there is nothing to resolve
anymore.

This module snapshots the .torrent file while it still exists (on
playback start) into the add-on profile, and restores it into the temp
directory synchronously before Up Next hands the next URL to the
player. No race: the restore happens in the autoplay path itself.

Only .torrent metadata is cached (kilobytes); media/buffer data is
untouched. Old entries are pruned, newest first wins.
"""

from __future__ import absolute_import, division, unicode_literals
import os
import shutil

try:
    from urllib.parse import parse_qsl, urlsplit
except ImportError:  # Python 2
    from urlparse import parse_qsl, urlsplit

CACHE_SUBDIR = 'torrent_cache'
CACHED_SUFFIX = '.torrent'
MAX_CACHED_FILES = 20


def parse_elementum_history_url(url):
    """Parse an Elementum history URL. Returns (infohash, index|None)."""
    if not url or 'plugin.video.elementum' not in url:
        return None, None
    try:
        parts = urlsplit(url)
    except Exception:
        return None, None
    if not parts.path.rstrip('/').endswith('/history'):
        return None, None
    params = dict(parse_qsl(parts.query))
    infohash = params.get('infohash')
    if not infohash:
        return None, None
    try:
        index = int(params.get('index')) if params.get('index') else None
    except (TypeError, ValueError):
        index = None
    return infohash, index


def elementum_dirs():
    """Kodi-dependent temp/cache directories for .torrent files."""
    from xbmcvfs import translatePath
    temp_dir = translatePath('special://temp/elementum/')
    cache_dir = translatePath('special://profile/addon_data/service.upnext/'
                              + CACHE_SUBDIR + '/')
    return temp_dir, cache_dir


def _torrent_filename(infohash):
    return (infohash or '') + CACHED_SUFFIX


def cache_torrent_file(infohash, temp_dir, cache_dir,
                       max_files=MAX_CACHED_FILES):
    """Snapshot the live .torrent file. Returns True when cached."""
    if not infohash:
        return False
    source = os.path.join(temp_dir, _torrent_filename(infohash))
    if not os.path.isfile(source):
        return False
    try:
        if not os.path.isdir(cache_dir):
            os.makedirs(cache_dir)
        shutil.copyfile(source, os.path.join(cache_dir, _torrent_filename(infohash)))
    except (OSError, IOError):
        return False
    _prune_cache(cache_dir, max_files)
    return True


def restore_torrent_file(infohash, temp_dir, cache_dir):
    """Restore a missing .torrent file from cache. Returns True if ready."""
    if not infohash:
        return False
    target = os.path.join(temp_dir, _torrent_filename(infohash))
    if os.path.isfile(target):
        return True
    cached = os.path.join(cache_dir, _torrent_filename(infohash))
    if not os.path.isfile(cached):
        return False
    try:
        shutil.copyfile(cached, target)
    except (OSError, IOError):
        return False
    return True


def _prune_cache(cache_dir, max_files):
    """Keep only the newest MAX files in the cache directory."""
    try:
        entries = [os.path.join(cache_dir, name)
                   for name in os.listdir(cache_dir)]
    except OSError:
        return
    entries = sorted(
        (path for path in entries if os.path.isfile(path)),
        key=lambda path: os.path.getmtime(path),
        reverse=True,
    )
    for stale in entries[max_files:]:
        try:
            os.remove(stale)
        except OSError:
            pass

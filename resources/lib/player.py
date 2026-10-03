# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import getCondVisibility, Player, Monitor
from api import Api
from state import State
from torrentcache import (
    cache_torrent_file,
    daemon_infohashes,
    elementum_dirs,
    extract_infohashes,
    parse_elementum_history_url,
    restore_all_cached,
)
from utils import get_setting_bool, log as ulog


class UpNextPlayer(Player):
    """Service class for playback monitoring"""
    last_file = None
    track = False

    def __init__(self):
        self.api = Api()
        self.state = State()
        self.monitor = Monitor()
        Player.__init__(self)

    def set_last_file(self, filename):
        self.state.last_file = filename

    def get_last_file(self):
        return self.state.last_file

    def is_tracking(self):
        return self.state.track

    def disable_tracking(self):
        self.state.track = False

    def enable_tracking(self):
        self.state.track = True

    def reset_queue(self):
        if self.state.queued:
            self.api.reset_queue()
            self.state.queued = False

    def _cache_elementum_torrent(self):
        """Snapshot .torrent files while playback (and the files) is live.

        Elementum deletes them the moment the episode ends, which breaks
        the next-episode URL of the same season pack. Cached early and
        restored in the autoplay path itself (see
        api.ensure_elementum_torrent) plus a periodic sweep (see
        monitor._restore_cached_torrents).

        Infohashes come from the daemon torrent list, not from the
        playback URL: by the time playback starts Kodi has already
        resolved plugin URLs to stream URLs.
        """
        if not get_setting_bool('repairFragileUrls'):
            return
        infohashes = set()
        try:
            playing_file = self.getPlayingFile()
        except RuntimeError:
            playing_file = ''
        infohash, _index = parse_elementum_history_url(playing_file or '')
        if infohash:
            infohashes.add(infohash)
        try:
            infohashes |= daemon_infohashes()
        except Exception:
            pass
        if not infohashes:
            return
        try:
            temp_dir, cache_dir = elementum_dirs()
        except Exception:
            return
        for candidate in sorted(infohashes):
            try:
                if cache_torrent_file(candidate, temp_dir, cache_dir):
                    ulog('Cached .torrent for next-episode switch: %s' % candidate,
                         name=self.__class__.__name__, level=2)
            except Exception:
                pass

    def _check_video(self):
        self.monitor.waitForAbort(5)
        if not getCondVisibility('videoplayer.content(episodes)'):
            return
        self.state.track = True

    if callable(getattr(Player, 'onAVStarted', None)):
        def onAVStarted(self):  # pylint: disable=invalid-name
            """Will be called when Kodi has a video or audiostream"""
            self._check_video()

        def onPlayBackStarted(self):  # pylint: disable=invalid-name
            """Will be called when kodi starts playing a file"""
            self.reset_queue()
            self._cache_elementum_torrent()
    else:
        def onPlayBackStarted(self):  # pylint: disable=invalid-name
            """Will be called when kodi starts playing a file"""
            self.reset_queue()
            self._check_video()
            self._cache_elementum_torrent()

    def onPlayBackPaused(self):  # pylint: disable=invalid-name
        self.state.pause = True

    def onPlayBackResumed(self):  # pylint: disable=invalid-name
        self.state.pause = False

    def _restore_elementum_torrents(self):
        """Put cached .torrent files back the moment playback stops.

        This is the deterministic hook: Kodi advances to the next
        playlist item (or Up Next plays it) right after the stop, while
        Elementum deletes the .torrent file in the same instant. A
        restore here wins that race for every play path - queued
        autoplay, playlist advance or a manual next press.
        """
        if not get_setting_bool('repairFragileUrls'):
            return
        try:
            temp_dir, cache_dir = elementum_dirs()
            restored = restore_all_cached(temp_dir, cache_dir)
        except Exception:
            return
        for infohash in restored:
            ulog('Restored cached .torrent on stop: %s' % infohash,
                 name=self.__class__.__name__, level=2)

    def onPlayBackStopped(self):  # pylint: disable=invalid-name
        """Will be called when user stops playing a file"""
        self._restore_elementum_torrents()
        self.reset_queue()
        self.api.reset_addon_data()
        self.state = State()  # Reset state

    def onPlayBackEnded(self):  # pylint: disable=invalid-name
        """Will be called when Kodi has ended playing a file"""
        self._restore_elementum_torrents()
        self.reset_queue()
        # Only reset state if not playing the next episode
        if not self.state.playing_next:
            self.api.reset_addon_data()
            self.state = State()  # Reset state

    def onPlayBackError(self):  # pylint: disable=invalid-name
        """Will be called when when playback stops due to an error"""
        self.reset_queue()
        self.api.reset_addon_data()
        self.state = State()  # Reset state

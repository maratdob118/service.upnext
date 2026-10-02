# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import getCondVisibility, Player, Monitor
from api import Api
from state import State
from torrentcache import cache_torrent_file, elementum_dirs, parse_elementum_history_url
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
        """Snapshot the .torrent file while playback (and the file) is live.

        Elementum deletes it the moment the episode ends, which breaks the
        next-episode URL of the same season pack. Cached early, restored
        (see api.ensure_elementum_torrent) in the autoplay path itself.
        """
        try:
            playing_file = self.getPlayingFile()
        except RuntimeError:
            return
        infohash, _index = parse_elementum_history_url(playing_file)
        if not infohash or not get_setting_bool('repairFragileUrls'):
            return
        try:
            temp_dir, cache_dir = elementum_dirs()
        except Exception:
            return
        try:
            if cache_torrent_file(infohash, temp_dir, cache_dir):
                ulog('Cached .torrent for next-episode switch: %s' % infohash,
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

    def onPlayBackStopped(self):  # pylint: disable=invalid-name
        """Will be called when user stops playing a file"""
        self.reset_queue()
        self.api.reset_addon_data()
        self.state = State()  # Reset state

    def onPlayBackEnded(self):  # pylint: disable=invalid-name
        """Will be called when Kodi has ended playing a file"""
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

# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

"""Repair fragile add-on play URLs before queueing/playing the next episode.

Some source add-ons hand Up Next URLs that only resolve while a transient
cache is warm. The known case is Elementum: a `history?...&silent=true`
URL is skipped as unplayable once the cached .torrent file is gone, while
the same URL without `silent` makes Elementum re-fetch it. Rewriting to
the re-resolving form keeps autoplay working.

Rules are small pure functions collected in REPAIR_RULES, so new fragile
URL shapes can be covered without touching playback logic.
"""

from __future__ import absolute_import, division, unicode_literals


def _drop_query_param(url, name):
    """Return url without query parameter NAME (exact, case sensitive)."""
    if '?' not in url:
        return url
    base, query = url.split('?', 1)
    kept = [part for part in query.split('&')
            if part and part.split('=', 1)[0] != name]
    return base if not kept else base + '?' + '&'.join(kept)


def _elementum_history_silent(url):
    """Elementum silent history URLs fail on a cold cache, drop `silent`.

    `plugin://plugin.video.elementum/history?...&silent=true` is skipped
    as unplayable when the cached .torrent file no longer exists, while
    the identical URL without `silent` makes Elementum re-fetch it.
    """
    if 'plugin.video.elementum' not in url:
        return url
    path = url.split('?', 1)[0]
    if not path.rstrip('/').endswith('/history'):
        return url
    if 'silent=true' not in url:
        return url
    return _drop_query_param(url, 'silent')


# Ordered repair rules, first match wins. Add new rules here.
REPAIR_RULES = (
    _elementum_history_silent,
)


def repair_play_url(url):
    """Repair a fragile play URL. Returns (url, changed)."""
    if not url:
        return url, False
    for rule in REPAIR_RULES:
        try:
            repaired = rule(url)
        except Exception:  # A rule must never break playback
            continue
        if repaired != url:
            return repaired, True
    return url, False

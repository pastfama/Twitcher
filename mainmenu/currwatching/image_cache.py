"""Async image downloader with URL-keyed pixmap caching.

All network I/O happens on a background thread (via
:func:`workers.run_in_background`) so the Qt GUI thread never blocks.
Finished pixmaps are cached so the same avatar/thumbnail is only
fetched once per session.

The cache is shared application-wide through :meth:`ImageCache.shared`.
"""

import requests

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from core import run_in_background


class ImageCache:
    """Download and cache remote images asynchronously.

    Call :meth:`load` with a target ``QLabel`` and an image URL.  If
    the image is already cached the label is updated immediately (fast,
    no network).  Otherwise the download is dispatched to a background
    thread and the label is updated via a queued callback on the GUI
    thread once the data arrives.
    """

    _shared = None

    def __init__(self, max_cache=128):
        self._pixmaps = {}       # url -> QPixmap (already scaled)
        self._pending = set()    # urls with an in-flight download
        self._max_cache = max_cache

    # ---------------------------------------------------------- public

    def load(self, label, url, size, placeholder="?"):
        """Load *url* into *label* at *size*.

        Returns immediately.  Cached images are applied synchronously;
        new downloads complete on a background thread and the label is
        updated through a queued callback on the GUI thread.
        """
        if not url:
            self._show_placeholder(label, placeholder)
            return

        cached = self._pixmaps.get(url)
        if cached is not None:
            self._apply(label, cached)
            return

        if url in self._pending:
            return

        self._pending.add(url)
        run_in_background(
            lambda: self._fetch(url),
            lambda result: self._on_done(result, label, size, placeholder),
            lambda _err: self._discard(url),
        )

    # ---------------------------------------------------------- fetching

    @staticmethod
    def _fetch(url):
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return url, response.content

    def _on_done(self, result, label, size, placeholder):
        url, data = result
        self._discard(url)

        if not data:
            self._show_placeholder(label, placeholder)
            return

        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            scaled = pixmap.scaled(
                size[0],
                size[1],
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._store(url, scaled)
            self._apply(label, scaled)
        else:
            self._show_placeholder(label, placeholder)

    # ---------------------------------------------------------- helpers

    def _store(self, url, pixmap):
        if len(self._pixmaps) >= self._max_cache:
            self._pixmaps.pop(next(iter(self._pixmaps)))
        self._pixmaps[url] = pixmap

    @staticmethod
    def _apply(label, pixmap):
        label.setPixmap(pixmap)
        label.setText("")

    @staticmethod
    def _show_placeholder(label, text):
        """Clear any existing pixmap and show placeholder text."""
        # PySide6 does not accept None for setPixmap — use an empty QPixmap.
        from PySide6.QtGui import QPixmap
        label.setPixmap(QPixmap())
        label.setText(text)

    def _discard(self, url):
        self._pending.discard(url)

    # ---------------------------------------------------------- singleton

    @classmethod
    def shared(cls):
        """Return the process-wide :class:`ImageCache` instance."""
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

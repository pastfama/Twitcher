"""Async bridge — runs an asyncio event loop in a background thread.

Both ``twitchAPI`` and ``irc3`` are asyncio-based, but Twitcher's UI runs
on the PySide6 (Qt) event loop.  This module provides a single shared
asyncio loop running in a daemon thread, plus helpers to:

- schedule coroutines from the Qt thread (``run_async``)
- bridge async results/events back to Qt signals (``AsyncSignal``)
- run a blocking call in the loop and wait for its result (``run_sync``)

Usage::

    from core.async_bridge import run_async, run_sync

    # Fire-and-forget from Qt thread:
    run_async(my_coroutine())

    # Blocking call (e.g. inside a QThreadPool worker):
    result = run_sync(my_coroutine())
"""

import asyncio
import threading
from typing import Any, Awaitable, Optional, TypeVar

from PySide6.QtCore import QObject, Signal

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Shared event loop
# ---------------------------------------------------------------------------

_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_thread: Optional[threading.Thread] = None
_loop_lock = threading.Lock()


def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Target for the background thread — runs the loop forever."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def get_loop() -> asyncio.AbstractEventLoop:
    """Return the shared asyncio event loop, starting it if needed."""
    global _loop, _loop_thread
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            _loop_thread = threading.Thread(
                target=_run_loop,
                args=(_loop,),
                name="twitcher-asyncio",
                daemon=True,
            )
            _loop_thread.start()
        return _loop


def run_async(coro: Awaitable[T]) -> asyncio.Future:
    """Schedule *coro* on the shared loop from any thread.

    Returns an ``asyncio.Future`` that completes when the coroutine
    finishes.  The caller is responsible for attaching a callback if it
    needs the result (or use :func:`run_sync` to block).
    """
    loop = get_loop()
    return asyncio.run_coroutine_threadsafe(coro, loop)


def run_sync(coro: Awaitable[T], timeout: Optional[float] = None) -> T:
    """Run *coro* on the shared loop and block until it completes.

    Safe to call from a QThreadPool worker (not the GUI thread).
    """
    future = run_async(coro)
    return future.result(timeout)


def stop_loop() -> None:
    """Stop the shared event loop (used on app shutdown)."""
    global _loop
    with _loop_lock:
        if _loop is not None and _loop.is_running():
            _loop.call_soon_threadsafe(_loop.stop)


# ---------------------------------------------------------------------------
# Qt signal bridge
# ---------------------------------------------------------------------------


class AsyncSignal(QObject):
    """Bridges an async event to a Qt signal on the GUI thread.

    Usage::

        class MyBridge(QObject):
            result_ready = Signal(object)

            def __init__(self):
                super().__init__()
                self._signal = AsyncSignal(self.result_ready)

            async def _worker(self):
                data = await fetch()
                self._signal.emit(data)

    The signal is emitted from the asyncio thread; Qt automatically
    queues the delivery to the GUI thread (queued connection).
    """

    def __init__(self, signal: Signal, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._signal = signal

    def emit(self, *args: Any) -> None:
        """Emit the wrapped signal (thread-safe)."""
        self._signal.emit(*args)
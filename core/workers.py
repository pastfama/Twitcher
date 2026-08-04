"""Run blocking work (Twitch HTTP calls) off the GUI thread.

Qt widgets may only be touched from the GUI thread, so the callables passed
here must do network/CPU work only. Results come back through queued signals,
which Qt delivers on the GUI thread — safe to update widgets from there.
"""

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class TaskSignals(QObject):

    finished = Signal(object)

    failed = Signal(str)


class BackgroundTask(QRunnable):

    def __init__(self, work):

        super().__init__()

        # We keep the Python object alive ourselves (see _ACTIVE below), so Qt
        # must not delete the C++ side out from under it when run() returns.
        self.setAutoDelete(False)

        self.work = work
        self.signals = TaskSignals()

    def run(self):

        try:
            result = self.work()
        except Exception as exc:
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")
            return

        self.signals.finished.emit(result)


# Tasks handed to the pool would otherwise be garbage collected while still
# running, taking their signals object with them.
_ACTIVE = set()


def run_in_background(work, on_success, on_error):

    task = BackgroundTask(work)

    _ACTIVE.add(task)

    def release(_result=None):
        _ACTIVE.discard(task)

    task.signals.finished.connect(on_success)
    task.signals.failed.connect(on_error)

    task.signals.finished.connect(release)
    task.signals.failed.connect(release)

    QThreadPool.globalInstance().start(task)

    return task


def wait_for_pending(timeout_ms=2000):

    return QThreadPool.globalInstance().waitForDone(timeout_ms)

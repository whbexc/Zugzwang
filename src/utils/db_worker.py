"""
ZUGZWANG - DB Worker Utility
Non-blocking SQLite / heavy-I/O helper using Qt's global thread-pool.

Usage:
    from src.utils.db_worker import run_in_thread

    run_in_thread(
        some_blocking_fn, arg1, arg2,
        on_result=self._handle_result,
        on_error=lambda msg: logger.error(msg),
        on_finished=self._on_done,
    )

Rules:
  - Never touch Qt UI widgets from inside the worker; only emit signals.
  - Never pass an sqlite3.Connection across threads.
    Each function passed here must open its own connection and close it.
  - Use QRunnable + QThreadPool (NOT QThread subclassing).
"""

from __future__ import annotations

import traceback
from typing import Callable, Any, Optional

from PySide6.QtCore import QRunnable, QThreadPool, Signal, QObject


class WorkerSignals(QObject):
    """Signals emitted by DBWorker back onto the Qt event loop."""
    finished = Signal()          # always fires, even on error
    error = Signal(str)          # full traceback as string
    result = Signal(object)      # return value of the callable

    def __init__(self, parent=None):
        super().__init__(parent)


class DBWorker(QRunnable):
    """
    Generic QRunnable that executes a callable in Qt's global thread-pool.

    Each worker is fire-and-forget; results are delivered via Qt signals so
    that slot code runs back on the main thread (or whichever thread owns
    the connected object).
    """

    def __init__(self, fn: Callable, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        
        # Parenting to QApplication prevents the C++ QObject from being deleted 
        # while the thread is still using it, even if the Python wrapper is flaky.
        from PySide6.QtWidgets import QApplication
        parent = QApplication.instance()
        self.signals = WorkerSignals(parent)
        
        # Keep the worker alive until run() finishes
        self.setAutoDelete(True)

    def run(self) -> None:  # executed on a pool thread
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception:
            self.signals.error.emit(traceback.format_exc())
        finally:
            self.signals.finished.emit()


# Global registry to prevent garbage collection of workers while they are running.
_active_workers: set[DBWorker] = set()
_pinned_signals: set[WorkerSignals] = set()

def run_in_thread(
    fn: Callable,
    *args: Any,
    on_result: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
    on_finished: Optional[Callable] = None,
    **kwargs: Any,
) -> DBWorker:
    """
    Submit *fn* to Qt's global thread-pool and return the worker.

    Keyword-only callbacks:
        on_result(result)   – called with the return value on success
        on_error(tb: str)   – called with the full traceback string on failure
        on_finished()       – called unconditionally when the worker exits
    """
    worker = DBWorker(fn, *args, **kwargs)
    
    # Protect both worker and signals from garbage collection
    _active_workers.add(worker)
    _pinned_signals.add(worker.signals)
    
    if on_result is not None:
        worker.signals.result.connect(on_result)
    if on_error is not None:
        worker.signals.error.connect(on_error)
    
    # Internal cleanup callback
    def _cleanup():
        _pinned_signals.discard(worker.signals)
        _active_workers.discard(worker)
        if on_finished is not None:
            on_finished()
            
    worker.signals.finished.connect(_cleanup)
    
    QThreadPool.globalInstance().start(worker)
    return worker

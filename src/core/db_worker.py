import threading
import queue
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

class DatabaseWorker(threading.Thread):
    """
    A dedicated background thread for handling blocking I/O operations.
    Prevents the main GUI thread from stalling during SQLite writes or file operations.
    """
    def __init__(self):
        super().__init__(name="DatabaseWorker", daemon=True)
        self._queue = queue.Queue()
        self._stop_event = threading.Event()

    def run(self):
        logger.info("DatabaseWorker thread started.")
        while not self._stop_event.is_set():
            try:
                # Wait for a task with a timeout to allow checking stop_event
                task = self._queue.get(timeout=1.0)
                if task is None:
                    break
                
                func, args, kwargs, callback = task
                try:
                    result = func(*args, **kwargs)
                    if callback:
                        # Callbacks should ideally be thread-safe or use signals to talk to UI
                        callback(result)
                except Exception as e:
                    logger.error(f"DatabaseWorker task failed: {e}", exc_info=True)
                finally:
                    self._queue.task_done()
            except queue.Empty:
                continue

    def submit(self, func: Callable, *args, **kwargs):
        """Submit a function to be executed in the background."""
        # Optional callback can be passed as a kwarg
        callback = kwargs.pop('callback', None)
        self._queue.put((func, args, kwargs, callback))

    def stop(self):
        self._stop_event.set()
        self._queue.put(None)

# Global singleton
db_worker = DatabaseWorker()
db_worker.start()

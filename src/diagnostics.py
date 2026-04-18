import sys
import time
import threading
import traceback
import functools
import sqlite3
import asyncio
from pathlib import Path
from datetime import datetime
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from PySide6.QtCore import QTimer, QCoreApplication
from PySide6.QtGui import QGuiApplication, QFontDatabase



LOG_DIR = Path.cwd() / "logs"
LOG_DIR.mkdir(exist_ok=True)

def _log(severity: str, module: str, message: str, filename: str = "freeze_watchdog.log"):
    """Write structured log messages to the console and specified file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    log_line = f"[{timestamp}] [{severity}] [{module}] {message}"
    print(log_line)
    try:
        with open(LOG_DIR / filename, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception:
        pass


# ── 1. MAIN THREAD WATCHDOG ────────────────────────────────────────────────
_last_heartbeat = time.time()

def _heartbeat_slot():
    global _last_heartbeat
    _last_heartbeat = time.time()

def _watchdog_loop(main_thread_id):
    while True:
        time.sleep(0.5)
        now = time.time()
        elapsed = now - _last_heartbeat
        
        if elapsed > 1.5:
            # Main thread is stale
            frame = sys._current_frames().get(main_thread_id)
            stack = ""
            if frame:
                stack = "".join(traceback.format_stack(frame))
            _log(
                "HEARTBEAT", 
                "WATCHDOG", 
                f"Main thread frozen for {elapsed:.2f}s.\nTraceback:\n{stack}",
                "freeze_watchdog.log"
            )


# ── 2. SLOW SLOT DETECTOR ────────────────────────────────────────────────
def monitor_slot(func):
    """Decorator to measure and log slow Qt slots."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        res = func(*args, **kwargs)
        duration = (time.time() - start) * 1000
        
        if duration > 100:
            import inspect
            try:
                # Get the caller of this wrapped function
                frame = inspect.currentframe().f_back
                caller = inspect.getframeinfo(frame)
                caller_info = f"{Path(caller.filename).name}:{caller.lineno}"
            except Exception:
                caller_info = "unknown"
                
            _log("SLOW_SLOT", "SLOT", f"Slot '{func.__name__}' took {duration:.1f}ms. Caller: {caller_info}")
        return res
    return wrapper


# ── 3. SQLITE CONTENTION LOGGER ───────────────────────────────────────────
_original_connect = sqlite3.connect

class MonitoredCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, *args, **kwargs):
        start = time.time()
        
        # Check if we are running the query on the main GUI thread
        is_main = threading.current_thread() is threading.main_thread()
        if is_main:
            _log("SQLITE", "DB", f"CRITICAL: SQLite execute on MAIN thread! Query: {sql[:100]}...")
            
        res = self._cursor.execute(sql, *args, **kwargs)
        
        duration = (time.time() - start) * 1000
        if duration > 50:
            import inspect
            try:
                frame = inspect.currentframe().f_back
                caller = inspect.getframeinfo(frame)
                caller_info = f"{Path(caller.filename).name}:{caller.lineno}"
            except Exception:
                caller_info = "unknown"
            _log("SQLITE", "DB", f"Slow query ({duration:.1f}ms): {sql[:150]}... Caller: {caller_info}")
        return res

    def __getattr__(self, name):
        return getattr(self._cursor, name)

class MonitoredConnection:
    def __init__(self, conn):
        self._conn = conn
    
    def cursor(self, *args, **kwargs):
        return MonitoredCursor(self._conn.cursor(*args, **kwargs))
    
    def execute(self, sql, *args, **kwargs):
        return self.cursor().execute(sql, *args, **kwargs)
        
    def __enter__(self):
        self._conn.__enter__()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._conn.__exit__(exc_type, exc_val, exc_tb)
        
    def __getattr__(self, name):
        return getattr(self._conn, name)

def _monitored_connect(*args, **kwargs):
    conn = _original_connect(*args, **kwargs)
    return MonitoredConnection(conn)

# Monkey-patch sqlite3
sqlite3.connect = _monitored_connect


# ── 4. PLAYWRIGHT / ASYNCIO BRIDGE CHECK ─────────────────────────────────
_original_asyncio_run = asyncio.run

def _monitored_asyncio_run(*args, **kwargs):
    if threading.current_thread() is threading.main_thread():
        import inspect
        try:
            frame = inspect.currentframe().f_back
            caller = inspect.getframeinfo(frame)
            caller_info = f"{Path(caller.filename).name}:{caller.lineno}"
        except Exception:
            caller_info = "unknown"
        _log("ASYNCIO", "BRIDGE", f"CRITICAL: asyncio.run() on main Qt thread! Caller: {caller_info}")
    return _original_asyncio_run(*args, **kwargs)

asyncio.run = _monitored_asyncio_run

_original_run_until_complete = asyncio.BaseEventLoop.run_until_complete

def _monitored_run_until_complete(self, *args, **kwargs):
    if threading.current_thread() is threading.main_thread():
        import inspect
        try:
            frame = inspect.currentframe().f_back
            caller = inspect.getframeinfo(frame)
            caller_info = f"{Path(caller.filename).name}:{caller.lineno}"
        except Exception:
            caller_info = "unknown"
        _log("ASYNCIO", "BRIDGE", f"CRITICAL: loop.run_until_complete() on main Qt thread! Caller: {caller_info}")
    return _original_run_until_complete(self, *args, **kwargs)

asyncio.BaseEventLoop.run_until_complete = _monitored_run_until_complete


# ── 5. MEMORY + CPU SNAPSHOT ──────────────────────────────────────────────
def _resource_snapshot_loop():
    while True:
        try:
            process = psutil.Process()
            rss_mb = process.memory_info().rss / (1024 * 1024)
            cpu_pct = process.cpu_percent(interval=1.0)
            threads = process.num_threads()
            
            # Process.num_fds() is Unix-only, fallback for Windows
            try:
                fds = process.num_handles() if hasattr(process, 'num_handles') else process.num_fds()
            except AttributeError:
                try:
                    fds = len(process.open_files())
                except Exception:
                    fds = 0
            
            _log(
                "RESOURCE", 
                "USAGE", 
                f"RSS: {rss_mb:.1f}MB | CPU: {cpu_pct:.1f}% | Threads: {threads} | Handles/FDs: {fds}", 
                "resource_snapshot.log"
            )
        except Exception as e:
            _log("RESOURCE", "USAGE", f"Error collecting metrics: {e}", "resource_snapshot.log")
        
        # Sleep exactly 10s between snapshots
        time.sleep(10)


# ── 6. UI METRICS & FONTS ────────────────────────────────────────────────
def _get_ui_metrics():
    """Captures screen resolution, scaling, and DPI data."""
    metrics = []
    try:
        screens = QGuiApplication.screens()
        for i, screen in enumerate(screens):
            geom = screen.geometry()
            dpr = screen.devicePixelRatio()
            logical_dpi = screen.logicalDotsPerInch()
            physical_dpi = screen.physicalDotsPerInch()
            metrics.append(
                f"Screen {i}: {geom.width()}x{geom.height()} | DPR: {dpr:.2f} | DPI: L={logical_dpi:.1f}/P={physical_dpi:.1f}"
            )
    except Exception as e:
        metrics.append(f"Error collecting screen metrics: {e}")
    return metrics

def _check_font_integrity():
    """Verifies that the required PT Root UI font is available."""
    db = QFontDatabase()
    families = db.families()
    target = "PT Root UI"
    if target in families:
        return f"Font '{target}' is LOADED and available."
    else:
        # Check for partial matches or common fallback names
        matches = [f for f in families if "PT Root" in f]
        if matches:
            return f"Font '{target}' NOT found. Closest matches: {', '.join(matches)}"
        return f"Font '{target}' is MISSING (Fallback expected)."

def get_ui_health_snapshot():
    """Returns a dictionary summary of the current UI and system health."""
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "screens": _get_ui_metrics(),
        "fonts": _check_font_integrity(),
        "uptime": f"{time.time() - _last_heartbeat:.1f}s since heartbeat",
    }
    
    if HAS_PSUTIL:
        try:
            p = psutil.Process()
            snapshot.update({
                "memory_rss_mb": p.memory_info().rss / (1024 * 1024),
                "cpu_percent": p.cpu_percent(),
                "threads": p.num_threads()
            })
        except: pass
        
    return snapshot

# ── ENTRY POINT ──────────────────────────────────────────────────────────

_timer = None

def install_diagnostics(app: QCoreApplication):
    """
    Installs all runtime diagnostics. 
    Call this once in your main entry point before app.exec().
    """
    global _timer
    
    # Needs to be called from the main thread
    main_thread_id = threading.current_thread().ident
    if not isinstance(app, QCoreApplication):
        _log("ERROR", "INIT", "install_diagnostics must be called with a valid QApplication instance!")
        return
        
    # 1. Main Thread Watchdog
    _timer = QTimer(app)
    _timer.timeout.connect(_heartbeat_slot)
    _timer.start(500)
    
    wt = threading.Thread(target=_watchdog_loop, args=(main_thread_id,), daemon=True, name="Diag-Watchdog")
    wt.start()
    
    # 2. Resource Snapshot
    if HAS_PSUTIL:
        rt = threading.Thread(target=_resource_snapshot_loop, daemon=True, name="Diag-Resource")
        rt.start()
    else:
        _log("WARNING", "INIT", "psutil not found. Resource snapshots (CPU/Memory) are disabled.")

    
    # 3. UI Metrics Logging
    try:
        ui_info = " | ".join(_get_ui_metrics())
        font_status = _check_font_integrity()
        _log("INFO", "UI", f"{ui_info} | {font_status}", "ui_diagnostics.log")
    except Exception as e:
        _log("ERROR", "UI", f"Failed to log initial UI metrics: {e}", "ui_diagnostics.log")

    _log("INFO", "INIT", "ZUGZWANG Diagnostics installed successfully.")


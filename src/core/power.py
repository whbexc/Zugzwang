"""
ZUGZWANG - Power & Sleep Management
Prevents macOS system sleep while long-running tasks (scraping leads, batch PDF exports, sending emails)
are active, while still allowing the display to dim or turn off.
"""

from __future__ import annotations
import os
import sys
import threading
import subprocess
from typing import Optional
from .logger import get_logger

logger = get_logger("power")

class WakeLock:
    _lock = threading.Lock()
    _active_count = 0
    _process: Optional[subprocess.Popen] = None
    _reasons: dict[str, int] = {}

    @classmethod
    def acquire(cls, reason: str = "Background Task") -> None:
        """
        Acquire a sleep prevention lock for the given reason.
        On macOS, launches `caffeinate -i -s -w <pid>` if this is the first active lock.
        """
        with cls._lock:
            cls._active_count += 1
            cls._reasons[reason] = cls._reasons.get(reason, 0) + 1
            
            if cls._active_count == 1:
                cls._start_caffeinate(reason)
            else:
                logger.debug(f"[WakeLock] Acquired lock for '{reason}' (total active: {cls._active_count})")

    @classmethod
    def release(cls, reason: str = "Background Task") -> None:
        """
        Release a sleep prevention lock. When the active count reaches 0, system sleep is restored.
        """
        with cls._lock:
            if cls._active_count <= 0:
                return
                
            cls._active_count -= 1
            if reason in cls._reasons:
                cls._reasons[reason] -= 1
                if cls._reasons[reason] <= 0:
                    del cls._reasons[reason]
                    
            if cls._active_count == 0:
                cls._stop_caffeinate()
            else:
                logger.debug(f"[WakeLock] Released lock for '{reason}' (total active: {cls._active_count})")

    @classmethod
    def _start_caffeinate(cls, reason: str) -> None:
        if sys.platform == "darwin":
            try:
                # -i: Prevent system idle sleep
                # -s: Prevent system sleep on AC power
                # -w: Automatically release assertion if process exits
                cls._process = subprocess.Popen(
                    ["caffeinate", "-i", "-s", "-w", str(os.getpid())],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logger.info(f"[WakeLock] System sleep prevented for '{reason}' (PID: {cls._process.pid})")
            except Exception as e:
                logger.warning(f"[WakeLock] Failed to start caffeinate: {e}")
        elif sys.platform == "win32":
            try:
                import ctypes
                # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
                logger.info(f"[WakeLock] System sleep prevented on Windows for '{reason}'")
            except Exception as e:
                logger.warning(f"[WakeLock] Failed to set execution state on Windows: {e}")

    @classmethod
    def _stop_caffeinate(cls) -> None:
        if sys.platform == "darwin" and cls._process:
            try:
                cls._process.terminate()
                cls._process.wait(timeout=2.0)
                logger.info("[WakeLock] Restored normal system sleep behavior.")
            except Exception as e:
                logger.debug(f"[WakeLock] Error stopping caffeinate: {e}")
            finally:
                cls._process = None
        elif sys.platform == "win32":
            try:
                import ctypes
                # ES_CONTINUOUS
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
                logger.info("[WakeLock] Restored normal system sleep behavior on Windows.")
            except Exception:
                pass

    @classmethod
    def is_active(cls) -> bool:
        with cls._lock:
            return cls._active_count > 0

    @classmethod
    def get_active_reasons(cls) -> list[str]:
        with cls._lock:
            return list(cls._reasons.keys())

# 1.1.0 Beta5

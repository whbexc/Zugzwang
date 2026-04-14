"""
ZUGZWANG - Win32 RPC Cache Patch
=================================
Monkey-patches the three blocking Win32 RPC calls inside qframelesswindow
that are called on *every* WM_NCHITTEST / WM_NCCALCSIZE message and can
stall the main thread for 5–20 seconds when the Win32 scheduler is busy.

Functions patched (all in qframelesswindow.utils.win32_utils):
  • getResizeBorderThickness  – cached for 1 s per (hWnd, horizontal)
  • Taskbar.getPosition       – cached for 2 s per hWnd
  • isMaximized               – cached for 100 ms per hWnd

Call ``install()`` once, before the QApplication event loop starts.
"""

from __future__ import annotations

import time
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── TTL cache ────────────────────────────────────────────────────────────────

class _TTLCache:
    """Minimal thread-safe TTL cache keyed by arbitrary hashable keys."""

    __slots__ = ("_ttl", "_store")

    def __init__(self, ttl: float):
        self._ttl: float = ttl
        self._store: dict[Any, tuple[Any, float]] = {}

    def get(self, key, _miss=object()):
        entry = self._store.get(key, _miss)
        if entry is _miss:
            return _miss
        value, expires = entry
        if time.monotonic() > expires:
            del self._store[key]
            return _miss
        return value

    def set(self, key, value):
        self._store[key] = (value, time.monotonic() + self._ttl)

    _MISS = object()  # sentinel re-exported for callers

_MISS = _TTLCache._MISS


# ── Patch install ─────────────────────────────────────────────────────────────

_installed = False


def install() -> None:
    """Apply all patches. Safe to call multiple times (idempotent)."""
    global _installed
    if _installed:
        return

    try:
        import qframelesswindow.utils.win32_utils as _wu
        _patch_resize_border(_wu)
        _patch_taskbar_position(_wu)
        _patch_is_maximized(_wu)
        _installed = True
        logger.info("[win32_patch] Win32 RPC cache patches installed successfully.")
    except Exception as exc:
        logger.warning(f"[win32_patch] Could not install Win32 patches: {exc}")


# ── Individual patches ────────────────────────────────────────────────────────

def _patch_resize_border(wu) -> None:
    """Cache getResizeBorderThickness for 1 s per (hWnd, horizontal)."""
    _orig = wu.getResizeBorderThickness
    _cache = _TTLCache(ttl=1.0)

    def _patched(hWnd, horizontal=True):
        key = (int(hWnd) if hWnd else 0, horizontal)
        result = _cache.get(key)
        if result is _MISS:
            result = _orig(hWnd, horizontal)
            _cache.set(key, result)
        return result

    wu.getResizeBorderThickness = _patched


def _patch_taskbar_position(wu) -> None:
    """Cache Taskbar.getPosition for 2 s per hWnd (taskbar rarely moves)."""
    _orig = wu.Taskbar.getPosition.__func__  # classmethod -> underlying function
    _cache = _TTLCache(ttl=2.0)

    @classmethod
    def _patched(cls, hWnd):
        key = int(hWnd) if hWnd else 0
        result = _cache.get(key)
        if result is _MISS:
            result = _orig(cls, hWnd)
            _cache.set(key, result)
        return result

    wu.Taskbar.getPosition = _patched


def _patch_is_maximized(wu) -> None:
    """Cache isMaximized for 100 ms per hWnd."""
    _orig = wu.isMaximized
    _cache = _TTLCache(ttl=0.1)

    def _patched(hWnd):
        key = int(hWnd) if hWnd else 0
        result = _cache.get(key)
        if result is _MISS:
            result = _orig(hWnd)
            _cache.set(key, result)
        return result

    wu.isMaximized = _patched

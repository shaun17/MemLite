"""Compatibility package for legacy memlite imports."""

from importlib import import_module

_memolite = import_module("memolite")

__all__ = getattr(_memolite, "__all__", [])
__path__ = _memolite.__path__

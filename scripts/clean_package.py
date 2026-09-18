#!/usr/bin/env python3
import sys as _louter_sys
_louter_sys.dont_write_bytecode = True
"""Remove generated files that must never enter the published npm/ClawPack artifact."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

for cache in ROOT.rglob("__pycache__"):
    if cache.is_dir():
        shutil.rmtree(cache)

for pattern in ("*.pyc", "*.pyo", "*.bak", "*.pre-*"):
    for p in ROOT.rglob(pattern):
        if p.is_file():
            p.unlink()

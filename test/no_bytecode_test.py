#!/usr/bin/env python3
"""Regression test: packaged Python entry points must not create bytecode after extraction."""
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("*.pyc", "*.pyo")

def bad(root):
    rows = [p for p in root.rglob("__pycache__") if p.is_dir()]
    for pattern in FORBIDDEN:
        rows.extend(p for p in root.rglob(pattern) if p.is_file())
    return sorted({str(p.relative_to(root)) for p in rows})

def run_clean(args, cwd, env):
    subprocess.run(args, cwd=cwd, env=env, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

with tempfile.TemporaryDirectory() as td:
    temp = Path(td)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    packed = subprocess.run(["npm", "pack", "--silent"], cwd=ROOT, env=env, check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout.strip().splitlines()[-1]
    tgz = ROOT / packed
    try:
        with tarfile.open(tgz, "r:gz") as archive:
            archive.extractall(temp, filter="data")
        package = temp / "package"
        before = bad(package)
        if before:
            raise AssertionError("bytecode already present in packed artifact: " + ", ".join(before))

        # Exercise entry points that import sibling helpers. Help/preview paths avoid
        # changing OpenClaw or GitHub state but reproduce Python's import machinery.
        commands = [
            [sys.executable, "-B", "scripts/install.py", "--help"],
            [sys.executable, "-B", "scripts/setup.py", "--help"],
            [sys.executable, "-B", "scripts/setup_local.py", "--help"],
            [sys.executable, "-B", "scripts/louterctl.py", "--help"],
            [sys.executable, "-B", "scripts/smoke.py", "--help"],
            [sys.executable, "-B", "scripts/publish.py", "--help"],
            [sys.executable, "-B", "scripts/telemetry.py", "--state-dir", str(temp/"state"), "preview"],
            [sys.executable, "-B", "scripts/aggregate_telemetry.py", "--help"],
        ]
        for command in commands:
            run_clean(command, package, env)
            found = bad(package)
            if found:
                raise AssertionError(f"{command[2]} created bytecode: " + ", ".join(found))

        # Also exercise the shell entry point, which must export the no-bytecode
        # policy before Python imports common.py.
        run_clean(["bash", "install.sh", "--help"], package, env)
        found = bad(package)
        if found:
            raise AssertionError("install.sh created bytecode: " + ", ".join(found))
    finally:
        tgz.unlink(missing_ok=True)

print("PASS packaged Python entry points create no bytecode")

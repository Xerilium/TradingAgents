"""Python runtime policy: discover the host interpreter, never bundle one.

Two different numbers are kept apart on purpose:

* the support window (``SUPPORTED_MIN``/``SUPPORTED_MAX_EXCLUSIVE``) is what the
  code runs on. The upper bound comes from upstream, not from us: nautilus-trader
  publishes ``Requires-Python: <3.15,>=3.12`` and ships Windows wheels for
  cp312/cp313/cp314 only, so the engine has no 3.15 wheel yet.
* the release line is the single interpreter minor each reviewed lock was
  compiled for. It is read from the lock header instead of being written here, so
  a lock can never be applied to an interpreter it was not resolved for.

No patch version, wheel tag, or interpreter path is pinned anywhere: an
interpreter is *discovered* on the host, the ABI tag is *derived* from it, and the
dependency set stays exactly as reviewed.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Upstream ceiling, verified against nautilus-trader wheel tags on PyPI.
SUPPORTED_MIN = (3, 12)
SUPPORTED_MAX_EXCLUSIVE = (3, 15)

KINDS = ("desk", "native")


def target() -> tuple[str, str]:
    """Return the (platform name, wheel tag) pair for this build host."""
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in ("amd64", "x86_64"):
        return "windows", "win_amd64"
    if sys.platform == "darwin" and machine == "arm64":
        if tuple(int(x) for x in platform.mac_ver()[0].split(".")[:1]) < (26,):
            raise RuntimeError("The official Nautilus wheel requires macOS 26 or later")
        return "macos-arm64", "macosx_26_0_arm64"
    raise RuntimeError("Supported build hosts are Windows x64 and macOS 26+ arm64")


def lock_minor(lock: Path) -> tuple[int, int]:
    """Read the interpreter minor a reviewed lock was compiled for."""
    header = "\n".join(lock.read_text(encoding="utf-8").splitlines()[:4])
    match = re.search(r"--python-version\s+(\d+)\.(\d+)", header)
    if not match:
        raise RuntimeError(f"Lock does not declare --python-version: {lock}")
    minor = (int(match.group(1)), int(match.group(2)))
    if not supported(minor):
        raise RuntimeError(f"{lock.name} is compiled for Python {minor[0]}.{minor[1]}, "
                           f"outside the supported window {version_text(SUPPORTED_MIN)}"
                           f"-{version_text((SUPPORTED_MAX_EXCLUSIVE[0], SUPPORTED_MAX_EXCLUSIVE[1] - 1))}")
    return minor


def supported(minor: tuple[int, int]) -> bool:
    return SUPPORTED_MIN <= minor < SUPPORTED_MAX_EXCLUSIVE


def version_text(minor: tuple[int, int]) -> str:
    return f"{minor[0]}.{minor[1]}"


def abi_tag(minor: tuple[int, int]) -> str:
    """The interpreter's own ABI tag; derived, never hard-coded."""
    return f"cp{minor[0]}{minor[1]}"


def interpreter_path(root: Path) -> Path:
    return root / ("python.exe" if os.name == "nt" else "bin/python3")


def venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / "Scripts/python.exe"
    return root / "bin/python3"


def version_of(python: Path) -> tuple[int, int] | None:
    try:
        out = subprocess.run([str(python), "-I", "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
                             capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    parts = out.split(".")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    return int(parts[0]), int(parts[1])


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    if os.name == "nt":
        launcher = shutil.which("py")
        if launcher:
            try:
                listing = subprocess.run([launcher, "--list-paths"], capture_output=True, text=True, timeout=60).stdout
            except (OSError, subprocess.SubprocessError):
                listing = ""
            for line in listing.splitlines():
                match = re.search(r"\s+([A-Za-z]:[^\"]*python\.exe)\s*$", line)
                if match:
                    paths.append(Path(match.group(1)))
        local = os.environ.get("LOCALAPPDATA")
        if local:
            core = Path(local) / "Python"
            if core.is_dir():
                paths.extend(sorted(core.glob("pythoncore-3.*-64/python.exe"), reverse=True))
        for name in ("python3", "python"):
            found = shutil.which(name)
            if found:
                paths.append(Path(found))
    else:
        for minor in range(SUPPORTED_MIN[1], SUPPORTED_MAX_EXCLUSIVE[1]):
            for name in (f"python3.{minor}", "python3"):
                found = shutil.which(name)
                if found:
                    paths.append(Path(found))
        paths.extend(sorted(Path("/usr/local/bin").glob("python3.*"), reverse=True))
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower()
        if key not in seen and path.is_file():
            seen.add(key)
            unique.append(path)
    return unique


def discover(minor: tuple[int, int]) -> Path | None:
    """Find a host interpreter for the requested minor, or None."""
    for path in _candidate_paths():
        if version_of(path) == minor:
            return path
    return None


def installed_interpreters() -> list[tuple[tuple[int, int], Path]]:
    result: list[tuple[tuple[int, int], Path]] = []
    for path in _candidate_paths():
        version = version_of(path)
        if version:
            result.append((version, path))
    return result


def environment_base(environment: Path) -> tuple[str | None, bool]:
    """Report the interpreter a virtual environment was built from and whether it still exists."""
    config = environment / "pyvenv.cfg"
    if not config.is_file():
        return None, False
    values: dict[str, str] = {}
    for line in config.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    base = values.get("executable") or values.get("home")
    if not base:
        return None, False
    return base, Path(base.split()[0] if os.name == "nt" else base).is_file()


def environment_status(environment: Path) -> tuple[Path | None, str]:
    """Classify one runtime environment as missing, incomplete, broken, or usable."""
    python = venv_python(environment)
    if not environment.is_dir():
        return None, "missing"
    if not (environment / "pyvenv.cfg").is_file():
        if interpreter_path(environment).is_file():
            return None, "a bundled runtime rather than a virtual environment"
        return None, "incomplete"
    if not python.is_file():
        return None, "incomplete"
    base, alive = environment_base(environment)
    if not alive:
        return None, f"broken: its interpreter {base} is no longer installed"
    site = environment / ("Lib/site-packages" if os.name == "nt" else "lib")
    if not site.is_dir():
        return python, "incomplete"
    return python, "usable"


def remedy(minor: tuple[int, int]) -> str:
    text = version_text(minor)
    if os.name == "nt":
        return f"Install Python {text} with the Python Manager: py install {text}"
    return f"Install Python {text} (for example: brew install python@{text})"

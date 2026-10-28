"""Prepare isolated, relocatable runtimes for the native Tauri release host.

Run from the checkout root using an existing Python 3.11+ and uv. This prepares
only the payload; it does not build or install the desktop app.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "packaging" / "build"
PAYLOAD = ROOT / "desktop" / "src-tauri" / "payload"
CACHE = BUILD / "cache"
VERSIONS = {"desk": "3.12.10", "native": "3.13.7"}
NAUTILUS = "1.231.0"


def run(*args: object, env: dict[str, str] | None = None) -> None:
    subprocess.run([str(arg) for arg in args], cwd=ROOT, env=env, check=True)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def target() -> tuple[str, str]:
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in ("amd64", "x86_64"):
        return "windows", "win_amd64"
    if sys.platform == "darwin" and machine == "arm64":
        if tuple(int(x) for x in platform.mac_ver()[0].split(".")[:1]) < (26,):
            raise RuntimeError("The official Nautilus wheel requires macOS 26 or later")
        return "macos-arm64", "macosx_26_0_arm64"
    raise RuntimeError("Supported build hosts are Windows x64 and macOS 26+ arm64")


def interpreter(root: Path) -> Path:
    return root / ("python.exe" if sys.platform == "win32" else "bin/python3")


def package_dir(python: Path) -> Path:
    value = subprocess.check_output(
        [str(python), "-I", "-c", "import importlib.util; print(importlib.util.find_spec('tradingagents').submodule_search_locations[0])"],
        text=True, cwd=BUILD,
    ).strip()
    return Path(value)


def stage_app(wheel: Path, manifest: bytes) -> None:
    """Stage replaceable project code separately from the persistent runtimes."""
    app = PAYLOAD / "app"
    if app.exists():
        shutil.rmtree(app)
    app.mkdir(parents=True)
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(app)
    target = app / "tradingagents/assets/runtime-manifests/nautilus-v1-runtime-manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(manifest)


def native_manifest(tag: str, lock: Path) -> dict:
    with urllib.request.urlopen(f"https://pypi.org/pypi/nautilus-trader/{NAUTILUS}/json") as response:
        releases = json.load(response)["urls"]
    suffix = f"-cp313-cp313-{tag}.whl"
    matches = [item for item in releases if item["filename"].endswith(suffix)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one official Nautilus wheel for {suffix}")
    item = matches[0]
    expected = item["digests"]["sha256"]
    if f"--hash=sha256:{expected}" not in lock.read_text(encoding="utf-8"):
        raise RuntimeError("Official Nautilus wheel hash is absent from the reviewed lock")
    wheel = BUILD / item["filename"]
    with urllib.request.urlopen(item["url"]) as source, wheel.open("wb") as dest:
        shutil.copyfileobj(source, dest)
    if digest(wheel) != expected:
        raise RuntimeError("Downloaded Nautilus wheel does not match its locked SHA-256")
    files = {}
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            name = info.filename
            if name.startswith("nautilus_trader/") and name.endswith((".py", ".pyd", ".so", ".dll", ".dylib")):
                data = archive.read(info)
                files[name.removeprefix("nautilus_trader/")] = {
                    "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()
                }
    if not files:
        raise RuntimeError("No code files found in the official Nautilus wheel")
    return {
        "nautilus_version": NAUTILUS,
        "source_commit": "27a8e54e7ac3c57d6cbf8891f0283dfbaee97317",
        "source_tag": "v1.231.0",
        "official_wheel": {"filename": item["filename"], "url": item["url"],
                           "size": item["size"], "sha256": expected},
        "installed_files": files,
    }


def main() -> None:
    name, tag = target()
    locks = {kind: ROOT / "packaging" / f"{kind}-{name}.lock" for kind in VERSIONS}
    for lock in locks.values():
        if not lock.is_file():
            raise RuntimeError(f"Missing reviewed platform lock: {lock}")
    BUILD.mkdir(parents=True, exist_ok=True)
    if PAYLOAD.exists():
        raise RuntimeError(f"Remove the prior generated payload first: {PAYLOAD}")
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv is required on the build host")
    uv_version = subprocess.check_output([uv, "--version"], text=True).strip()
    if uv_version.split()[:2] != ["uv", "0.12.22"]:
        raise RuntimeError(f"Expected uv 0.12.22, got {uv_version}")
    manifest = native_manifest(tag, locks["native"])
    wheel_dir = BUILD / "wheels"
    wheel_dir.mkdir(exist_ok=True)
    run(uv, "build", "--wheel", "--out-dir", wheel_dir, "--cache-dir", CACHE,
        "--build-constraints", ROOT / "packaging" / "build-constraints.txt")
    wheels = list(wheel_dir.glob("tradingagents-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("Expected exactly one project wheel")
    for kind, version in VERSIONS.items():
        managed = BUILD / f"python-{kind}"
        run(uv, "python", "install", version, "--install-dir", managed, "--no-bin", "--no-registry", "--cache-dir", CACHE)
        installations = [path for path in managed.iterdir() if path.is_dir() and path.name.startswith(f"cpython-{version}-")]
        if len(installations) != 1:
            raise RuntimeError(f"Expected one standalone Python under {managed}")
        destination = PAYLOAD / kind
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(installations[0]), str(destination))
        python = interpreter(destination)
        run(uv, "pip", "install", "--python", python, "--system", "--break-system-packages", "--only-binary", ":all:",
            "--require-hashes", "--no-deps", "--link-mode", "copy", "--cache-dir", CACHE,
            "-r", locks[kind])
        run(uv, "pip", "install", "--python", python, "--system", "--break-system-packages", "--no-deps", "--link-mode", "copy",
            "--cache-dir", CACHE, wheels[0])
        target_manifest = package_dir(python) / "assets" / "runtime-manifests" / "nautilus-v1-runtime-manifest.json"
        target_manifest.parent.mkdir(parents=True, exist_ok=True)
        target_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    native_site = package_dir(interpreter(PAYLOAD / "native")).parent / "nautilus_trader"
    for relative, expected in manifest["installed_files"].items():
        if digest(native_site / relative) != expected["sha256"]:
            raise RuntimeError(f"Installed native file differs from official wheel: {relative}")
    stage_app(wheels[0], (json.dumps(manifest, indent=2) + "\n").encode())
    revision = subprocess.check_output(["rtk", "proxy", "git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["rtk", "proxy", "git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True).strip())
    provenance = {"source_revision": revision, "working_changes_present": dirty,
                  "project_wheel_sha256": digest(wheels[0]), "platform": name,
                  "python_versions": VERSIONS, "uv_version": uv_version,
                  "python_executable_sha256": {kind: digest(interpreter(PAYLOAD / kind)) for kind in VERSIONS},
                  "dependency_locks_sha256": {kind: digest(lock) for kind, lock in locks.items()},
                  "nautilus_wheel": manifest["official_wheel"]}
    (PAYLOAD / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    size = sum(path.stat().st_size for path in PAYLOAD.rglob("*") if path.is_file())
    print(f"Prepared payload: {size / 1024**3:.2f} GiB ({size} bytes)")


if __name__ == "__main__":
    main()

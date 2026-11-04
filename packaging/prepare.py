"""Prepare the release payload: application code plus reviewed wheelhouses.

Run from the checkout root using any Python in the support window. The payload
holds no interpreter and no virtual environment. It holds the replaceable
application code and, for each runtime, the exact reviewed wheels the desktop
host installs offline into a profile environment the first time that environment
is needed. App updates replace payload/app and never touch those environments.

The interpreter for each runtime is discovered on this host; its minor comes from
the reviewed lock header, so the wheels in a wheelhouse and the environment the
host later creates always agree.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtimes  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "packaging" / "build"
PAYLOAD = ROOT / "desktop" / "src-tauri" / "payload"
CACHE = BUILD / "cache"
NAUTILUS = "1.231.0"
MIN_UV = (0, 12)


def run(*args, env=None):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, env=env, check=True)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stage_app(wheel, manifest):
    """Stage replaceable project code separately from the dependency wheelhouses."""
    app = PAYLOAD / "app"
    if app.exists():
        shutil.rmtree(app)
    app.mkdir(parents=True)
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(app)
    target = app / "tradingagents/assets/runtime-manifests/nautilus-v1-runtime-manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(manifest)


def native_manifest(minor, tag, lock):
    """Build the runtime contract from the wheel matching the discovered interpreter."""
    with urllib.request.urlopen(f"https://pypi.org/pypi/nautilus-trader/{NAUTILUS}/json") as response:
        releases = json.load(response)["urls"]
    abi = runtimes.abi_tag(minor)
    suffix = "-{}-{}-{}.whl".format(abi, abi, tag)
    matches = [item for item in releases if item["filename"].endswith(suffix)]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected one official Nautilus wheel for {}; nautilus-trader {} does not support python {}".format(
                suffix, NAUTILUS, runtimes.version_text(minor)))
    item = matches[0]
    expected = item["digests"]["sha256"]
    if "--hash=sha256:" + expected not in lock.read_text(encoding="utf-8"):
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
        "python_abi": abi,
        "official_wheel": {"filename": item["filename"], "url": item["url"],
                           "size": item["size"], "sha256": expected},
        "installed_files": files,
    }


def find_uv():
    """Locate build-time uv (never shipped): PATH first, then the repository build env."""
    found = shutil.which("uv")
    if found:
        return found
    candidate = ROOT / ".venv-build" / ("Scripts/uv.exe" if os.name == "nt" else "bin/uv")
    if candidate.is_file():
        return str(candidate)
    raise RuntimeError(
        "uv is required on the build host (build time only; it is not shipped). Create the repository "
        "build environment and install it there: python -m venv .venv-build, then "
        ".venv-build/Scripts/python -m pip install uv")


def wheelhouse(python, minor, tag, lock, destination):
    """Fetch the reviewed wheels for one runtime, verifying every hash while downloading."""
    destination.mkdir(parents=True)
    run(python, "-m", "pip", "download", "--require-hashes", "--only-binary", ":all:",
        "--python-version", runtimes.version_text(minor), "--implementation", "cp",
        "--abi", runtimes.abi_tag(minor), "--platform", tag,
        "--cache-dir", CACHE, "-r", lock, "-d", destination)
    wheels = list(destination.glob("*.whl"))
    if not wheels:
        raise RuntimeError("Wheelhouse for {} is empty".format(lock.name))
    return len(wheels)


def main():
    name, tag = runtimes.target()
    locks = {kind: ROOT / "packaging" / "{}-{}.lock".format(kind, name) for kind in runtimes.KINDS}
    for lock in locks.values():
        if not lock.is_file():
            raise RuntimeError("Missing reviewed platform lock: {}".format(lock))
    minors = {kind: runtimes.lock_minor(lock) for kind, lock in locks.items()}
    if len(set(minors.values())) != 1:
        raise RuntimeError("The runtimes must share one interpreter line, got {}".format(minors))
    minor = minors["desk"]
    base = runtimes.discover(minor)
    if not base:
        raise RuntimeError("No python {} interpreter found. {}".format(runtimes.version_text(minor), runtimes.remedy(minor)))
    build_python = subprocess.check_output(
        [base, "-I", "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"], text=True).strip()
    uv = find_uv()
    uv_version = subprocess.check_output([uv, "--version"], text=True).strip()
    if tuple(int(x) for x in uv_version.split()[1].split(".")[:2]) < MIN_UV:
        raise RuntimeError("uv {}.{} or newer is required, got {}".format(MIN_UV[0], MIN_UV[1], uv_version))
    BUILD.mkdir(parents=True, exist_ok=True)
    if PAYLOAD.exists():
        raise RuntimeError("Remove the prior generated payload first: {}".format(PAYLOAD))

    manifest = native_manifest(minor, tag, locks["native"])
    manifest_text = (json.dumps(manifest, indent=2) + "\n").encode()

    wheel_dir = BUILD / "wheels"
    wheel_dir.mkdir(exist_ok=True)
    run(uv, "build", "--wheel", "--out-dir", wheel_dir, "--cache-dir", CACHE,
        "--build-constraints", ROOT / "packaging" / "build-constraints.txt")
    wheels = list(wheel_dir.glob("tradingagents-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("Expected exactly one project wheel")

    counts = {}
    environments = {}
    for kind, lock in locks.items():
        counts[kind] = wheelhouse(base, minor, tag, lock, PAYLOAD / "wheels" / kind)
        # Ship the reviewed lock with the installer so the first run installs exactly
        # these versions and verifies every wheel hash without any network access.
        setup = PAYLOAD / "setup"
        setup.mkdir(parents=True, exist_ok=True)
        install_file = setup / "{}-requirements.txt".format(kind)
        install_file.write_bytes(lock.read_bytes())
        environments[kind] = {
            "python_minor": runtimes.version_text(minor),
            "abi": runtimes.abi_tag(minor),
            "platform": name,
            "wheelhouse": "wheels/{}".format(kind),
            "requirements": "setup/{}-requirements.txt".format(kind),
            "requirements_sha256": digest(install_file),
        }

    stage_app(wheels[0], manifest_text)
    revision = subprocess.check_output(["rtk", "proxy", "git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["rtk", "proxy", "git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True).strip())
    provenance = {
        "source_revision": revision, "working_changes_present": dirty,
        "project_wheel_sha256": digest(wheels[0]), "platform": name,
        "python_minor": runtimes.version_text(minor), "python_abi": runtimes.abi_tag(minor),
        "build_python_version": build_python, "uv_version": uv_version,
        "wheel_counts": counts,
        "dependency_locks_sha256": {kind: digest(lock) for kind, lock in locks.items()},
        "nautilus_wheel": manifest["official_wheel"],
        "environments": environments,
    }
    (PAYLOAD / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    size = sum(path.stat().st_size for path in PAYLOAD.rglob("*") if path.is_file())
    print("Prepared payload: {:.2f} GiB ({} bytes); python {} ({}); wheels desk={} native={}".format(
        size / 1024**3, size, build_python, runtimes.abi_tag(minor), counts["desk"], counts["native"]))


if __name__ == "__main__":
    main()

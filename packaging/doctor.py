"""Report why a build or a launch cannot proceed, before it fails somewhere else.

Run from the checkout root:  python packaging/doctor.py [--profile production]

Checks the reviewed locks' interpreter line against the interpreters actually
installed on this machine, and reports the state of every runtime environment the
app or a build would use. Exits non-zero when something must be fixed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtimes  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "desktop" / "src-tauri" / "payload"
DEV_ENVIRONMENTS = {"desk": ROOT / ".venv", "native": ROOT / ".venv-nautilus-v1"}


def profile_root(profile: str) -> Path:
    config = ROOT / "desktop/src-tauri/tauri.conf.json"
    override = json.loads(config.read_text(encoding="utf-8")).get("appDirectoriesOverride", {}).get(profile)
    if override:
        return Path(override.replace("${HOME}", str(Path.home()))) / profile
    return Path.home() / ".cache/trader" / profile


def report(failures: list[str], profile: str | None) -> None:
    name, _ = runtimes.target()
    print(f"Build host: {name}")
    interpreters = runtimes.installed_interpreters()
    if not interpreters:
        print("Interpreters found: none")
    for version, path in sorted(interpreters, reverse=True):
        mark = "supported" if runtimes.supported(version) else "outside the supported window"
        print(f"  python {runtimes.version_text(version)}  {path}  ({mark})")

    for kind in runtimes.KINDS:
        lock = ROOT / "packaging" / f"{kind}-{name}.lock"
        if not lock.is_file():
            failures.append(f"Missing reviewed lock for this platform: {lock}")
            print(f"{kind} lock: MISSING ({lock})")
            continue
        minor = runtimes.lock_minor(lock)
        found = runtimes.discover(minor)
        print(f"{kind} lock: {lock.name} compiled for python {runtimes.version_text(minor)} "
              f"(abi {runtimes.abi_tag(minor)})")
        if found:
            print(f"  interpreter: {found}")
        else:
            message = f"No python {runtimes.version_text(minor)} interpreter found for the {kind} environment."
            failures.append(f"{message} {runtimes.remedy(minor)}")
            print(f"  interpreter: NONE -> {runtimes.remedy(minor)}")

    for kind, environment in DEV_ENVIRONMENTS.items():
        _, status = runtimes.environment_status(environment)
        print(f"development {kind} environment: {environment} is {status}")
        if status.startswith("broken") or status == "incomplete":
            lock = ROOT / "packaging" / f"{kind}-{name}.lock"
            line = runtimes.version_text(runtimes.lock_minor(lock)) if lock.is_file() else "the reviewed lock's"
            failures.append(f"Development {kind} environment is {status}. Recreate it from python {line}: "
                            f"python -m venv {environment}")

    if profile:
        root = profile_root(profile)
        print(f"profile {profile}: {root}")
        for kind in runtimes.KINDS:
            _, status = runtimes.environment_status(root / "runtimes" / kind)
            print(f"  {kind} runtime: {status}")

    if PAYLOAD.is_dir():
        for kind in runtimes.KINDS:
            wheelhouse = PAYLOAD / "wheels" / kind
            count = len(list(wheelhouse.glob("*.whl"))) if wheelhouse.is_dir() else 0
            print(f"payload wheelhouse {kind}: {count} wheels")
    else:
        print("payload: not prepared")

    if failures:
        print("\nNeeds attention:")
        for failure in failures:
            print(f"  - {failure}")
        sys.exit(1)
    print("\nNo runtime blockers found.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Report runtime blockers before a build or launch fails.")
    parser.add_argument("--profile", choices=("production", "development"),
                        help="Also inspect an installed profile's runtimes.")
    args = parser.parse_args()
    failures: list[str] = []
    report(failures, args.profile)

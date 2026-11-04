"""Move this PC's stopped desk into its installed production profile.

This is an offline installation operation. It never deletes the source stores,
merges destinations, changes saved research, or contacts a broker.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import socket
import sys
import tempfile


def copy_tree(source, destination, *, internal_links=False):
    source = source.resolve()
    count, size, tree = 0, 0, hashlib.sha256()
    destination.mkdir(parents=True)
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        if item.is_symlink() and (
            not internal_links or not item.resolve().is_relative_to(source)
        ):
            raise ValueError(f"Refusing a linked source outside the copy contract: {relative}")
        target = destination / relative
        if item.is_dir():
            target.mkdir(exist_ok=True)
            continue
        if not item.is_file():
            raise ValueError(f"Unsupported source entry: {relative}")
        shutil.copy2(item, target)
        with item.open("rb") as stream:
            before = hashlib.file_digest(stream, "sha256").hexdigest()
        with target.open("rb") as stream:
            after = hashlib.file_digest(stream, "sha256").hexdigest()
        if before != after:
            raise ValueError(f"Copy verification failed: {relative}")
        length = target.stat().st_size
        tree.update(f"{relative.as_posix()}\0{length}\0{after}\n".encode())
        count += 1
        size += length
    return {"files": count, "bytes": size, "sha256": tree.hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    if sys.platform == "win32" and "pythonsoftwarefoundation.python" in sys.base_prefix.casefold():
        parser.error("Use the installed app's bundled Python; Windows Store Python redirects AppData writes")
    parser.add_argument("--source-launch-config", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--laya-cache", type=Path)
    args = parser.parse_args()
    config_file = args.source_launch_config.resolve(strict=True)
    config = json.loads(config_file.read_text(encoding="utf-8"))
    paths = {
        name: (config_file.parent / config[name]).resolve(strict=True)
        for name in ("application", "history", "credentials_file")
    }
    destination = args.destination.resolve()
    if destination.exists():
        raise ValueError("The destination already exists; no files were merged or replaced")
    if any(destination.is_relative_to(path) for path in paths.values()):
        raise ValueError("The destination must be outside the original installation")
    sibling = paths["application"].with_name(paths["application"].name + ".recovery")
    if sibling.exists():
        raise ValueError("Resolve the existing sibling recovery generation before moving this desk")
    for port in (int(config["port"]), 8099):
        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise ValueError(f"Cannot reserve port {port}; stop the desk before copying its stores") from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=destination.name + ".move-", dir=destination.parent)).resolve()
    try:
        receipt = {
            "source_application": str(paths["application"]),
            "source_history": str(paths["history"]),
            "credentials_copied_separately": True,
            "application": copy_tree(paths["application"], stage / "application"),
            "research": copy_tree(paths["history"], stage / "research"),
        }
        private = stage / "private"
        private.mkdir(mode=0o700)
        credentials = private / "providers.env"
        shutil.copy2(paths["credentials_file"], credentials)
        credentials.chmod(0o600)
        for name in ("logs", "cache", "tmp", "updates"):
            (stage / name).mkdir()
        if args.laya_cache:
            receipt["laya_cache"] = copy_tree(
                args.laya_cache.resolve(strict=True), stage / "cache/laya", internal_links=True
            )
        (stage / "installation-copy.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )
        stage.rename(destination)
    except BaseException:
        # Only remove the staging directory created by this invocation.
        if stage.parent == destination.parent and stage.name.startswith(destination.name + ".move-"):
            shutil.rmtree(stage)
        raise
    print(json.dumps({"installed_profile": str(destination), **receipt}, indent=2))


if __name__ == "__main__":
    main()

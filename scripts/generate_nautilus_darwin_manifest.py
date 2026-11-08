"""Write docs/nautilus-v1-runtime-manifest-darwin.json from an installed macOS nautilus_trader wheel.

Usage: .venv-nautilus-v1/bin/python scripts/generate_nautilus_darwin_manifest.py WHEEL_FILE
The wheel file must be the official PyPI wheel. The script hashes the installed files and
refuses to write if any hash differs from the wheel RECORD.
"""
import base64, hashlib, json, sys, zipfile
from datetime import UTC, datetime
from pathlib import Path

import nautilus_trader

ROOT = Path(__file__).resolve().parents[1]
wheel = Path(sys.argv[1])
package = Path(nautilus_trader.__file__).parent
record = {}
with zipfile.ZipFile(wheel) as z:
    name = next(n for n in z.namelist() if n.endswith(".dist-info/RECORD"))
    for line in z.read(name).decode().splitlines():
        path, digest, _ = line.rsplit(",", 2)
        if path.startswith("nautilus_trader/") and digest:
            record[path.removeprefix("nautilus_trader/")] = digest
files = {}
for relative, digest in sorted(record.items()):
    data = (package / relative).read_bytes()
    expected = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    if expected != digest:
        raise SystemExit("Installed file differs from wheel RECORD: " + relative)
    files[relative] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
windows = json.loads((ROOT / "docs/nautilus-v1-runtime-manifest.json").read_text(encoding="utf-8"))
if nautilus_trader.__version__ != windows["nautilus_version"]:
    raise SystemExit("Version differs from the Windows manifest")
manifest = {k: windows[k] for k in ("nautilus_version", "source_commit", "source_tag", "cache_contract", "source_urls")}
manifest.update({
    "observed_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "platform": "darwin",
    "executable": ".venv-nautilus-v1/bin/python",
    "official_wheel": {"filename": wheel.name, "size": wheel.stat().st_size, "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()},
    "provenance": "Installed package files compared with the official PyPI macOS wheel RECORD digests.",
    "installed_files": files,
})
out = ROOT / "docs/nautilus-v1-runtime-manifest-darwin.json"
out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(out, len(files))

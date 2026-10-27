"""Refresh only the application wheel in an already prepared payload."""
import json
import subprocess
from pathlib import Path
from prepare import BUILD, CACHE, PAYLOAD, ROOT, VERSIONS, digest, interpreter, package_dir, run

uv = "uv"
wheel_dir = BUILD / "wheels"
manifest_name = Path("assets/runtime-manifests/nautilus-v1-runtime-manifest.json")
manifest_bytes = {kind: (package_dir(interpreter(PAYLOAD / kind)) / manifest_name).read_bytes() for kind in VERSIONS}
run(uv, "build", "--wheel", "--out-dir", wheel_dir, "--cache-dir", CACHE,
    "--build-constraints", ROOT / "packaging" / "build-constraints.txt")
wheels = list(wheel_dir.glob("tradingagents-*.whl"))
if len(wheels) != 1:
    raise RuntimeError("Expected exactly one project wheel")
for kind in VERSIONS:
    python = interpreter(PAYLOAD / kind)
    run(uv, "pip", "install", "--python", python, "--system", "--break-system-packages",
        "--no-deps", "--reinstall", "--link-mode", "copy", "--cache-dir", CACHE, wheels[0])
    target = package_dir(python) / manifest_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(manifest_bytes[kind])
provenance_path = PAYLOAD / "provenance.json"
provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
provenance["project_wheel_sha256"] = digest(wheels[0])
provenance["source_revision"] = subprocess.check_output(["rtk", "proxy", "git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
provenance["working_changes_present"] = bool(subprocess.check_output(["rtk", "proxy", "git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True).strip())
provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
print("Refreshed project wheel SHA-256:", provenance["project_wheel_sha256"])

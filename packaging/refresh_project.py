"""Refresh application code without opening or changing either Python runtime."""
import json
import subprocess
from pathlib import Path
from prepare import BUILD, CACHE, PAYLOAD, ROOT, digest, run, stage_app

uv = "uv"
wheel_dir = BUILD / "wheels"
manifest_name = Path("tradingagents/assets/runtime-manifests/nautilus-v1-runtime-manifest.json")
manifest_bytes = (PAYLOAD / "app" / manifest_name).read_bytes()
provenance_path = PAYLOAD / "provenance.json"
provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
run(uv, "build", "--wheel", "--out-dir", wheel_dir, "--cache-dir", CACHE,
    "--build-constraints", ROOT / "packaging" / "build-constraints.txt")
wheels = list(wheel_dir.glob("tradingagents-*.whl"))
if len(wheels) != 1:
    raise RuntimeError("Expected exactly one project wheel")
stage_app(wheels[0], manifest_bytes)
provenance["project_wheel_sha256"] = digest(wheels[0])
provenance["source_revision"] = subprocess.check_output(["rtk", "proxy", "git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
provenance["working_changes_present"] = bool(subprocess.check_output(["rtk", "proxy", "git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True).strip())
provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
print("Refreshed project wheel SHA-256:", provenance["project_wheel_sha256"])

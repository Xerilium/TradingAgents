"""Create an updater manifest for a signed local installer; does not publish it."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

parser = argparse.ArgumentParser()
parser.add_argument("installer", type=Path)
parser.add_argument("--version", required=True)
parser.add_argument("--tag", required=True)
parser.add_argument("--platform", choices=("windows-x86_64", "darwin-aarch64"), required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
signature = Path(str(args.installer) + ".sig").read_text(encoding="utf-8").strip()
if not signature or not args.installer.is_file():
    raise SystemExit("A signed installer and its .sig file are required")
with args.installer.open("rb") as stream:
    sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
url = ("https://github.com/Xerilium/TradingAgents/releases/download/"
       + quote(args.tag, safe="") + "/" + quote(args.installer.name, safe=""))
manifest = {"version": args.version, "platforms": {args.platform: {"signature": signature, "url": url}}}
args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
(args.output.parent / (args.installer.name + ".sha256")).write_text(f"{sha256}  {args.installer.name}\n", encoding="utf-8")
print(f"Prepared {args.output} for {args.installer.name}; SHA-256 {sha256}")

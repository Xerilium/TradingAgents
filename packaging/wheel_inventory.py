"""List official wheel filenames for release planning."""
import json
import urllib.request

for name, version in (("torch", "2.14.1"), ("nautilus-trader", "1.231.0")):
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json") as response:
        files = json.load(response)["urls"]
    print(name, version)
    for item in files:
        if "macosx" in item["filename"] or ("win_amd64" in item["filename"] and "cp312" in item["filename"]):
            print(item["filename"], item["size"])

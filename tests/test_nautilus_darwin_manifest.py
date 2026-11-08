import hashlib
import json
import sys
from pathlib import Path

import pytest

from tradingagents.web.nautilus_runtime import default_nautilus_python

ROOT = Path(__file__).resolve().parents[1]


def test_default_python_is_platform_aware():
    expected = Path(".venv-nautilus-v1") / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    assert default_nautilus_python("/r") == Path("/r") / expected


def test_manifests_are_platform_separate():
    windows = json.loads((ROOT / "docs/nautilus-v1-runtime-manifest.json").read_text(encoding="utf-8"))
    darwin = json.loads((ROOT / "docs/nautilus-v1-runtime-manifest-darwin.json").read_text(encoding="utf-8"))
    assert windows["nautilus_version"] == darwin["nautilus_version"]
    assert any(k.endswith(".pyd") for k in windows["installed_files"])
    assert not any(k.endswith(".pyd") for k in darwin["installed_files"])
    assert any(k.endswith(".so") for k in darwin["installed_files"])


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS wheel only")
def test_installed_wheel_matches_darwin_manifest():
    nautilus = pytest.importorskip("nautilus_trader")
    manifest = json.loads((ROOT / "docs/nautilus-v1-runtime-manifest-darwin.json").read_text(encoding="utf-8"))
    assert nautilus.__version__ == manifest["nautilus_version"]
    for relative, expected in manifest["installed_files"].items():
        assert hashlib.sha256((Path(nautilus.__file__).parent / relative).read_bytes()).hexdigest() == expected["sha256"], relative

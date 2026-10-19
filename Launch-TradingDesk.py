"""Project-local browser launcher; existing environments and migrated stores only."""
import ctypes
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent


def main():
    config_path = ROOT / "tradingdesk.launch.json"
    if not config_path.is_file():
        raise ValueError("Missing tradingdesk.launch.json. Set the existing migrated application, history, native Python and credentials-file paths. No installation or migration was attempted.")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    keys = {"application", "history", "native_python", "credentials_file", "port"}
    if set(config) != keys or type(config["port"]) is not int or not 1 <= config["port"] <= 65535:
        raise ValueError("tradingdesk.launch.json must contain the five documented fields and a valid local port")
    paths = {name: Path(config[name]).resolve() for name in keys - {"port"}}
    for name, path in paths.items():
        if not path.exists():
            raise ValueError("Configured " + name + " is missing. Correct tradingdesk.launch.json; no fallback store or installation is used.")
    application = paths["application"]
    # The existing server validates any active recovery generation and SQLite contents.
    sibling = application.with_name(application.name + ".recovery")
    if not (application / "desk.sqlite3").is_file() and not (application / "active-store.json").is_file() and not (sibling / "recovered-for.json").is_file():
        raise ValueError("The configured application has no migrated SQLite store. This launcher never migrates JSON or selects another journal.")
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        raise ValueError("The existing project Python environment is missing. Restore its approved environment; this launcher installs nothing.")
    identity = hashlib.sha256(str(application).casefold().encode()).hexdigest()
    url = "http://127.0.0.1:" + str(config["port"])
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def matching():
        with opener.open(url + "/", timeout=3) as response:
            response.read(1)
        with opener.open(url + "/api/health", timeout=3) as response:
            value = json.loads(response.read(1024 * 1024))
        return (value.get("product") == "TradingAgents" and value.get("application_identity") == identity
            and value.get("native_cache_mode") == "memory")
    try:
        with socket.create_connection(("127.0.0.1", config["port"]), timeout=2):
            occupied = True
    except OSError:
        occupied = False
    if occupied:
        if not matching():
            raise ValueError("Port is occupied by an unverified instance. Leave it running and correct the configured port or inspect its identity.")
    else:
        logs = ROOT / ".runtime-stage"
        logs.mkdir(exist_ok=True)
        arguments = [str(python), "-m", "tradingagents.web.server", "--port", str(config["port"]),
            "--data-dir", str(application), "--history-dir", str(paths["history"]),
            "--nautilus-python", str(paths["native_python"]), "--alpaca-credentials-file", str(paths["credentials_file"])]
        with (logs / "launcher.out.log").open("ab") as output, (logs / "launcher.err.log").open("ab") as errors:
            process = subprocess.Popen(arguments, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        for _ in range(30):
            if process.poll() is not None:
                raise ValueError("TradingAgents did not start. Inspect .runtime-stage/launcher.err.log; original stores were retained.")
            try:
                if matching():
                    break
            except (OSError, ValueError):
                pass
            time.sleep(1)
        else:
            raise ValueError("Startup identity is not available yet. Inspect the launcher log; no process was stopped or restarted.")
    webbrowser.open(url)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else "Launch failed (" + type(exc).__name__ + "). Inspect the configured paths and .runtime-stage launcher logs."
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(None, message, "TradingAgents launch", 0x10)
        else:
            print(message)

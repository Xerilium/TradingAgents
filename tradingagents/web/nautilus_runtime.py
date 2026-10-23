"""Own one native node subprocess and its durable-authority command channel."""

import copy
import json
import os
import queue
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class NautilusRuntime:
    def __init__(self, directory, python, credentials_file, *, application_root=None):
        self.directory, self.python = Path(directory), Path(python)
        self.credentials_file = Path(credentials_file).resolve()
        self.application_root = Path(application_root).resolve() if application_root else Path(directory).parent.resolve()
        self.lock = threading.RLock()
        self.process = None
        self.snapshot = {"status": "stopped", "read_only": True}
        self.received = 0
        self.pending = {}
        self.symbols = []
        self.option_feed = None
        self.execution_profile = "long_only"
        self.authority_database = None
        self.observers = []
        self.observer_queue = queue.Queue(maxsize=1)
        self.observer_thread = None

    def configure(self, symbols, *, option_feed=None, execution_profile=None):
        from .linked_orders import EXECUTION_PROFILES

        if execution_profile is not None and execution_profile not in EXECUTION_PROFILES:
            raise ValueError("Choose an identified execution profile")
        if option_feed is not None and option_feed not in {"opra", "indicative"}:
            raise ValueError("Choose an explicit OPRA or indicative option feed")
        with self.lock:
            running = self.process and self.process.poll() is None
            if running and execution_profile is not None and execution_profile != self.execution_profile:
                raise ValueError("Stop the native session before selecting a different execution profile")
            self.symbols = list(symbols)
            if execution_profile is not None:
                self.execution_profile = execution_profile
            if option_feed is not None:
                self.option_feed = option_feed
            running = self.process and self.process.poll() is None
        if running:
            self.request("configure", symbols=self.symbols, option_feed=self.option_feed)

    def start(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                return self.state()
            if not self.python.is_file() or not self.credentials_file.is_file():
                raise ValueError("Configured Nautilus Python or Alpaca credentials file is missing")
            self.directory.mkdir(parents=True, exist_ok=True)
            if self.observer_thread is None or not self.observer_thread.is_alive():
                self.observer_thread = threading.Thread(target=self._observe, daemon=True, name="account-record-observer")
                self.observer_thread.start()
            with (self.directory / "nautilus.log").open("ab") as log:
                self.process = subprocess.Popen(
                    [str(self.python), "-u", str(Path(__file__).with_name("nautilus_worker.py")), str(self.credentials_file)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                    text=True, encoding="utf-8", cwd=self.directory,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            self.snapshot, self.received = {"status": "starting", "read_only": False, "persistence": {"configured": False, "state": "in_memory", "backing": "memory", "restore_ready": False, "durable_writes_confirmed": False}}, time.monotonic()
            self.process.stdin.write(json.dumps({"symbols": self.symbols, "authority_database": str(self.authority_database) if self.authority_database else None,
                "application_root": str(self.application_root), "option_feed": self.option_feed, "execution_profile": self.execution_profile}) + "\n")
            self.process.stdin.flush()
            self.reader_thread = threading.Thread(target=self._read, args=(self.process,), daemon=True)
            self.reader_thread.start()
            return self.state()

    def _read(self, process):
        for line in process.stdout:
            try:
                value = json.loads(line)
                if not isinstance(value, dict) or type(value.get("read_only")) is not bool:
                    raise ValueError("Invalid runtime snapshot")
                if value.get("type") == "reply":
                    with self.lock:
                        target = self.pending.get(value.get("request_id"))
                        if target is not None:
                            target.put_nowait(value)
                    continue
            except (ValueError, TypeError):
                value = {"status": "error", "error": "Invalid Nautilus protocol output", "read_only": True}
            with self.lock:
                if process is self.process and (self.snapshot["status"] != "stopped" or value.get("status") == "error"):
                    self.snapshot, self.received = value, time.monotonic()
                else:
                    continue
            try:
                self.observer_queue.put_nowait(value)
            except queue.Full:
                try:
                    self.observer_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self.observer_queue.put_nowait(value)
                except queue.Full:
                    pass

    def _observe(self):
        while True:
            value = self.observer_queue.get()
            for observer in self.observers:
                try:
                    observer(copy.deepcopy(value))
                except Exception:
                    with self.lock:
                        self.snapshot["local_record_error"] = "Account-dependent local records could not be updated; command admission remains blocked"

    def request(self, command, **fields):
        request_id, target = str(uuid4()), queue.Queue(maxsize=1)
        with self.lock:
            status = self.state()["status"]
            if status not in {"connected", "starting"}:
                raise ValueError("A connected Nautilus node is required")
            if command == "native_report" and status != "connected":
                raise ValueError("A current connected native node is required for reports")
            self.pending[request_id] = target
            try:
                self.process.stdin.write(json.dumps({"command": command, "request_id": request_id, **fields}) + "\n")
                self.process.stdin.flush()
            except OSError:
                self.pending.pop(request_id, None)
                raise ValueError("Nautilus command pipe is unavailable") from None
        try:
            reply = target.get(timeout=45)
            if reply.get("error"):
                raise ValueError(reply["error"])
            if command == "native_report":
                current = self.state()
                if (reply.get("read_only") is not True or current["status"] != "connected"
                        or reply.get("native_report", {}).get("native_epoch") != current.get("native_epoch")):
                    raise ValueError("Native report capture no longer belongs to the current connected node")
            return reply
        except queue.Empty:
            raise ValueError("Nautilus did not acknowledge the command within 45 seconds") from None
        finally:
            with self.lock:
                self.pending.pop(request_id, None)

    def prepare_package(self, terms):
        if self.state()["status"] != "connected":
            raise ValueError("A current connected native node is required to derive actual package valuation")
        return self.request("package_valuation", terms=terms)["package_valuation"]

    def state(self):
        with self.lock:
            state = copy.deepcopy(self.snapshot)
            state["execution_profile"] = self.execution_profile
            if state.get("profile_transition", {}).get("selected_profile") != self.execution_profile:
                state["profile_transition"] = {"selected_profile": self.execution_profile, "native_account_type": None,
                    "eligibility": {"eligible": False, "blockers": ["A new authenticated native session has not validated this profile"]}}
            state["pid"] = self.process.pid if self.process else None
            if self.process and self.process.poll() is not None and state["status"] != "stopped":
                state.update(status="disconnected", error=state.get("error") or "Nautilus process exited")
                state["persistence"] = {"configured": False, "state": "in_memory", "backing": "memory", "restore_ready": False, "durable_writes_confirmed": False}
            elif state["status"] == "connected":
                age = (datetime.now(UTC) - datetime.fromisoformat(state["account_at"])).total_seconds()
                if time.monotonic() - self.received > 5 or age > 90:
                    state.update(status="stale", error="Nautilus heartbeat or account snapshot is stale")
            state["desired_symbols"] = list(self.symbols)
            state["desired_option_feed"] = self.option_feed
            if state["status"] != "connected":
                state["native_risk"] = {**state.get("native_risk", {}), "status": "unavailable", "values": None,
                                        "reason": "Native node is " + state["status"]}
            state.setdefault("persistence", {"configured": False, "state": "in_memory", "backing": "memory", "restore_ready": False, "durable_writes_confirmed": False})
            return state

    def stop(self):
        with self.lock:
            process = self.process
        forced = False
        if process and process.poll() is None:
            try:
                process.stdin.write('{"command":"stop"}\n')
                process.stdin.flush()
                process.wait(timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                forced = True
                process.terminate()
                process.wait(timeout=5)
        if getattr(self, "reader_thread", None):
            self.reader_thread.join(timeout=3)
        with self.lock:
            persistence = copy.deepcopy(self.snapshot.get("persistence", {}))
            persistence.update(configured=False, state="in_memory", backing="memory", restore_ready=False, durable_writes_confirmed=False, quiescent=bool(process and process.poll() == 0 and not forced))
            self.snapshot = {"status": "stopped", "read_only": True, "persistence": persistence}
            return self.state()

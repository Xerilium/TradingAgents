"""Profile-scoped credentials in the operating system's native vault."""

import json
import os
import runpy
import sys
from pathlib import Path

_PROVIDERS = runpy.run_path(str(Path(__file__).parent / "llm_clients" / "api_key_env.py"))["PROVIDER_API_KEY_ENV"]
KEYS = tuple(dict.fromkeys([key for key in _PROVIDERS.values() if key] + ["FRED_API_KEY", "ALPHA_VANTAGE_API_KEY", "TYPESAFE_API_KEY"]))
ALPACA_FIELDS = {"APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "APCA_API_BASE_URL"}
PAPER = "https://paper-api.alpaca.markets"


class CredentialStore:
    def __init__(self, profile=None):
        profile = profile or os.getenv("TRADINGAGENTS_DESKTOP_PROFILE") or "development"
        if profile not in {"production", "development"}:
            raise ValueError("Choose a production or development credential profile")
        self.profile = profile
        self.service = "TradingAgents.desktop." + self.profile
        self.backend_name = {"win32": "Windows Credential Manager", "darwin": "macOS Keychain"}.get(sys.platform, "unsupported")
        self.backend = None
        try:
            if sys.platform == "win32":
                from keyring.backends.Windows import WinVaultKeyring
                self.backend = WinVaultKeyring()
                self.backend.persist = "local machine"
            elif sys.platform == "darwin":
                from keyring.backends.macOS import Keyring
                self.backend = Keyring()
        except Exception:
            self.backend = None

    def _get(self, group):
        if self.backend is None:
            raise ValueError("Native credential storage is unavailable")
        try:
            return self.backend.get_password(self.service + "." + group, "credential")
        except Exception:
            raise ValueError("Native credential storage is unavailable") from None

    def _set(self, group, value):
        if self.backend is None:
            raise ValueError("Native credential storage is unavailable")
        try:
            self.backend.set_password(self.service + "." + group, "credential", value)
        except Exception:
            raise ValueError("Native credential storage could not save credentials") from None

    def _alpaca(self):
        raw = self._get("alpaca")
        if raw is None:
            return {}
        try:
            values = json.loads(raw)
            if not isinstance(values, dict) or set(values) - ALPACA_FIELDS or any(not isinstance(v, str) for v in values.values()):
                raise ValueError()
            return values
        except (ValueError, TypeError):
            raise ValueError("Stored Alpaca credentials are invalid") from None

    def status(self):
        result = {"available": False, "backend": self.backend_name, "profile": self.profile,
                  "message": "Native credential storage is unavailable",
                  "alpaca": {"key_id_configured": False, "secret_configured": False, "endpoint": None, "mode": None},
                  "keys": [{"id": key, "label": key.replace("_API_KEY", "").replace("_", " "), "configured": False} for key in KEYS]}
        try:
            values = self._alpaca()
            from .web.alpaca_readonly import normalize_trading_endpoint, TRADING_ORIGINS
            endpoint = normalize_trading_endpoint(values.get("APCA_API_BASE_URL") or PAPER) if values else None
            result["alpaca"] = {"key_id_configured": bool(values.get("APCA_API_KEY_ID")), "secret_configured": bool(values.get("APCA_API_SECRET_KEY")), "endpoint": endpoint, "mode": TRADING_ORIGINS.get(endpoint)}
            for item in result["keys"]:
                item["configured"] = bool(self._get(item["id"]))
            result.update(available=True, message=None)
        except (ValueError, KeyError):
            pass
        return result

    def connection_config(self, config_class=None):
        if config_class is None:
            from .web.alpaca_readonly import ConnectionConfig
            config_class = ConnectionConfig
        values = self._alpaca()
        if not values.get("APCA_API_KEY_ID") or not values.get("APCA_API_SECRET_KEY"):
            raise ValueError("Add Alpaca credentials in Settings > Account before starting Nautilus")
        return config_class(values.get("APCA_API_BASE_URL") or PAPER, values.get("APCA_API_KEY_ID"), values.get("APCA_API_SECRET_KEY"))

    def load_environment(self):
        try:
            values = {key: self._get(key) for key in KEYS}
        except ValueError:
            values = {}
        for key in KEYS:
            value = values.get(key)
            if value:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)

    def save(self, group, values):
        if not isinstance(values, dict):
            raise ValueError("Credential values must be an object")
        if group == "alpaca":
            if set(values) - ALPACA_FIELDS or any(not isinstance(v, str) for v in values.values()):
                raise ValueError("Unsupported Alpaca credential fields")
            from .web.alpaca_readonly import normalize_trading_endpoint
            merged = self._alpaca()
            merged.update({key: value.strip() for key, value in values.items() if value.strip()})
            if not merged.get("APCA_API_KEY_ID") or not merged.get("APCA_API_SECRET_KEY"):
                raise ValueError("Both Alpaca key ID and secret are required")
            merged["APCA_API_BASE_URL"] = normalize_trading_endpoint(merged.get("APCA_API_BASE_URL") or PAPER)
            self._set(group, json.dumps(merged))
        elif group in KEYS:
            if set(values) != {"value"} or not isinstance(values["value"], str) or not values["value"].strip():
                raise ValueError("Enter a credential value")
            value = values["value"].strip()
            self._set(group, value)
            os.environ[group] = value
        else:
            raise ValueError("Unknown credential group")
        return self.status()

    def remove(self, group):
        if group != "alpaca" and group not in KEYS:
            raise ValueError("Unknown credential group")
        if self._get(group) is not None:
            try:
                self.backend.delete_password(self.service + "." + group, "credential")
            except Exception:
                raise ValueError("Native credential storage could not remove credentials") from None
        if group in KEYS:
            os.environ.pop(group, None)
        return self.status()

"""Validate no-access resource probes emitted by the Codex app-server."""

from __future__ import annotations

import json


def require_disabled_mcp(server, thread_id: str) -> None:
    """Require explicit runtime isolation, including every inventory page."""
    cursor = None
    cursors = set()
    while True:
        inventory = server.rpc("mcpServerStatus/list", {
            "threadId": thread_id, "detail": "full", "cursor": cursor,
        })
        entries = inventory.get("data")
        if not isinstance(entries, list) or any(
            not isinstance(item, dict)
            or item.get("runtimeStatus") != "disabled"
            or item.get("tools") != {}
            or item.get("resources") != []
            or item.get("resourceTemplates") != []
            for item in entries
        ):
            raise RuntimeError("Codex MCP runtime is not fully disabled; account adapter stopped before research.")
        cursor = inventory.get("nextCursor")
        if cursor is None:
            return
        if not isinstance(cursor, str) or not cursor or cursor in cursors:
            raise RuntimeError("Codex returned invalid MCP inventory pagination.")
        cursors.add(cursor)


class ResourceProbeGuard:
    """Allow empty discovery and unavailable reads, never native resource data."""

    _PREFIX = {
        "list_mcp_resources": "resources/list failed: ",
        "list_mcp_resource_templates": "resources/templates/list failed: ",
        "read_mcp_resource": "resources/read failed: ",
    }

    def __init__(self):
        self.pending = {}
        self.seen = set()

    @staticmethod
    def _identity(item):
        if not all(isinstance(item.get(key), str) and item[key] for key in ("id", "server", "tool")):
            raise RuntimeError("Codex returned an invalid MCP resource probe identity.")
        if "arguments" not in item:
            raise RuntimeError("Codex omitted MCP resource probe arguments.")
        return item["server"], item["tool"], json.dumps(item["arguments"], sort_keys=True, allow_nan=False)

    def started(self, item):
        identity = self._identity(item)
        if identity[1] not in self._PREFIX:
            raise RuntimeError(f"Codex exposed an unexpected native MCP tool ({identity[0]}/{identity[1]}); account adapter stopped.")
        if item["id"] in self.seen or item.get("status") != "inProgress" or item.get("result") is not None or item.get("error") is not None:
            raise RuntimeError("Codex returned an invalid MCP resource probe start.")
        self.seen.add(item["id"])
        self.pending[item["id"]] = identity

    def completed(self, item):
        identity = self._identity(item)
        if self.pending.get(item["id"]) != identity:
            raise RuntimeError("Codex returned an unmatched or changed MCP resource probe.")
        server, tool, _ = identity
        error = item.get("error")
        no_access_errors = {
            self._PREFIX[tool] + f"unknown MCP server '{server}'",
            f"MCP tool `{server}/{tool}` is not available to the model",
        }
        unavailable = (
            item.get("status") == "failed" and item.get("result") is None
            and isinstance(error, dict) and set(error) == {"message"}
            and error["message"] in no_access_errors
        )
        if not unavailable and not self._empty_listing(item):
            raise RuntimeError("Codex native resource probe returned data or an unrecognized outcome; account adapter stopped.")
        del self.pending[item["id"]]

    @staticmethod
    def _empty_listing(item):
        key = {"list_mcp_resources": "resources", "list_mcp_resource_templates": "resourceTemplates"}.get(item["tool"])
        result = item.get("result")
        if key is None or item.get("status") != "completed" or item.get("error") is not None or not isinstance(result, dict):
            return False
        if set(result) - {"content", "structuredContent", "_meta"} or result.get("structuredContent") is not None or result.get("_meta") is not None:
            return False
        content = result.get("content")
        if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict):
            return False
        block = content[0]
        if set(block) != {"type", "text"} or block["type"] != "text" or not isinstance(block["text"], str):
            return False
        arguments = item["arguments"]
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict) or set(arguments) - {"server", "cursor"} or arguments.get("cursor") not in (None, ""):
            return False
        target = arguments.get("server")
        if target is not None and not isinstance(target, str):
            return False
        target = (target or "").strip()
        if item["server"] != (target or "codex"):
            return False
        expected = {key: []}
        if target:
            expected["server"] = target
        try:
            return json.loads(block["text"]) == expected
        except ValueError:
            return False

    def require_finished(self, boundary="before returning a response"):
        if self.pending:
            raise RuntimeError(f"Codex left an MCP resource probe unfinished {boundary}; account adapter stopped.")

"""Exercise HTTP dispatch without opening a network listener."""

from __future__ import annotations

import io
import json
from email.message import Message
from threading import RLock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tradingagents.web.server import DeskHandler


def handler(path="/api/trading/pause", body=b'{"paused":true}', **headers):
    instance = object.__new__(DeskHandler)
    instance.path = path
    instance.headers = Message()
    defaults = {
        "Host": "127.0.0.1:8088",
        "Origin": "http://127.0.0.1:8088",
        "X-CSRF-Token": "session-token",
        "Cookie": "tradingagents_session_8088=browser-session",
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
    }
    defaults.update(headers)
    for name, value in defaults.items():
        if value is not None:
            instance.headers[name] = str(value)
    service = Mock(maintenance=RLock(), recovery_only=False, browse_only=False)
    service.state.return_value = {"paused": False}
    service.command_action.return_value = {"paused": True}
    instance.server = SimpleNamespace(server_port=8088, csrf_token="session-token", session_token="browser-session", service=service)
    instance.rfile = io.BytesIO(body)
    instance.wfile = io.BytesIO()
    instance.close_connection = False
    instance._send = Mock()
    return instance, service


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "attacker.example:8088"},
        {"Host": "127.0.0.1"},
        {"Host": None},
        {"Origin": "https://attacker.example"},
        {"Origin": "null"},
        {"X-CSRF-Token": None},
        {"X-CSRF-Token": "wrong"},
    ],
)
def test_rejects_foreign_host_origin_and_missing_or_wrong_csrf_before_dispatch(headers):
    request, service = handler(**headers)
    request.do_POST()
    assert request._send.call_args.args[0] == 403
    assert service.mock_calls == []
    assert request.rfile.tell() == 0
    assert request.close_connection is True


def test_valid_local_json_request_dispatches_once():
    request, service = handler()
    request.do_POST()
    service.command_action.assert_called_once_with({"paused": True, "action": "block", "blocked": True})
    assert request._send.call_args.args == (200, {"paused": True})


@pytest.mark.parametrize("date", [None, "2020-01-02"])
def test_run_request_forwards_optional_analysis_date(date):
    payload = {"symbols": ["META"], "config_revision": 3}
    if date is not None:
        payload["analysis_date"] = date
    request, service = handler(path="/api/runs", body=json.dumps(payload).encode())
    request.do_POST()
    service.start_run.assert_called_once_with(["META"], expected_revision=3, analysis_date=date)
    assert request._send.call_args.args[0] == 200


def test_disconnected_browser_response_closes_without_retrying_the_operation():
    request, service = handler()
    request.send_response = Mock()
    request.send_header = Mock()
    request.end_headers = Mock()
    request.wfile = Mock()
    request.wfile.write.side_effect = ConnectionAbortedError("Browser cancelled its request")
    DeskHandler._send(request, 200, {"paused": True})
    assert request.close_connection is True
    request.wfile.write.assert_called_once()
    assert service.mock_calls == []


def test_same_localhost_origin_alias_is_accepted():
    request, service = handler(Host="localhost:8088", Origin="http://localhost:8088")
    request.do_POST()
    service.command_action.assert_called_once_with({"paused": True, "action": "block", "blocked": True})


@pytest.mark.parametrize(
    "body,headers",
    [
        (b"[]", {}),
        (b"null", {}),
        (b"not json", {}),
        (b'{"paused":NaN}', {}),
        (b"{}", {"Content-Length": "0"}),
        (b"{}", {"Content-Length": "65537"}),
        (b"{}", {"Content-Length": "invalid"}),
        (b"{}", {"Transfer-Encoding": "chunked"}),
        (b"{}", {"Content-Type": "text/plain"}),
    ],
)
def test_rejects_invalid_body_type_size_encoding_and_nonfinite_json(body, headers):
    request, service = handler(body=body, **headers)
    request.do_POST()
    assert request._send.call_args.args[0] == 400
    assert service.mock_calls == []


def test_unknown_api_route_has_no_service_effect():
    request, service = handler(path="/api/arbitrary-action", body=b"{}")
    request.do_POST()
    assert request._send.call_args.args[0] == 404
    assert service.mock_calls == []


def test_truncated_request_body_is_rejected_before_dispatch():
    request, service = handler(body=b'{"paused":true}', **{"Content-Length": "100"})
    request.do_POST()
    assert request._send.call_args.args[0] == 400
    assert request.close_connection is True
    assert service.mock_calls == []


def test_order_route_is_forbidden_before_service_dispatch():
    request, service = handler(path="/api/orders", body=b"{}")
    request.do_POST()
    assert request._send.call_args.args[0] == 403
    assert service.mock_calls == []


def test_service_failure_is_generic_and_does_not_echo_private_details():
    request, service = handler()
    service.command_action.side_effect = RuntimeError("secret broker credential")
    request.do_POST()
    status, body = request._send.call_args.args
    assert status == 502
    assert "secret" not in json.dumps(body)


def test_state_includes_csrf_only_for_accepted_local_host():
    request, service = handler(path="/api/state")
    request.do_GET()
    assert request._send.call_args.args == (200, {"paused": False, "csrf_token": "session-token"})
    service.state.assert_called_once_with()


def test_foreign_host_cannot_read_account_state_or_csrf():
    request, service = handler(path="/api/state", Host="attacker.example:8088")
    request.do_GET()
    assert request._send.call_args.args[0] == 403
    assert service.mock_calls == []


@pytest.mark.parametrize(
    "path", ["/../desk.json", "/static/../../.env", "/%2e%2e/.env", "/arbitrary.txt"]
)
def test_static_allowlist_does_not_expose_filesystem_paths(path):
    request, service = handler(path=path)
    request.do_GET()
    assert request._send.call_args.args[0] == 404
    assert service.mock_calls == []


def test_response_headers_disable_cache_and_cross_origin_framing():
    request, _ = handler()
    request.send_response = Mock()
    request.send_header = Mock()
    request.end_headers = Mock()
    DeskHandler._send(request, 200, {"ok": True})
    headers = dict(call.args for call in request.send_header.call_args_list)
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "Access-Control-Allow-Origin" not in headers
    assert int(headers["Content-Length"]) == len(request.wfile.getvalue())

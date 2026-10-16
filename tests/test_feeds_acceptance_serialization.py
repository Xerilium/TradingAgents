import base64
import json

import pytest
from mcp.types import CallToolResult, TextContent

from tests.feeds_live_acceptance import receipt_default


def test_vendor_receipt_serializes_actual_mcp_result_without_losing_fields():
    result = CallToolResult(content=[TextContent(type="text", text='{"tokens": 131}')],
                            structuredContent={"sequence_tokens": {"about": 131}}, isError=False)
    receipt = {"payload": {"result": result}, "raw_feed": b"<feed>actual bytes</feed>"}
    recovered = json.loads(json.dumps(receipt, default=receipt_default))
    assert recovered["payload"]["result"]["content"][0]["text"] == '{"tokens": 131}'
    assert recovered["payload"]["result"]["structuredContent"] == {"sequence_tokens": {"about": 131}}
    assert recovered["payload"]["result"]["isError"] is False
    assert base64.b64decode(recovered["raw_feed"]["data"]) == receipt["raw_feed"]


def test_unknown_evidence_type_is_not_silently_stringified():
    with pytest.raises(TypeError, match="Unsupported receipt"):
        json.dumps({"result": object()}, default=receipt_default)

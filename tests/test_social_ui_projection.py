from tradingagents.web.store import DeskStore


def test_compact_social_projection_keeps_counts_without_post_text():
    social = {"status": "partial", "model": "multilingual", "sources": {"reddit": {
        "status": "partial", "counts": {"neutral": 0, "unscreened": 2},
        "note": "Unavailable", "posts": [{"text": "large raw post", "text_sha256": "abc"}],
    }}}
    result = {"symbol": "META", "reports": {}, "social_sentiment": social}
    compact = DeskStore.result_summary(result)
    assert compact["social_sentiment"]["sources"]["reddit"]["counts"]["unscreened"] == 2
    assert "posts" not in compact["social_sentiment"]["sources"]["reddit"]
    assert result["social_sentiment"]["sources"]["reddit"]["posts"][0]["text"] == "large raw post"
    compact["social_sentiment"]["sources"]["reddit"]["counts"]["neutral"] = 9
    assert social["sources"]["reddit"]["counts"]["neutral"] == 0

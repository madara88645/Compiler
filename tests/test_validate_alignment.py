"""Test that offline Quality Report weaknesses and suggestions stay index-aligned.

The QualityCoach component in the frontend maps ``suggestions[i]`` to
``weaknesses[i]``.  If the two lists have different lengths or misaligned
indexes, users see the wrong suggestion next to a weakness.

Fixes #1075.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_validate_weakness_suggestion_alignment():
    """weaknesses and suggestions lists in /validate must be equal length."""
    resp = client.post(
        "/validate",
        json={"text": "do stuff with things and whatever"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    weaknesses = body.get("weaknesses", [])
    suggestions = body.get("suggestions", [])

    assert len(weaknesses) == len(suggestions), (
        f"Length mismatch: {len(weaknesses)} weaknesses vs {len(suggestions)} suggestions"
    )


def test_validate_returns_report_shape():
    """Basic shape validation of the /validate response."""
    resp = client.post(
        "/validate",
        json={"text": "Write me a short haiku about winter"},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert "score" in body
    assert isinstance(body["score"], int)
    assert "category_scores" in body
    assert "weaknesses" in body
    assert "suggestions" in body
    assert "summary" in body


def test_validate_paired_content_quality():
    """Each weakness should pair with a suggestion (possibly empty), never mismatched."""
    resp = client.post(
        "/validate",
        json={
            "text": "help me with something",
            "include_suggestions": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()

    weaknesses = body.get("weaknesses", [])
    suggestions = body.get("suggestions", [])

    assert len(weaknesses) == len(suggestions)

    # All suggestions should be strings (empty string is acceptable for no suggestion)
    for s in suggestions:
        assert isinstance(s, str)

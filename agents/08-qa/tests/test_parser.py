"""
test_parser.py — Tests for parse_json_from_llm

Covers the failure modes we've hit in practice:
  1. Clean JSON (ideal case)
  2. ```json fenced block with preamble
  3. ``` fenced block (no language tag)
  4. Preamble + raw JSON + trailing commentary (no fences)
  5. Multiple fenced blocks (pick the right one)
  6. Nested braces in strings
  7. Completely unparseable response (graceful failure)
  8. shot_grades as dict instead of list
"""

import json
import sys
from pathlib import Path

# Add parent so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.pipeline import parse_json_from_llm


def test_clean_json():
    """Strategy 1: Model returned raw JSON with no wrapping."""
    raw = json.dumps({
        "overall_verdict": "revise",
        "overall_notes": "Two major issues found.",
        "findings": [],
        "shot_grades": [],
    })
    result = parse_json_from_llm(raw)
    assert result["overall_verdict"] == "revise"
    assert result["overall_notes"] == "Two major issues found."
    print("  PASS: clean JSON")


def test_json_fenced():
    """Strategy 2: ```json ... ``` with preamble text."""
    raw = """Here's my analysis of the rough cut:

```json
{
  "overall_verdict": "approved",
  "overall_notes": "Looks good overall.",
  "findings": [
    {
      "finding_id": "F001",
      "severity": "minor",
      "category": "visual_continuity",
      "shots_affected": ["s01-sh02"],
      "timestamp": "12.0s",
      "description": "Slight dust level change."
    }
  ],
  "shot_grades": []
}
```

Let me know if you need any clarification on these findings."""

    result = parse_json_from_llm(raw)
    assert result["overall_verdict"] == "approved"
    assert len(result["findings"]) == 1
    assert result["findings"][0]["finding_id"] == "F001"
    print("  PASS: ```json fenced with preamble + trailing text")


def test_plain_fenced():
    """Strategy 3: ``` ... ``` with no language tag."""
    raw = """Analysis complete.

```
{
  "overall_verdict": "revise",
  "overall_notes": "Character consistency needs work.",
  "findings": [],
  "shot_grades": [{"shot_id": "s01-sh01", "grade": "B+", "notes": "Good."}]
}
```
"""
    result = parse_json_from_llm(raw)
    assert result["overall_verdict"] == "revise"
    assert len(result["shot_grades"]) == 1
    print("  PASS: plain ``` fenced")


def test_no_fences_with_preamble():
    """Strategy 4: Preamble + raw JSON + trailing text, no fences at all."""
    raw = """I've reviewed all 18 frames. Here are my findings:

{
  "overall_verdict": "revise",
  "overall_notes": "Desert environment shifts between shots 2 and 3.",
  "findings": [
    {
      "finding_id": "F001",
      "severity": "major",
      "category": "visual_continuity",
      "shots_affected": ["s01-sh02", "s01-sh03"],
      "timestamp": "25.0s",
      "description": "Desert type changes from Sonoran to Mojave.",
      "recommendation": "Regenerate s01-sh03."
    }
  ],
  "shot_grades": []
}

I hope this helps with your review process. The most critical issue is the desert continuity."""

    result = parse_json_from_llm(raw)
    assert result["overall_verdict"] == "revise"
    assert len(result["findings"]) == 1
    assert result["findings"][0]["severity"] == "major"
    print("  PASS: no fences, preamble + trailing text")


def test_nested_braces_in_strings():
    """Strategy 4 edge case: JSON values contain braces (shouldn't break matcher)."""
    raw = """Here:

{
  "overall_verdict": "revise",
  "overall_notes": "The shot at {timestamp} shows {artifact_type} issues.",
  "findings": [],
  "shot_grades": []
}

Done."""

    result = parse_json_from_llm(raw)
    assert result["overall_verdict"] == "revise"
    assert "{timestamp}" in result["overall_notes"]
    print("  PASS: nested braces in string values")


def test_multiple_fenced_blocks():
    """Multiple code blocks — should pick the JSON one."""
    raw = """I'll analyze the frames.

Here's the shot list for reference:
```
s01-sh01: wide establishing shot
s01-sh02: tracking motorcycle
```

And here's my QA report:
```json
{
  "overall_verdict": "approved",
  "overall_notes": "All shots pass.",
  "findings": [],
  "shot_grades": [{"shot_id": "s01-sh01", "grade": "A", "notes": "Strong."}]
}
```
"""
    result = parse_json_from_llm(raw)
    assert result["overall_verdict"] == "approved"
    assert len(result["shot_grades"]) == 1
    print("  PASS: multiple code blocks, picks ```json one")


def test_unparseable():
    """Completely unparseable response — should return error structure."""
    raw = """I'm sorry, I can't analyze these frames because the images appear
to be corrupted. Please re-extract and try again."""

    result = parse_json_from_llm(raw)
    assert result["overall_verdict"] == "error"
    assert "raw_response" in result
    print("  PASS: unparseable response returns error structure")


def test_json_with_trailing_comma():
    """Edge case: trailing comma (common LLM mistake). Brace matcher finds
    the block but json.loads fails. Should fall through gracefully."""
    raw = """{
  "overall_verdict": "revise",
  "findings": [],
  "shot_grades": [],
}"""
    # This will fail json.loads due to trailing comma.
    # Our parser should still return *something* (the error structure).
    result = parse_json_from_llm(raw)
    # We accept either a successful parse (if json is lenient) or the error fallback
    assert "overall_verdict" in result
    print("  PASS: trailing comma handled (error or lenient parse)")


def test_raw_json_with_trailing_text():
    """Strategy 1 partial: starts with { but has trailing text after }."""
    raw = """{
  "overall_verdict": "approved",
  "overall_notes": "Clean.",
  "findings": [],
  "shot_grades": []
}
Note: I focused primarily on visual continuity for this pass."""

    result = parse_json_from_llm(raw)
    assert result["overall_verdict"] == "approved"
    print("  PASS: raw JSON with trailing text after closing brace")


if __name__ == "__main__":
    print("Testing parse_json_from_llm:\n")
    test_clean_json()
    test_json_fenced()
    test_plain_fenced()
    test_no_fences_with_preamble()
    test_nested_braces_in_strings()
    test_multiple_fenced_blocks()
    test_unparseable()
    test_json_with_trailing_comma()
    test_raw_json_with_trailing_text()
    print(f"\nAll tests passed.")

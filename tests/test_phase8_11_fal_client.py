"""Phase 8.11: the older fal client uses the same queue contract as the engine.

The session is fake. requests.post and requests.get are blocked.
"""

from __future__ import annotations

import json
import sys

import pytest

from movie_swarm.paths import repo_root


PROD = repo_root() / "agents" / "05-production"
if str(PROD) not in sys.path:
    sys.path.insert(0, str(PROD))

from src.fal_client import (  # noqa: E402
    fetch_result,
    poll_status,
    queue_payload,
    submit_generation,
    wait_for_completion,
)


SECRET = "fal-client-test-key-do-not-leak"
FAST = "bytedance/seedance-2.0/fast/text-to-video"
STATUS = "https://queue.fal.run/bytedance/seedance-2.0/requests/job-1/status"
RESULT = "https://queue.fal.run/bytedance/seedance-2.0/requests/job-1"


class Response:
    def __init__(self, payload, status=200):
        self.status_code = status
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({
            "method": "POST",
            "url": url,
            "headers": dict(headers or {}),
            "json": json,
        })
        return self.responses.pop(0)

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({
            "method": "GET",
            "url": url,
            "headers": dict(headers or {}),
            "params": params,
        })
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr("src.fal_client.requests.post", blocked)
    monkeypatch.setattr("src.fal_client.requests.get", blocked)
    monkeypatch.setenv("FAL_KEY", SECRET)


def test_submit_posts_top_level_fields_and_rounds_duration():
    session = Session([Response({
        "request_id": "job-1",
        "status_url": STATUS,
        "response_url": RESULT,
    })])
    original = {"prompt": "A dock at night.", "duration": 2.087, "resolution": "720p"}
    result = submit_generation(FAST, original, session=session)
    assert original["duration"] == 2.087
    posted = session.calls[0]
    assert posted["method"] == "POST"
    assert posted["url"] == f"https://queue.fal.run/{FAST}"
    assert "input" not in posted["json"]
    assert posted["json"]["duration"] == "4"
    assert posted["json"]["prompt"] == "A dock at night."
    assert posted["json"]["resolution"] == "720p"
    assert set(posted["headers"]) >= {"Authorization", "Content-Type"}
    assert result["request_id"] == "job-1"
    assert result["status_url"] == STATUS
    assert result["response_url"] == RESULT
    assert SECRET not in json.dumps(posted["json"])
    assert SECRET not in json.dumps(result)


def test_polling_uses_the_returned_url():
    session = Session([Response({"status": "IN_QUEUE", "queue_position": 3})])
    data = poll_status(FAST, "job-1", status_url=STATUS, session=session)
    assert data["status"] == "IN_QUEUE"
    assert session.calls[0]["url"] == STATUS
    assert "/fast/text-to-video/requests/" not in session.calls[0]["url"]
    assert "Authorization" in session.calls[0]["headers"]


def test_a_missing_status_url_uses_the_app_id():
    session = Session([Response({"status": "IN_PROGRESS"})])
    poll_status(FAST, "job-9", session=session)
    assert session.calls[0]["url"] == (
        "https://queue.fal.run/bytedance/seedance-2.0/requests/job-9/status"
    )


def test_an_error_body_fails_and_drops_the_echoed_input():
    session = Session([Response({
        "detail": [{
            "loc": ["body", "prompt"],
            "msg": "Field required",
            "input": {"prompt": SECRET, "duration": "2.087"},
        }]
    })])
    with pytest.raises(RuntimeError) as caught:
        fetch_result(FAST, "job-1", response_url=RESULT, session=session)
    text = str(caught.value)
    assert "prompt: Field required" in text
    assert "Nothing was produced" in text
    assert SECRET not in text
    assert session.calls[0]["url"] == RESULT


def test_wait_follows_the_returned_urls(monkeypatch):
    session = Session([
        Response({"status": "IN_QUEUE", "queue_position": 1, "response_url": RESULT}),
        Response({"status": "COMPLETED", "response_url": RESULT}),
        Response({"video": {"url": "https://cdn.example/clip.mp4"}}),
    ])
    clock = {"now": 0.0}

    def sleeper(seconds):
        clock["now"] += seconds

    result = wait_for_completion(
        FAST,
        "job-1",
        timeout=30,
        poll_interval=5,
        status_url=STATUS,
        response_url=RESULT,
        session=session,
        sleeper=sleeper,
        clock=lambda: clock["now"],
    )
    assert result["video"]["url"].endswith("clip.mp4")
    assert [call["url"] for call in session.calls] == [STATUS, STATUS, RESULT]
    assert clock["now"] == 5
    assert SECRET not in json.dumps(result)


def test_auto_duration_is_left_alone_and_a_long_shot_is_not_posted():
    body = queue_payload(FAST, {"prompt": "x", "duration": "auto"})
    assert body["duration"] == "auto"
    session = Session([])
    with pytest.raises(ValueError) as caught:
        submit_generation(FAST, {"prompt": "x", "duration": 20}, session=session)
    assert "Nothing was sent" in str(caught.value)
    assert session.calls == []

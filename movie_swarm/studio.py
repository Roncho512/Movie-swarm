"""Run the studio from a treatment through delivery.

The default stops at the first gate that is not approved. It does not
approve anything, and it does not spend.

``auto_approve`` is a test harness. It is not the default. The command line
does not set it. When a test passes True, each gate is recorded as
``test-auto-approve``, not as Ron. The generation gate stays closed, so a
paid call is still refused.

Picture files for this offline run are synthetic placeholders when the
production has no takes manifest. They are not a generated film.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path

from movie_swarm.budget import trailer_enabled
from movie_swarm.continuity import load_costume_lock, load_makeup_lock, load_prop_lock
from movie_swarm.director import Director
from movie_swarm.dispatch import CrewCall
from movie_swarm.handoff import write_handoff
from movie_swarm.line_producer import LineProducer, LineProducerError
from movie_swarm.roles import GENERATION_STAGE


TEST_AUTO_APPROVE_ACTOR = "test-auto-approve"
TEST_AUTO_APPROVE_NOTE = (
    "Test harness only. This approval was not made by a person. "
    "The generation gate stays closed. Do not use this on a real film."
)

# A 1 by 1 picture used only when ffmpeg cannot make a moving placeholder.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
)


class StudioError(Exception):
    """The studio run stopped because a step failed. The message says why."""


def run_studio(
    production_dir: str | Path,
    *,
    run_id: str = "studio-1",
    auto_approve: bool = False,
) -> dict:
    """Walk treatment, previs, a quote, dailies, the cut, sound, color, and delivery.

    ``auto_approve`` defaults to False. Only tests should pass True.
    """
    folder = Path(production_dir)
    if not folder.is_dir():
        raise StudioError(f"Production folder not found: {folder}")
    producer = _open_or_start(folder, run_id)
    director = Director(folder, llm=None)
    completed: list[str] = []
    try:
        if not (folder / "treatment" / "treatment.json").is_file():
            raise StudioError(
                "No treatment file. Run the Director intake, answer the questions, and then run the studio."
            )
        from movie_swarm.treatment_doc import ensure_treatment_markdown

        ensure_treatment_markdown(folder)
        stopped = _need(producer, "treatment", auto_approve, completed)
        if stopped:
            return stopped
        _previs(director, run_id)
        completed.append("previs")
        stopped = _need(producer, "previs", auto_approve, completed)
        if stopped:
            return stopped
        stopped = _need(producer, "graphics", auto_approve, completed)
        if stopped:
            return stopped
        _dispatch(director, run_id, "title-graphic-design", "build")
        completed.append("graphics")
        stopped = _need(producer, "production", auto_approve, completed)
        if stopped:
            return stopped
        _dispatch(director, run_id, "production", "plan", output_dir=str(folder / "generation"))
        completed.append("plan")
        _placeholders(folder)
        _dispatch(director, run_id, "dailies", "review")
        _dispatch(director, run_id, "vfx-supervisor", "review")
        completed.append("dailies")
        _require_circles(folder)
        stopped = _need(producer, "dailies", auto_approve, completed)
        if stopped:
            return stopped
        stopped = _need(producer, "editor", auto_approve, completed)
        if stopped:
            return stopped
        _dispatch(director, run_id, "editor", "assemble")
        completed.append("edit")
        if not (folder / "edit" / "picture-lock.json").is_file():
            raise StudioError(_edit_block(folder))
        stopped = _need(producer, "edit", auto_approve, completed)
        if stopped:
            return stopped
        stopped = _need(producer, "sound-designer", auto_approve, completed)
        if stopped:
            return stopped
        _dispatch(director, run_id, "sound-designer", "spot")
        _dispatch(director, run_id, "composer", "spot")
        completed.append("sound")
        stopped = _need(producer, "sound", auto_approve, completed)
        if stopped:
            return stopped
        _dispatch(director, run_id, "colorist", "grade")
        _dispatch(director, run_id, "mixer", "mix")
        completed.append("color-mix")
        stopped = _need(producer, "color-mix", auto_approve, completed)
        if stopped:
            return stopped
        if trailer_enabled(folder):
            for command in ("research", "guard", "sign", "plan", "cut"):
                _dispatch(director, run_id, "trailer-editor", command)
            completed.append("trailer")
        _dispatch(director, run_id, "post-supervisor", "deliver")
        completed.append("delivery")
        stopped = _need(producer, "delivery", auto_approve, completed)
        if stopped:
            return stopped
    except StudioError as exc:
        return _result(
            producer,
            status="failed",
            stopped_at=None,
            message=str(exc),
            completed=completed,
            auto_approve=auto_approve,
        )
    producer = LineProducer.open(folder, run_id)
    return _result(
        producer,
        status="complete",
        stopped_at=None,
        message=(
            "The studio run finished. The delivery gate is approved. "
            "The generation gate is still closed. Nothing was spent."
            if auto_approve
            else "The studio run finished. Every gate on this run was already approved. Nothing was spent."
        ),
        completed=completed,
        auto_approve=auto_approve,
    )


def _need(producer: LineProducer, gate: str, auto_approve: bool, completed: list[str]) -> dict | None:
    if gate == GENERATION_STAGE:
        return _result(
            producer,
            status="stopped",
            stopped_at=gate,
            message="The generation gate stays closed. This run does not approve a paid call.",
            completed=completed,
            auto_approve=auto_approve,
        )
    if producer.gate_is_open(gate):
        return None
    if auto_approve:
        producer.approve_gate(gate, "approved", TEST_AUTO_APPROVE_ACTOR, note=TEST_AUTO_APPROVE_NOTE)
        return None
    if gate == "treatment":
        message = (
            "Stopped at the treatment gate. Read treatment/treatment.md, then approve the gate, "
            "then run the studio again. This command does not approve gates."
        )
    else:
        message = (
            f"Stopped at the {gate} gate. Approve it, then run the studio again. "
            "This command does not approve gates."
        )
    return _result(
        producer,
        status="stopped",
        stopped_at=gate,
        message=message,
        completed=completed,
        auto_approve=auto_approve,
    )


def _previs(director: Director, run_id: str) -> None:
    for agent, command in (
        ("prop-master", "lock"),
        ("costume-designer", "lock"),
        ("makeup-hair", "lock"),
        ("cinematographer", "package"),
        ("cinematographer", "boards"),
        ("gaffer", "plan"),
        ("key-grip", "plan"),
        ("stunt-coordinator", "breakdown"),
        ("assistant-director", "schedule"),
        ("vfx-supervisor", "breakdown"),
        ("title-graphic-design", "research"),
        ("title-graphic-design", "guide"),
        ("script-supervisor", "check"),
    ):
        _dispatch(director, run_id, agent, command)


def _dispatch(director: Director, run_id: str, agent: str, command: str, **extra) -> None:
    call = CrewCall(
        agent=agent,
        command=command,
        estimated_cost_usd=0,
        note=command,
        production_dir=str(director.production_dir),
        **extra,
    )
    result = director.dispatch(call, run_id)
    if result.status != "ran":
        raise StudioError(f"{agent} {command} did not run. {result.message}")


def _placeholders(folder: Path) -> None:
    """Synthetic takes for an offline run. A real takes manifest is left alone."""
    manifest_path = folder / "takes" / "takes-manifest.json"
    if manifest_path.is_file():
        return
    shot_list = folder / "storyboard" / "shot-list.json"
    if not shot_list.is_file():
        raise StudioError("The storyboard did not write a shot list, so placeholders were not made.")
    data = json.loads(shot_list.read_text(encoding="utf-8"))
    shots = [shot for shot in data.get("shots") or [] if isinstance(shot, dict) and shot.get("shot_id")]
    if not shots:
        raise StudioError("The shot list is empty, so placeholders were not made.")
    look = _read_json(folder / "look" / "look.json")
    lock = load_prop_lock(folder)
    costume = load_costume_lock(folder)
    makeup = load_makeup_lock(folder)
    ffmpeg = shutil.which("ffmpeg")
    takes = []
    frames = folder / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    for shot in shots:
        shot_id = str(shot["shot_id"])
        duration = shot.get("target_duration_seconds") or shot.get("duration_seconds") or 1
        try:
            duration = max(float(duration), 0.5)
        except (TypeError, ValueError):
            duration = 1.0
        if ffmpeg:
            dest = frames / f"{shot_id}.mp4"
            _moving_clip(dest, duration)
            kind = "clip"
            relative = f"frames/{shot_id}.mp4"
        else:
            dest = frames / f"{shot_id}.png"
            dest.write_bytes(_PNG)
            kind = "frame"
            relative = f"frames/{shot_id}.png"
        text = _placeholder_text(shot, look, lock, costume, makeup)
        Path(str(dest) + ".txt").write_text(text + "\n", encoding="utf-8")
        takes.append(
            {
                "take_id": f"{shot_id}-t01",
                "shot_id": shot_id,
                "file": relative,
                "kind": kind,
                "prompt": text,
            }
        )
    payload = {"version": "1.0.0", "production_id": folder.name, "takes": takes}
    write_handoff(manifest_path, payload, schema="takes-manifest")
    note = folder / "takes" / "placeholder.txt"
    note.write_text(
        "These files are synthetic placeholders for an offline studio run.\n"
        "They are not generated pictures. A paid generation waits on the generation gate.\n",
        encoding="utf-8",
    )


def _moving_clip(dest: Path, duration: float) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return
    completed = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=160x90:rate=24:duration={duration:.3f}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "ultrafast",
            str(dest),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not dest.is_file():
        raise StudioError("ffmpeg could not make a placeholder clip.")


def _placeholder_text(shot: dict, look: dict | None, lock: dict | None, costume=None, makeup=None) -> str:
    parts = [
        str(shot.get("shot_type") or ""),
        str(shot.get("description") or ""),
        str(shot.get("generation_prompt") or ""),
        str(shot.get("continuity_notes") or ""),
    ]
    if look:
        parts.append(str(look.get("summary") or ""))
        parts.append(str(look.get("look_name") or ""))
    parts.extend(_required_phrases(shot, lock))
    parts.extend(_character_phrases(shot, costume))
    parts.extend(_character_phrases(shot, makeup))
    return "\n".join(part.strip() for part in parts if part and str(part).strip())


def _required_phrases(shot: dict, lock: dict | None) -> list[str]:
    if not lock:
        return []
    blob = json.dumps(shot).casefold()
    phrases = []
    for prop in lock.get("props") or []:
        if not isinstance(prop, dict):
            continue
        names = [prop.get("prop_id"), prop.get("name"), *(prop.get("aliases") or [])]
        if not any(name and str(name).casefold() in blob for name in names):
            continue
        for attribute in prop.get("attributes") or []:
            if not isinstance(attribute, dict):
                continue
            for phrase in attribute.get("required_phrases") or []:
                text = str(phrase).strip()
                if text and text not in phrases:
                    phrases.append(text)
    return phrases


def _character_phrases(shot: dict, lock: dict | None) -> list[str]:
    if not lock:
        return []
    blob = json.dumps(shot).casefold()
    listed = {
        str(name).casefold()
        for name in (shot.get("characters_in_shot") or shot.get("characters") or [])
        if str(name).strip()
    }
    phrases = []
    for character in lock.get("characters") or []:
        if not isinstance(character, dict):
            continue
        names = [character.get("character_id"), character.get("name"), *(character.get("aliases") or [])]
        visible = any(name and str(name).casefold() in listed for name in names) or any(
            name and len(str(name)) >= 2 and str(name).casefold() in blob for name in names
        )
        if not visible:
            continue
        for attribute in character.get("attributes") or []:
            if not isinstance(attribute, dict) or not attribute.get("must_be_stated_when_visible"):
                continue
            for phrase in attribute.get("required_phrases") or []:
                text = str(phrase).strip()
                if text and text not in phrases:
                    phrases.append(text)
    return phrases


def _require_circles(folder: Path) -> None:
    path = folder / "dailies" / "dailies-report.json"
    if not path.is_file():
        raise StudioError("Dailies did not write a report.")
    report = json.loads(path.read_text(encoding="utf-8"))
    circled = [row for row in report.get("shots") or [] if row.get("verdict") == "circle"]
    if circled:
        return
    reasons = []
    for row in report.get("shots") or []:
        reasons.append(f"{row.get('shot_id')}: {row.get('verdict')}. {' '.join(row.get('reasons') or [])}")
    detail = " ".join(reasons) or "No shots were reviewed."
    raise StudioError(f"Dailies circled no takes, so the edit cannot lock picture. {detail}")


def _edit_block(folder: Path) -> str:
    path = folder / "edit" / "rough-cut.json"
    if not path.is_file():
        return "The editor did not write a picture-lock file."
    data = json.loads(path.read_text(encoding="utf-8"))
    blockers = data.get("blockers") or []
    continuity = [item for item in data.get("continuity") or [] if item.get("status") == "fail"]
    pieces = [data.get("runtime_note") or ""]
    for item in blockers:
        pieces.append(str(item.get("detail") or item))
    for item in continuity:
        pieces.append(str(item.get("detail") or ""))
    detail = " ".join(piece for piece in pieces if piece)
    return f"The cut is not ready for picture lock. {detail}".strip()


def _open_or_start(folder: Path, run_id: str) -> LineProducer:
    state = folder / "runs" / run_id / "run-state.json"
    if state.is_file():
        return LineProducer.open(folder, run_id)
    try:
        return LineProducer.start(folder, run_id=run_id)
    except LineProducerError as exc:
        raise StudioError(str(exc)) from exc


def _result(
    producer: LineProducer,
    *,
    status: str,
    stopped_at: str | None,
    message: str,
    completed: list[str],
    auto_approve: bool,
) -> dict:
    generation = "approved" if producer.gate_is_open(GENERATION_STAGE) else "closed"
    return {
        "status": status,
        "stopped_at": stopped_at,
        "message": message,
        "completed": list(completed),
        "spent_usd": float(producer.run.data["cost_usd"]),
        "generation_gate": generation,
        "auto_approve": auto_approve,
    }


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None

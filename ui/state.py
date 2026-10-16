"""Restore one server snapshot before Streamlit creates its input widgets."""
from __future__ import annotations

from copy import deepcopy

from ts.desk import saved_run_state

DRAFT_WIDGETS = (
    "direction_input", "correction_input", "period_start", "period_end",
    "old_tech_query", "old_tech_families",
)


def start_demo(state) -> None:
    """Reset this browser's presentation only; retain an immutable saved example."""
    state["demo_saved_workspace"] = deepcopy(state.get("workspace") or {})
    state["demo_session"] = {"viewed_run_ids": [], "archive_submissions": 0, "notice": ""}
    for key in (
        "payload", "meta", "pending_workspace", "pending_workspace_kind", "pending_run_response",
        "latest_issue", "latest_loaded", "workspace_notice", "signal_selected", "potential_selected",
        "old_selected", "old_selection_key",
    ):
        state.pop(key, None)
    state["input_drafts"] = {}
    for key in DRAFT_WIDGETS:
        state[key] = [] if key == "old_tech_families" else ""
        remember_draft(state, key)
    state["potential_filter"] = ""
    state["latest_checked"] = True
    state["active_module"] = "Тонкие сигналы"


def stop_demo(state) -> None:
    state.pop("demo_session", None)
    state.pop("demo_saved_workspace", None)
    state.pop("latest_checked", None)


def record_demo_run(state, payload: dict, *, saved: bool = False, viewed: bool = True) -> None:
    if "demo_session" not in state:
        return
    demo = deepcopy(state["demo_session"])
    run_id = payload.get("run_id")
    if viewed and run_id and run_id not in demo["viewed_run_ids"]:
        demo["viewed_run_ids"].append(run_id)
    if saved:
        notice = "Сохранённый результат · открыт повторно, новый поиск не запускался"
    elif payload.get("repeated") is True:
        notice = "Повторно использован точный сохранённый результат. Источники и модели повторно не запускались."
    else:
        notice = (
            "Получен результат поискового конвейера. Кэш материалов и моделей, а также ранее найденные "
            "публикации могли использоваться повторно."
        )
    demo["notice"] = notice
    demo["response_run_id"] = run_id
    state["demo_session"] = demo


def open_saved_example(state) -> None:
    snapshot = state.get("demo_saved_workspace") or {}
    run = snapshot.get("run")
    if not (run and snapshot.get("run_compatible") and saved_run_state(run)["safe_to_autoload"]):
        state["latest_issue"] = "Совместимый сохранённый пример недоступен. Можно запустить новый поиск."
        return
    state["payload"] = deepcopy(run)
    state["meta"] = {"direction": run.get("query", ""), "correction": "", "start": "", "end": ""}
    for key in ("direction_input", "correction_input", "period_start", "period_end"):
        state[key] = run.get("query", "") if key == "direction_input" else ""
        remember_draft(state, key)
    state.pop("latest_issue", None)
    state["signal_selected"] = state["potential_selected"] = 0
    record_demo_run(state, run, saved=True)


def record_demo_archive(state, snapshot: dict) -> None:
    """Apply one successful explicit archive response without selecting a Run."""
    state["workspace"] = snapshot
    archive = snapshot.get("archive") or {}
    for key, value in (
        ("old_tech_query", archive.get("query", "")),
        ("old_tech_families", archive.get("families", [])),
    ):
        state[key] = deepcopy(value)
        remember_draft(state, key)
    demo = deepcopy(state["demo_session"])
    demo["archive_submissions"] += 1
    state["demo_session"] = demo
    state["old_selected"] = 0


def remember_draft(state, key: str) -> None:
    """Keep edits outside widget storage, which Streamlit clears for hidden modules."""
    drafts = dict(state.get("input_drafts") or {})
    drafts[key] = deepcopy(state[key])
    state["input_drafts"] = drafts


def sync_draft_widget(state, key: str, default) -> None:
    """Send the restored value to the client, retaining this session's active edit."""
    drafts = state.get("input_drafts") or {}
    # Explicit assignment is required: setdefault does not synchronize a hidden
    # widget's existing server value into the new browser widget's protobuf.
    state[key] = deepcopy(drafts.get(key, state.get(key, default)))


def restore_workspace(state, snapshot: dict) -> None:
    state["input_drafts"] = {}
    state["workspace"] = snapshot
    state["latest_checked"] = True
    state["latest_loaded"] = True
    issues = list(snapshot.get("issues") or [])
    run = snapshot.get("run")
    if run and snapshot.get("run_compatible") and saved_run_state(run)["safe_to_autoload"]:
        state["payload"] = run
        state["meta"] = {"direction": run.get("query", ""), "correction": "", "start": "", "end": ""}
        state["direction_input"] = run.get("query", "")
        for key in ("correction_input", "period_start", "period_end"):
            state[key] = ""
    else:
        state.pop("payload", None)
        if run and not issues:
            issues.append("Сохранённый прогон несовместим с текущим экраном.")
    if issues:
        state["latest_issue"] = " ".join(issues)
    else:
        state.pop("latest_issue", None)
    archive = snapshot.get("archive") or {}
    state["old_tech_query"] = archive.get("query", "")
    state["old_tech_families"] = [
        family for family in archive.get("families") or []
        if family in archive.get("available_families", archive.get("families", []))
    ]
    for key in DRAFT_WIDGETS:
        if key in state:
            remember_draft(state, key)
    for key in ("signal_selected", "potential_selected", "old_selected"):
        state[key] = 0

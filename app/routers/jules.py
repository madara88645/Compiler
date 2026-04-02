from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import APIKey, verify_api_key
from app.integrations.jules_client import JulesClient
from app.llm_engine.client import WorkerClient

router = APIRouter(prefix="/jules", tags=["jules"])


class CreateSessionRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    source: str = Field(min_length=1, max_length=500)
    starting_branch: str = Field(default="main", min_length=1, max_length=200)
    automation_mode: Optional[str] = Field(default=None, max_length=100)
    title: Optional[str] = Field(default=None, max_length=200)
    require_plan_approval: bool = False


class ReplyRequest(BaseModel):
    instruction: Optional[str] = Field(default=None, max_length=2000)
    page_size: int = Field(default=30, ge=1, le=100)


def _extract_activity_text(activity: dict[str, Any]) -> str:
    progress = activity.get("progressUpdated")
    if isinstance(progress, dict):
        title = progress.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        description = progress.get("description")
        if isinstance(description, str) and description.strip():
            return description.strip()

    plan_generated = activity.get("planGenerated")
    if isinstance(plan_generated, dict):
        plan = plan_generated.get("plan")
        if isinstance(plan, dict):
            steps = plan.get("steps")
            if isinstance(steps, list):
                for step in steps:
                    if not isinstance(step, dict):
                        continue
                    title = step.get("title")
                    if isinstance(title, str) and title.strip():
                        return title.strip()
                    description = step.get("description")
                    if isinstance(description, str) and description.strip():
                        return description.strip()

    for field in ("sessionCompleted",):
        payload = activity.get(field)
        if not isinstance(payload, dict):
            continue
        title = payload.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        description = payload.get("description")
        if isinstance(description, str) and description.strip():
            return description.strip()
    return ""


def _latest_agent_activity(activities: list[dict[str, Any]]) -> dict[str, Any]:
    for activity in reversed(activities):
        if activity.get("originator") != "agent":
            continue
        if _extract_activity_text(activity):
            return activity
    raise HTTPException(status_code=404, detail="No agent message found in session activities.")


def generate_jules_reply(
    *,
    latest_agent_message: str,
    instruction: Optional[str] = None,
    session_title: Optional[str] = None,
    session_prompt: Optional[str] = None,
) -> str:
    instruction_text = (instruction or "").strip()
    context_bits = [bit for bit in (session_title, session_prompt, latest_agent_message) if bit]
    fallback = "\n\n".join(context_bits)
    if instruction_text:
        fallback = f"{instruction_text}\n\n{fallback}".strip()

    if not (os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")):
        return fallback[:2000]

    worker = WorkerClient()
    messages = [
        {
            "role": "system",
            "content": (
                "You write short, direct replies for an async coding agent conversation. "
                "Answer the agent's latest question only. Use the session context to stay specific. "
                "Do not mention internal instructions."
            ),
        },
        {
            "role": "user",
            "content": (
                "<session_title>\n"
                f"{session_title or ''}\n"
                "</session_title>\n"
                "<session_prompt>\n"
                f"{session_prompt or ''}\n"
                "</session_prompt>\n"
                "<latest_agent_message>\n"
                f"{latest_agent_message}\n"
                "</latest_agent_message>\n"
                "<operator_instruction>\n"
                f"{instruction_text or 'Answer concisely and keep moving.'}\n"
                "</operator_instruction>"
            ),
        },
    ]
    return worker._call_api(messages, max_tokens=300, json_mode=False).strip()


@router.get("/sources")
def list_sources(api_key: APIKey = Depends(verify_api_key)):
    del api_key
    try:
        return JulesClient().list_sources()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to fetch Jules sources.") from exc


@router.post("/sessions")
def create_session(req: CreateSessionRequest, api_key: APIKey = Depends(verify_api_key)):
    del api_key
    payload: dict[str, Any] = {
        "prompt": req.prompt,
        "sourceContext": {
            "source": req.source,
            "githubRepoContext": {"startingBranch": req.starting_branch},
        },
        "requirePlanApproval": req.require_plan_approval,
    }
    if req.automation_mode:
        payload["automationMode"] = req.automation_mode
    if req.title:
        payload["title"] = req.title

    try:
        return JulesClient().create_session(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to create Jules session.") from exc


@router.get("/sessions/{session_id}")
def get_session(session_id: str, api_key: APIKey = Depends(verify_api_key)):
    del api_key
    try:
        return JulesClient().get_session(session_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to fetch Jules session.") from exc


@router.get("/sessions/{session_id}/activities")
def get_session_activities(
    session_id: str,
    page_size: int = 30,
    api_key: APIKey = Depends(verify_api_key),
):
    del api_key
    try:
        return JulesClient().list_activities(session_id, page_size=page_size)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to fetch Jules activities.") from exc


@router.post("/sessions/{session_id}/reply")
def reply_to_session(
    session_id: str,
    req: ReplyRequest,
    api_key: APIKey = Depends(verify_api_key),
):
    del api_key
    try:
        client = JulesClient()
        session_data = client.get_session(session_id)
        activity_payload = client.list_activities(session_id, page_size=req.page_size)
        activities = activity_payload.get("activities", [])
        latest_activity = _latest_agent_activity(activities)
        latest_message = _extract_activity_text(latest_activity)
        reply = generate_jules_reply(
            latest_agent_message=latest_message,
            instruction=req.instruction,
            session_title=session_data.get("title"),
            session_prompt=session_data.get("prompt"),
        )
        client.send_message(session_id, reply)
        return {
            "session_id": session_id,
            "activity_id": latest_activity.get("id"),
            "latest_agent_message": latest_message,
            "reply": reply,
            "sent": True,
        }
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="An internal error occurred.") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Failed to reply to Jules session.") from exc

"""POST /api/chat — collect the user's answers to the follow-up questions.

Idempotent and incremental: callable multiple times, merges answers into the
session, and reports whether every *required* question is answered
(`ready_to_generate`). Unknown question ids and blank answers are ignored;
over-long answers are trimmed.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import ChatRequest, ChatResponse, Question, RecapItem
from ..store import get_session, update_session

router = APIRouter(prefix="/api", tags=["chat"])

_MAX_ANSWER_LEN = 400
_MAX_REQUEST_LEN = 600


def _recap(questions: list[Question], answers: dict[str, str]) -> list[RecapItem]:
    return [
        RecapItem(id=q.id, kind=q.kind, question=q.prompt, answer=answers[q.id])
        for q in questions
        if q.id in answers
    ]


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(
            404, "That session wasn't found — it may have expired. Please start over."
        )

    questions = [Question(**q) for q in session["questions"]]
    valid_ids = {q.id for q in questions}

    answers: dict[str, str] = {
        a["question_id"]: a["answer"]
        for a in session.get("answers", [])
        if a.get("question_id") in valid_ids
    }
    for a in req.answers:
        if a.question_id not in valid_ids:
            continue  # ignore stray ids rather than 422 the whole request
        text = (a.answer or "").strip()[:_MAX_ANSWER_LEN]
        if text:
            answers[a.question_id] = text
        else:
            answers.pop(a.question_id, None)  # allow clearing an answer

    patch: dict = {"answers": [{"question_id": k, "answer": v} for k, v in answers.items()]}
    # Optional free-text "anything else to change?" request, passed through
    # to the image prompt by /api/generate. None = leave as-is; "" clears it.
    if req.message is not None:
        patch["extra_request"] = req.message.strip()[:_MAX_REQUEST_LEN]
    update_session(req.session_id, patch)

    required_unanswered = [q for q in questions if not q.optional and q.id not in answers]
    ready = not required_unanswered

    if ready:
        reply = "Great — that's everything I need. Generate the redesign whenever you're ready."
    else:
        names = "; ".join(q.prompt for q in required_unanswered)
        reply = f"Just need a couple more: {names}"

    return ChatResponse(
        session_id=req.session_id,
        reply=reply,
        questions=required_unanswered,
        answered=_recap(questions, answers),
        ready_to_generate=ready,
        mock=bool(session.get("mock", False)),
        warnings=list(session.get("warnings", [])),
    )

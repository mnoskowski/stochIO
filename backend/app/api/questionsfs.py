from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from app.core.database import db
from app.api.auth import get_current_user
from app.schemas.user import User
from app.srs.fsrs import FSRSManager, FSRSAnswerRequest
import asyncpg
import json
from datetime import timezone, datetime
router = APIRouter(prefix="/questions-fs", tags=["questions-fs"])

def harmonic_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    # avoid division by zero for cards with 0 retrievability
    values = [max(v, 1e-9) for v in values]
    return len(values) / sum(1/v for v in values)

async def update_topic_stats(user_id: int, topic_id: int, conn: asyncpg.Connection):
    # get all cards for this user in this topic
    cards = await conn.fetch("""
        SELECT p.card_data FROM user_question_progress p
        JOIN question_topics qt ON p.question_id = qt.question_id
        WHERE p.user_id = $1 AND qt.topic_id = $2
    """, user_id, topic_id)

    if not cards:
        return
    fsrs_managers = [FSRSManager(c["card_data"]) for c in cards]
    retrievabilities = [fs.get_retrievability() for fs in fsrs_managers]
    avg_retrievability = harmonic_mean(retrievabilities)

    due_count = await conn.fetchval("""
        SELECT COUNT(*) FROM user_question_progress p
        JOIN question_topics qt ON p.question_id = qt.question_id
        WHERE p.user_id = $1 AND qt.topic_id = $2
        AND p.next_review <= NOW()
    """, user_id, topic_id)

    await conn.execute("""
        INSERT INTO user_topic_stats (user_id, topic_id, average_retrievability, cards_due, cards_reviewed)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id, topic_id) DO UPDATE SET
            average_retrievability = $3,
            cards_due = $4,
            cards_reviewed = $5,
            last_activity = NOW()
    """, user_id, topic_id, avg_retrievability, due_count, len(cards))
@router.post("/answer")
async def answer_question(
    answer_request: FSRSAnswerRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(db.acquire)
):
    if answer_request.rating not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 4")

    progress = await conn.fetchrow(
            "SELECT card_data FROM user_question_progress WHERE user_id = $1 AND question_id = $2",
            current_user.id, answer_request.question_id
        )
    fsrs_manager = FSRSManager(progress["card_data"] if progress else None)
    card_json, review_log_json = fsrs_manager.review(
        rating=answer_request.rating,
        review_time_ms=answer_request.review_time_ms
    )

    next_review = json.loads(card_json)['due']
    next_review = datetime.fromisoformat(next_review).astimezone(timezone.utc)

    await conn.execute("""
        INSERT INTO user_question_progress (user_id, question_id, card_data, next_review)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, question_id)
        DO UPDATE SET card_data = $3, next_review = $4
    """, current_user.id, answer_request.question_id, card_json, next_review)

    # insert review log
    await conn.execute("""
        INSERT INTO review_logs (user_id, question_id, log_data)
        VALUES ($1, $2, $3)
    """, current_user.id, answer_request.question_id, review_log_json)
    # Get which topics this question belongs to
    topic_ids = await conn.fetch("""
        SELECT topic_id FROM question_topics WHERE question_id = $1
    """, answer_request.question_id)

    for record in topic_ids:
        await update_topic_stats(current_user.id, record["topic_id"], conn)
    return {"message": "Answer recorded successfully", "next_review": next_review}

@router.post("/flashcard-create")
async def create_flashcard(
    question_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(db.acquire)
):
    # create a new flashcard for the question if it doesn't exist
    progress = await conn.fetchrow(
            "SELECT card_data FROM user_question_progress WHERE user_id = $1 AND question_id = $2",
            current_user.id, question_id
        )
    if progress is None:
        fsrs_manager = FSRSManager(None)
        await conn.execute("""
            INSERT INTO user_question_progress (user_id, question_id, card_data)
            VALUES ($1, $2, $3)
        """, current_user.id, question_id, fsrs_manager.card.to_json())
        return {"message": "Flashcard created successfully"}
    else:
        return {"message": "Flashcard already exists"}

@router.get('/due')
async def get_due(
    limit: int = Query(20, le=100),
    current_user: User = Depends(get_current_user),
    conn=Depends(db.acquire)
):
    rows = await conn.fetch("""
        SELECT q.*, p.card_data, p.next_review
        FROM user_question_progress p
        JOIN questions q ON p.question_id = q.id
        WHERE p.user_id = $1 AND p.next_review <= NOW()
        ORDER BY p.next_review ASC
        LIMIT $2
    """, current_user.id, limit)

    return [dict(r) for r in rows]
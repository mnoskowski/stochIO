from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from app.core.database import db
from app.api.auth import get_current_user
from app.schemas.user import User
import asyncpg
router = APIRouter(prefix="/questions", tags=["questions"])

@router.get("/")
async def get_questions(
    topic: str | None = Query(None),
    difficulty: int | None = Query(None),
    source: str | None = Query(None),
    type: str | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    conn=Depends(db.acquire)
):
    conditions = []
    params = []
    i = 1
    if topic:
        conditions.append(f"""
            q.id IN (
                SELECT qt.question_id FROM question_topics qt
                JOIN topics t ON qt.topic_id = t.id
                WHERE t.slug = ${i}
            )
        """)
        params.append(topic)
        i += 1

    if difficulty:
        conditions.append(f"q.difficulty = ${i}")
        params.append(difficulty)
        i += 1

    if type:
        conditions.append(f"q.type = ${i}")
        params.append(type)
        i += 1

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    params.extend([limit, offset])

    rows = await conn.fetch(f"""
        SELECT q.* FROM questions q
        {where}
        ORDER BY q.created_at DESC
        LIMIT ${i} OFFSET ${i+1}
    """, *params)

    return [dict(r) for r in rows]
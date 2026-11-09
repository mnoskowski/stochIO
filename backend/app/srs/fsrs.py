import datetime

from fsrs import Card, Rating, Scheduler
from pydantic import BaseModel


class FSRSAnswerRequest(BaseModel):
    question_id: int
    rating: int # 1-4
    review_time_ms: int
class FSRSManager:
    def __init__(self, card_json: str | None):
        self.scheduler = Scheduler()
        self.review_log = None
        self.now = datetime.datetime.now(datetime.UTC)

        if card_json:
            self.card = Card.from_json(card_json) if card_json else Card()
        else:
            self.card = Card()

    def review(self, rating: int = 1, review_time_ms: int = 0):
        self.card, self.review_log = self.scheduler.review_card(
            self.card,
            Rating(rating),
            self.now,
            review_time_ms
        )
        return self.card.to_json(), self.review_log.to_json()
    def get_retrievability(self) -> float:
        return self.scheduler.get_card_retrievability(self.card)

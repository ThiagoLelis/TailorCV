"""Modelos de dados compartilhados pelo pipeline."""
from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    url: str
    ats_platform: str
    title: str
    company: str | None = None
    date_posted: date | None = None
    description: str = Field(default="", description="Descrição limpa, em Markdown")

    def is_stale(self, max_age_days: int = 30, today: date | None = None) -> bool:
        """True se a vaga foi publicada há mais de `max_age_days` dias.

        Vagas sem data são mantidas (não há como afirmar que são antigas).
        """
        if self.date_posted is None:
            return False
        today = today or date.today()
        return (today - self.date_posted) > timedelta(days=max_age_days)

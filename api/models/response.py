from typing import Literal

from pydantic import BaseModel, Field


class Issue(BaseModel):
    severity: Literal["high", "medium", "low"]
    area: str
    description: str
    suggestion: str


class Annotation(BaseModel):
    frame_index: int = Field(default=0, ge=0)
    x_pct: float = Field(ge=0, le=100)
    y_pct: float = Field(ge=0, le=100)
    width_pct: float = Field(ge=0, le=100)
    height_pct: float = Field(ge=0, le=100)
    issue_index: int = Field(ge=0)
    label: str


class PersonaFeedback(BaseModel):
    persona: str
    persona_label: str
    overall_impression: str
    issues: list[Issue]
    positives: list[str]
    score: int = Field(ge=1, le=10)
    annotations: list[Annotation] | None = None


class FeedbackResponse(BaseModel):
    feedback: list[PersonaFeedback]

from typing import Literal
from pydantic import BaseModel, Field


class STARScore(BaseModel):
    situation: float = Field(description="0–10: did the candidate set the context?", ge=0.0, le=10.0)
    task: float = Field(description="0–10: did the candidate explain their responsibility?", ge=0.0, le=10.0)
    action: float = Field(description="0–10: did the candidate describe what THEY specifically did?", ge=0.0, le=10.0)
    result: float = Field(description="0–10: did the candidate quantify or describe the outcome?", ge=0.0, le=10.0)


class BehavioralReview(BaseModel):
    question: str = Field(description="The behavioral question that was asked")
    star_score: STARScore = Field(description="STAR component scores for this answer")
    feedback: str = Field(description="Specific feedback on how to improve the STAR structure")


class TechnicalReview(BaseModel):
    question: str = Field(description="The technical question that was asked")
    accuracy: float = Field(description="0–10: correctness of the technical facts stated", ge=0.0, le=10.0)
    depth: float = Field(description="0–10: depth beyond surface-level explanation", ge=0.0, le=10.0)
    practical: float = Field(description="0–10: connection to real-world experience", ge=0.0, le=10.0)
    feedback: str = Field(description="Specific feedback on technical accuracy, depth, or practical grounding")


class CommunicationReview(BaseModel):
    clarity: float = Field(description="0–10: well-structured and easy to follow", ge=0.0, le=10.0)
    conciseness: float = Field(description="0–10: appropriate length with no rambling", ge=0.0, le=10.0)
    confidence: float = Field(description="0–10: assertive language, minimal hedging", ge=0.0, le=10.0)
    feedback: str = Field(description="Overall communication feedback across all answers")


class CoachReview(BaseModel):
    overall_score: float = Field(description="Composite interview score from 0 to 100", ge=0.0, le=100.0)
    behavioral_reviews: list[BehavioralReview] = Field(
        default_factory=list,
        description="Per-question STAR analysis for behavioral questions",
    )
    technical_reviews: list[TechnicalReview] = Field(
        default_factory=list,
        description="Per-question depth analysis for technical questions",
    )
    communication: CommunicationReview = Field(
        description="Cross-question communication assessment"
    )
    top_strengths: list[str] = Field(
        default_factory=list,
        description="Top 3 strengths with specific examples from the interview",
    )
    areas_for_improvement: list[str] = Field(
        default_factory=list,
        description="Top 3 improvement areas with specific actionable suggestions",
    )
    recommended_topics: list[str] = Field(
        default_factory=list,
        description="Topics to study or practise based on weak areas identified",
    )
    readiness: Literal["yes", "almost", "needs_more_practice"] = Field(
        description="Overall readiness verdict: 'yes', 'almost', or 'needs_more_practice'"
    )
    summary: str = Field(
        description="3–5 sentence overall assessment of the candidate's interview performance"
    )

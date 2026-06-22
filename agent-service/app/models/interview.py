from typing import Optional
from pydantic import BaseModel, Field


class InterviewQuestion(BaseModel):
    text: str = Field(description="Full interview question text")
    type: str = Field(description="Question type: 'behavioral' or 'technical'")
    category: str = Field(description="Skill or topic category, e.g. 'api_design', 'conflict_resolution'")
    difficulty: str = Field(description="Difficulty level: 'easy', 'medium', or 'hard'")
    topics: list[str] = Field(
        default_factory=list,
        description="Related topic tags, e.g. ['system_design', 'databases']",
    )


class AnswerEvaluation(BaseModel):
    question: str = Field(description="The question that was answered")
    answer: str = Field(description="The candidate's answer")
    relevance_score: float = Field(description="0–10: did the answer address the actual question?", ge=0.0, le=10.0)
    depth_score: float = Field(description="0–10: technical depth or STAR completeness", ge=0.0, le=10.0)
    communication_score: float = Field(description="0–10: clarity and structure", ge=0.0, le=10.0)
    overall_score: float = Field(description="0–10: weighted composite score", ge=0.0, le=10.0)
    strengths: list[str] = Field(default_factory=list, description="Positive aspects of the answer")
    improvements: list[str] = Field(default_factory=list, description="Specific areas to improve")
    follow_up: Optional[str] = Field(None, description="Suggested follow-up question, if any")


class InterviewSessionData(BaseModel):
    session_id: str = Field(description="Unique session identifier (UUID)")
    jd_title: str = Field(description="Job title from the job description")
    questions: list[InterviewQuestion] = Field(
        default_factory=list, description="Ordered list of questions for this session"
    )
    answers: list[AnswerEvaluation] = Field(
        default_factory=list, description="Evaluations collected so far"
    )
    current_question_index: int = Field(
        default=0, description="Index of the next question to ask (0-based)"
    )
    status: str = Field(
        default="active",
        description="Session lifecycle: 'active' while questions remain, 'completed' after all answered",
    )
    started_at: str = Field(description="ISO-8601 datetime when the session was created")
    ended_at: Optional[str] = Field(None, description="ISO-8601 datetime when the session ended")

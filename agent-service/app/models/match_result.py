from pydantic import BaseModel, Field


class MatchResult(BaseModel):
    overall_score: float = Field(description="Weighted composite score from 0 to 100")
    skill_score: float = Field(description="Skill alignment score from 0 to 100")
    experience_score: float = Field(description="Experience level score from 0 to 100")
    keyword_score: float = Field(description="ATS keyword coverage score from 0 to 100")
    missing_required_skills: list[str] = Field(
        default_factory=list,
        description="Required JD skills not found in the resume",
    )
    missing_preferred_skills: list[str] = Field(
        default_factory=list,
        description="Preferred JD skills not found in the resume",
    )
    improvement_suggestions: list[str] = Field(
        default_factory=list,
        description="Specific, actionable suggestions for improving the resume against this JD",
    )
    interview_focus_areas: list[str] = Field(
        default_factory=list,
        description="Topics the candidate should prepare for in interviews",
    )
    overall_assessment: str = Field(
        description="2-3 sentence narrative summary of the match quality and top gaps"
    )
    matched_skills: list[str] = Field(
        default_factory=list,
        description="Skills found in both the resume and the JD",
    )
    matched_keywords: list[str] = Field(
        default_factory=list,
        description="JD keywords found in the resume raw text",
    )
    ats_present: list[str] = Field(
        default_factory=list,
        description="Industry-standard ATS keywords found in the resume",
    )
    ats_missing: list[str] = Field(
        default_factory=list,
        description="Industry-standard ATS keywords absent from the resume",
    )
    ats_coverage_percent: float = Field(
        default=0.0,
        description="Percentage of industry-standard ATS keywords present in the resume (0–100)",
    )

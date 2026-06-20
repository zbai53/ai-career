from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# Imported at runtime (not just TYPE_CHECKING) so Pydantic can resolve the
# forward reference used in RewriteResult.fidelity_report.
from app.models.fidelity_report import FidelityReport  # noqa: F401


class RewrittenBullet(BaseModel):
    original: str = Field(description="The original bullet point text")
    rewritten: str = Field(description="The rewritten bullet point text")
    changes_made: list[str] = Field(
        default_factory=list,
        description="List of specific changes made and the reason for each",
    )


class RewrittenExperience(BaseModel):
    company: str = Field(description="Employer name, copied from resume")
    title: str = Field(description="Job title, copied from resume")
    original_bullets: list[str] = Field(
        default_factory=list,
        description="Original bullet points before rewriting",
    )
    rewritten_bullets: list[RewrittenBullet] = Field(
        default_factory=list,
        description="Rewritten bullets, one per original bullet in the same order",
    )


class RewriteResult(BaseModel):
    experiences: list[RewrittenExperience] = Field(
        default_factory=list,
        description="Rewritten experience entries, one per experience in the resume",
    )
    keywords_injected: list[str] = Field(
        default_factory=list,
        description="JD keywords that were successfully injected into the rewritten bullets",
    )
    overall_improvement_summary: str = Field(
        description="2-3 sentence summary of the overall improvements made",
    )
    rewrite_confidence: float = Field(
        description="Model confidence that the rewrite improved the match without fabrication, 0.0-1.0",
        ge=0.0,
        le=1.0,
    )
    fidelity_report: Optional[FidelityReport] = Field(
        default=None,
        description="Fidelity check result; None if check was not run",
    )
    rewrite_attempts: int = Field(
        default=1,
        description="Number of rewrite attempts made (1 = first pass passed; 2 = fidelity retry)",
        ge=1,
    )

from pydantic import BaseModel, Field

_DEFAULT_THRESHOLD = 0.85


class FidelityFlag(BaseModel):
    entity: str = Field(description="The entity text that was flagged as potentially fabricated")
    entity_type: str = Field(
        description="Type of entity: 'company', 'title', 'technology', 'metric', or 'date'"
    )
    found_in: str = Field(description="The rewritten bullet text where the entity was found")
    severity: str = Field(
        description="Risk level: 'high' (company/title/date), 'medium' (metric), 'low' (technology)"
    )


class FidelityReport(BaseModel):
    fidelity_score: float = Field(
        description="Score from 0.0 (full hallucination) to 1.0 (perfectly faithful)",
        ge=0.0,
        le=1.0,
    )
    flags: list[FidelityFlag] = Field(
        default_factory=list,
        description="List of entities found in rewritten bullets that were absent from the original resume",
    )
    total_original_entities: int = Field(
        description="Total number of distinct entities extracted from the original resume"
    )
    total_rewritten_entities: int = Field(
        description="Total number of distinct entities extracted from the rewritten bullets"
    )
    new_entities_found: int = Field(
        description="Number of entities in rewritten bullets that did not appear in the original"
    )
    passed: bool = Field(
        description="True when fidelity_score >= threshold"
    )
    threshold: float = Field(
        default=_DEFAULT_THRESHOLD,
        description="Minimum acceptable fidelity score; configurable, defaults to 0.85",
    )

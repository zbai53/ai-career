from typing import Optional
from pydantic import BaseModel, Field


class JDSkillRequirement(BaseModel):
    name: str = Field(description="Skill name, e.g. 'Python', 'Kubernetes', 'System Design'")
    is_required: bool = Field(
        description="True if the skill is listed as required; False if preferred or nice-to-have"
    )
    category: str = Field(
        description="Skill category: 'language', 'framework', 'tool', 'cloud', 'database', 'domain', 'soft_skill', or similar"
    )


class ParsedJobDescription(BaseModel):
    title: str = Field(description="Job title as listed in the posting")
    company: Optional[str] = Field(None, description="Company or organization name")
    location: Optional[str] = Field(None, description="Office location, city, or 'Remote'")
    remote_type: Optional[str] = Field(
        None, description="Work arrangement: 'remote', 'hybrid', or 'onsite'"
    )
    employment_type: Optional[str] = Field(
        None, description="Employment type: 'full-time', 'part-time', 'contract', or 'intern'"
    )
    min_years_experience: Optional[int] = Field(
        None, description="Minimum years of experience required", ge=0
    )
    max_years_experience: Optional[int] = Field(
        None, description="Maximum years of experience specified (upper bound of a range)", ge=0
    )
    salary_min: Optional[int] = Field(
        None, description="Minimum annual salary in whole units of salary_currency", ge=0
    )
    salary_max: Optional[int] = Field(
        None, description="Maximum annual salary in whole units of salary_currency", ge=0
    )
    salary_currency: Optional[str] = Field(
        None, description="ISO 4217 currency code for salary figures, e.g. 'USD', 'EUR', 'GBP'"
    )
    responsibilities: list[str] = Field(
        default_factory=list,
        description="Day-to-day responsibilities and duties listed in the job description",
    )
    skills: list[JDSkillRequirement] = Field(
        default_factory=list,
        description="Required and preferred skills extracted from the job description",
    )
    qualifications: list[str] = Field(
        default_factory=list,
        description="Education requirements, certifications, and other formal qualifications",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="ATS-relevant terms and phrases extracted from the posting for resume matching",
    )
    industry: Optional[str] = Field(
        None, description="Industry or domain sector, e.g. 'fintech', 'healthcare', 'e-commerce'"
    )
    raw_text: str = Field(
        description="Original job description text preserved for reference and re-parsing"
    )
    source_url: Optional[str] = Field(
        None, description="URL of the original job posting"
    )
    parse_confidence: float = Field(
        description="Model confidence in parse quality, from 0.0 (very low) to 1.0 (very high)",
        ge=0.0,
        le=1.0,
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                    "title": "Senior Backend Engineer",
                    "company": "Databricks",
                    "location": "San Francisco, CA",
                    "remote_type": "hybrid",
                    "employment_type": "full-time",
                    "min_years_experience": 5,
                    "max_years_experience": 8,
                    "salary_min": 180000,
                    "salary_max": 240000,
                    "salary_currency": "USD",
                    "responsibilities": [
                        "Design and implement scalable backend services handling petabyte-scale data workloads",
                        "Own the full lifecycle of services from design through deployment and on-call support",
                        "Collaborate with data engineering and ML platform teams to define API contracts",
                        "Drive engineering best practices including code reviews, design docs, and incident post-mortems",
                        "Mentor junior and mid-level engineers within the team",
                    ],
                    "skills": [
                        {"name": "Python", "is_required": True, "category": "language"},
                        {"name": "Scala", "is_required": False, "category": "language"},
                        {"name": "Java", "is_required": False, "category": "language"},
                        {"name": "Apache Spark", "is_required": True, "category": "framework"},
                        {"name": "gRPC", "is_required": True, "category": "tool"},
                        {"name": "Kubernetes", "is_required": True, "category": "tool"},
                        {"name": "Docker", "is_required": True, "category": "tool"},
                        {"name": "AWS", "is_required": True, "category": "cloud"},
                        {"name": "PostgreSQL", "is_required": True, "category": "database"},
                        {"name": "Delta Lake", "is_required": False, "category": "framework"},
                        {"name": "Distributed systems design", "is_required": True, "category": "domain"},
                        {"name": "Technical communication", "is_required": True, "category": "soft_skill"},
                    ],
                    "qualifications": [
                        "Bachelor's or Master's degree in Computer Science, Engineering, or equivalent practical experience",
                        "5+ years of professional software engineering experience",
                        "Demonstrated experience designing high-throughput, low-latency distributed systems",
                        "Experience with cloud-native infrastructure on AWS, GCP, or Azure",
                    ],
                    "keywords": [
                        "distributed systems",
                        "Apache Spark",
                        "petabyte scale",
                        "gRPC",
                        "microservices",
                        "Kubernetes",
                        "data platform",
                        "Python",
                        "Scala",
                        "high availability",
                        "on-call",
                        "SLO",
                        "cloud native",
                        "Delta Lake",
                    ],
                    "industry": "data and AI infrastructure",
                    "raw_text": "Senior Backend Engineer\nDatabricks | San Francisco, CA (Hybrid)\n$180,000 – $240,000 ...",
                    "source_url": "https://databricks.com/company/careers/open-positions/senior-backend-engineer-12345",
                    "parse_confidence": 0.91,
            }
        }
    }

from typing import Optional
from pydantic import BaseModel, Field


class ResumeContact(BaseModel):
    name: Optional[str] = Field(None, description="Full name of the candidate")
    email: Optional[str] = Field(None, description="Primary email address")
    phone: Optional[str] = Field(None, description="Phone number in any format")
    address: Optional[str] = Field(None, description="City, state, or full mailing address")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    github_url: Optional[str] = Field(None, description="GitHub profile URL")
    portfolio_url: Optional[str] = Field(None, description="Personal website or portfolio URL")


class ResumeEducation(BaseModel):
    institution: str = Field(description="Name of the school or university")
    degree: str = Field(description="Degree type, e.g. 'Bachelor of Science', 'Master of Engineering'")
    field_of_study: str = Field(description="Major or area of study, e.g. 'Computer Science'")
    start_date: Optional[str] = Field(None, description="Start date in YYYY-MM format")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM format; null if ongoing")
    gpa: Optional[float] = Field(None, description="GPA on a 4.0 scale", ge=0.0, le=4.0)
    highlights: list[str] = Field(default_factory=list, description="Notable awards, honors, or activities")


class ResumeExperience(BaseModel):
    company: str = Field(description="Employer or organization name")
    title: str = Field(description="Job title or role")
    location: Optional[str] = Field(None, description="City, state, or 'Remote'")
    start_date: Optional[str] = Field(None, description="Start date in YYYY-MM format")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM format; null if current")
    is_current: bool = Field(False, description="True if this is the candidate's current role")
    bullets: list[str] = Field(default_factory=list, description="Achievement and responsibility bullet points")
    technologies: list[str] = Field(default_factory=list, description="Technologies, languages, or tools used in this role")


class ResumeProject(BaseModel):
    name: str = Field(description="Project name or title")
    description: str = Field(description="Brief description of the project and its purpose")
    url: Optional[str] = Field(None, description="Link to live project, repo, or demo")
    technologies: list[str] = Field(default_factory=list, description="Technologies used in the project")
    highlights: list[str] = Field(default_factory=list, description="Key accomplishments or features")


class ResumeCertification(BaseModel):
    name: str = Field(description="Full certification name")
    issuer: str = Field(description="Issuing organization, e.g. 'AWS', 'Google'")
    date_obtained: Optional[str] = Field(None, description="Date earned in YYYY-MM format")
    expiry_date: Optional[str] = Field(None, description="Expiration date in YYYY-MM format; null if no expiry")
    credential_id: Optional[str] = Field(None, description="Certificate ID or verification code")


class ResumeSkill(BaseModel):
    name: str = Field(description="Skill name, e.g. 'Python', 'React', 'Docker'")
    category: str = Field(
        description="Skill category: 'language', 'framework', 'tool', 'cloud', 'database', 'soft_skill', or similar"
    )
    proficiency: Optional[str] = Field(
        None,
        description="Self-assessed proficiency level: 'expert', 'proficient', or 'familiar'"
    )


class ParsedResume(BaseModel):
    contact: ResumeContact = Field(description="Candidate contact information")
    summary: Optional[str] = Field(None, description="Professional summary or objective statement")
    education: list[ResumeEducation] = Field(default_factory=list, description="Educational background, most recent first")
    experience: list[ResumeExperience] = Field(default_factory=list, description="Work history, most recent first")
    projects: list[ResumeProject] = Field(default_factory=list, description="Personal or professional projects")
    certifications: list[ResumeCertification] = Field(default_factory=list, description="Professional certifications and licenses")
    skills: list[ResumeSkill] = Field(default_factory=list, description="Technical and soft skills")
    raw_text: str = Field(description="Original text extracted from the resume file, preserved for reference and re-parsing")
    parse_confidence: float = Field(
        description="Model confidence in parse quality, from 0.0 (very low) to 1.0 (very high)",
        ge=0.0,
        le=1.0,
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                    "contact": {
                        "name": "Alex Chen",
                        "email": "alex.chen@example.com",
                        "phone": "+1 (415) 555-0192",
                        "address": "San Francisco, CA",
                        "linkedin_url": "https://linkedin.com/in/alexchen",
                        "github_url": "https://github.com/alexchen",
                        "portfolio_url": "https://alexchen.dev",
                    },
                    "summary": (
                        "Software engineer with 5 years of experience building scalable "
                        "distributed systems and developer tooling. Passionate about "
                        "developer experience and open-source."
                    ),
                    "education": [
                        {
                            "institution": "University of California, Berkeley",
                            "degree": "Bachelor of Science",
                            "field_of_study": "Computer Science",
                            "start_date": "2015-08",
                            "end_date": "2019-05",
                            "gpa": 3.8,
                            "highlights": [
                                "Dean's List — 6 semesters",
                                "Teaching Assistant, CS 61B Data Structures",
                            ],
                        }
                    ],
                    "experience": [
                        {
                            "company": "Stripe",
                            "title": "Senior Software Engineer",
                            "location": "San Francisco, CA",
                            "start_date": "2022-03",
                            "end_date": None,
                            "is_current": True,
                            "bullets": [
                                "Led redesign of payment retry logic, reducing failed charge rate by 18%",
                                "Mentored 3 junior engineers through bi-weekly 1:1s and code reviews",
                                "Drove adoption of internal RPC framework across 6 teams",
                            ],
                            "technologies": ["Go", "Kafka", "PostgreSQL", "Kubernetes", "gRPC"],
                        },
                        {
                            "company": "Lyft",
                            "title": "Software Engineer",
                            "location": "San Francisco, CA",
                            "start_date": "2019-07",
                            "end_date": "2022-02",
                            "is_current": False,
                            "bullets": [
                                "Built real-time ETA prediction pipeline serving 2M requests/day",
                                "Reduced p99 API latency from 320ms to 95ms via query optimization",
                            ],
                            "technologies": ["Python", "Spark", "Redis", "MySQL", "Airflow"],
                        },
                    ],
                    "projects": [
                        {
                            "name": "pqlite",
                            "description": "Lightweight PostgreSQL query builder for Python with type-safe query construction",
                            "url": "https://github.com/alexchen/pqlite",
                            "technologies": ["Python", "PostgreSQL"],
                            "highlights": [
                                "1.2k GitHub stars",
                                "Published to PyPI with 8k monthly downloads",
                            ],
                        }
                    ],
                    "certifications": [
                        {
                            "name": "AWS Certified Solutions Architect – Associate",
                            "issuer": "Amazon Web Services",
                            "date_obtained": "2021-09",
                            "expiry_date": "2024-09",
                            "credential_id": "AWS-SAA-20210923-ACHEN",
                        }
                    ],
                    "skills": [
                        {"name": "Python", "category": "language", "proficiency": "expert"},
                        {"name": "Go", "category": "language", "proficiency": "proficient"},
                        {"name": "TypeScript", "category": "language", "proficiency": "familiar"},
                        {"name": "FastAPI", "category": "framework", "proficiency": "expert"},
                        {"name": "React", "category": "framework", "proficiency": "familiar"},
                        {"name": "Kubernetes", "category": "tool", "proficiency": "proficient"},
                        {"name": "Docker", "category": "tool", "proficiency": "expert"},
                        {"name": "PostgreSQL", "category": "database", "proficiency": "expert"},
                        {"name": "Redis", "category": "database", "proficiency": "proficient"},
                        {"name": "AWS", "category": "cloud", "proficiency": "proficient"},
                        {"name": "Technical mentorship", "category": "soft_skill", "proficiency": None},
                    ],
                    "raw_text": "Alex Chen\nalex.chen@example.com | +1 (415) 555-0192 ...",
                    "parse_confidence": 0.94,
            }
        }
    }

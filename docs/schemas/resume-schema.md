# Resume JSON Schema

Produced by `agent-service/app/models/resume.py` → `ParsedResume`.

## Example

```json
{
  "contact": {
    "name": "Alex Chen",
    "email": "alex.chen@example.com",
    "phone": "+1 (415) 555-0192",
    "address": "San Francisco, CA",
    "linkedin_url": "https://linkedin.com/in/alexchen",
    "github_url": "https://github.com/alexchen",
    "portfolio_url": "https://alexchen.dev"
  },
  "summary": "Software engineer with 5 years of experience building scalable distributed systems and developer tooling. Passionate about developer experience and open-source.",
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
        "Teaching Assistant, CS 61B Data Structures"
      ]
    }
  ],
  "experience": [
    {
      "company": "Stripe",
      "title": "Senior Software Engineer",
      "location": "San Francisco, CA",
      "start_date": "2022-03",
      "end_date": null,
      "is_current": true,
      "bullets": [
        "Led redesign of payment retry logic, reducing failed charge rate by 18%",
        "Mentored 3 junior engineers through bi-weekly 1:1s and code reviews",
        "Drove adoption of internal RPC framework across 6 teams"
      ],
      "technologies": ["Go", "Kafka", "PostgreSQL", "Kubernetes", "gRPC"]
    },
    {
      "company": "Lyft",
      "title": "Software Engineer",
      "location": "San Francisco, CA",
      "start_date": "2019-07",
      "end_date": "2022-02",
      "is_current": false,
      "bullets": [
        "Built real-time ETA prediction pipeline serving 2M requests/day",
        "Reduced p99 API latency from 320ms to 95ms via query optimization"
      ],
      "technologies": ["Python", "Spark", "Redis", "MySQL", "Airflow"]
    }
  ],
  "projects": [
    {
      "name": "pqlite",
      "description": "Lightweight PostgreSQL query builder for Python with type-safe query construction",
      "url": "https://github.com/alexchen/pqlite",
      "technologies": ["Python", "PostgreSQL"],
      "highlights": [
        "1.2k GitHub stars",
        "Published to PyPI with 8k monthly downloads"
      ]
    }
  ],
  "certifications": [
    {
      "name": "AWS Certified Solutions Architect – Associate",
      "issuer": "Amazon Web Services",
      "date_obtained": "2021-09",
      "expiry_date": "2024-09",
      "credential_id": "AWS-SAA-20210923-ACHEN"
    }
  ],
  "skills": [
    {"name": "Python",               "category": "language",   "proficiency": "expert"},
    {"name": "Go",                   "category": "language",   "proficiency": "proficient"},
    {"name": "TypeScript",           "category": "language",   "proficiency": "familiar"},
    {"name": "FastAPI",              "category": "framework",  "proficiency": "expert"},
    {"name": "React",                "category": "framework",  "proficiency": "familiar"},
    {"name": "Kubernetes",           "category": "tool",       "proficiency": "proficient"},
    {"name": "Docker",               "category": "tool",       "proficiency": "expert"},
    {"name": "PostgreSQL",           "category": "database",   "proficiency": "expert"},
    {"name": "Redis",                "category": "database",   "proficiency": "proficient"},
    {"name": "AWS",                  "category": "cloud",      "proficiency": "proficient"},
    {"name": "Technical mentorship", "category": "soft_skill", "proficiency": null}
  ],
  "raw_text": "Alex Chen\nalex.chen@example.com | +1 (415) 555-0192 ...",
  "parse_confidence": 0.94
}
```

## Field Reference

### `ParsedResume` (top-level)

| Field | Type | Required | Description |
|---|---|---|---|
| `contact` | `ResumeContact` | yes | Candidate contact information |
| `summary` | `string \| null` | no | Professional summary or objective statement |
| `education` | `ResumeEducation[]` | no | Educational background, most recent first |
| `experience` | `ResumeExperience[]` | no | Work history, most recent first |
| `projects` | `ResumeProject[]` | no | Personal or professional projects |
| `certifications` | `ResumeCertification[]` | no | Professional certifications and licenses |
| `skills` | `ResumeSkill[]` | no | Technical and soft skills |
| `raw_text` | `string` | yes | Original text extracted from the resume file |
| `parse_confidence` | `float [0.0–1.0]` | yes | Model confidence in parse quality |

### `ResumeContact`

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string \| null` | no | Full name of the candidate |
| `email` | `string \| null` | no | Primary email address |
| `phone` | `string \| null` | no | Phone number in any format |
| `address` | `string \| null` | no | City, state, or full mailing address |
| `linkedin_url` | `string \| null` | no | LinkedIn profile URL |
| `github_url` | `string \| null` | no | GitHub profile URL |
| `portfolio_url` | `string \| null` | no | Personal website or portfolio URL |

### `ResumeEducation`

| Field | Type | Required | Description |
|---|---|---|---|
| `institution` | `string` | yes | Name of the school or university |
| `degree` | `string` | yes | Degree type, e.g. `"Bachelor of Science"` |
| `field_of_study` | `string` | yes | Major or area of study |
| `start_date` | `string \| null` | no | Start date in `YYYY-MM` format |
| `end_date` | `string \| null` | no | End date in `YYYY-MM` format; `null` if ongoing |
| `gpa` | `float [0.0–4.0] \| null` | no | GPA on a 4.0 scale |
| `highlights` | `string[]` | no | Notable awards, honors, or activities |

### `ResumeExperience`

| Field | Type | Required | Description |
|---|---|---|---|
| `company` | `string` | yes | Employer or organization name |
| `title` | `string` | yes | Job title or role |
| `location` | `string \| null` | no | City, state, or `"Remote"` |
| `start_date` | `string \| null` | no | Start date in `YYYY-MM` format |
| `end_date` | `string \| null` | no | End date in `YYYY-MM` format; `null` if current |
| `is_current` | `boolean` | no (default: `false`) | `true` if this is the candidate's current role |
| `bullets` | `string[]` | no | Achievement and responsibility bullet points |
| `technologies` | `string[]` | no | Technologies, languages, or tools used in this role |

### `ResumeProject`

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | yes | Project name or title |
| `description` | `string` | yes | Brief description of the project and its purpose |
| `url` | `string \| null` | no | Link to live project, repo, or demo |
| `technologies` | `string[]` | no | Technologies used in the project |
| `highlights` | `string[]` | no | Key accomplishments or features |

### `ResumeCertification`

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | yes | Full certification name |
| `issuer` | `string` | yes | Issuing organization, e.g. `"AWS"`, `"Google"` |
| `date_obtained` | `string \| null` | no | Date earned in `YYYY-MM` format |
| `expiry_date` | `string \| null` | no | Expiration date in `YYYY-MM` format; `null` if no expiry |
| `credential_id` | `string \| null` | no | Certificate ID or verification code |

### `ResumeSkill`

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | yes | Skill name, e.g. `"Python"`, `"React"`, `"Docker"` |
| `category` | `string` | yes | `"language"`, `"framework"`, `"tool"`, `"cloud"`, `"database"`, `"soft_skill"`, or similar |
| `proficiency` | `string \| null` | no | `"expert"`, `"proficient"`, or `"familiar"` |

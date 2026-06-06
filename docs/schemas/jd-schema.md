# Job Description JSON Schema

Produced by `agent-service/app/models/job_description.py` → `ParsedJobDescription`.

## Example

```json
{
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
    "Mentor junior and mid-level engineers within the team"
  ],
  "skills": [
    {"name": "Python",                  "is_required": true,  "category": "language"},
    {"name": "Scala",                   "is_required": false, "category": "language"},
    {"name": "Java",                    "is_required": false, "category": "language"},
    {"name": "Apache Spark",            "is_required": true,  "category": "framework"},
    {"name": "gRPC",                    "is_required": true,  "category": "tool"},
    {"name": "Kubernetes",              "is_required": true,  "category": "tool"},
    {"name": "Docker",                  "is_required": true,  "category": "tool"},
    {"name": "AWS",                     "is_required": true,  "category": "cloud"},
    {"name": "PostgreSQL",              "is_required": true,  "category": "database"},
    {"name": "Delta Lake",              "is_required": false, "category": "framework"},
    {"name": "Distributed systems design", "is_required": true, "category": "domain"},
    {"name": "Technical communication", "is_required": true,  "category": "soft_skill"}
  ],
  "qualifications": [
    "Bachelor's or Master's degree in Computer Science, Engineering, or equivalent practical experience",
    "5+ years of professional software engineering experience",
    "Demonstrated experience designing high-throughput, low-latency distributed systems",
    "Experience with cloud-native infrastructure on AWS, GCP, or Azure"
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
    "Delta Lake"
  ],
  "industry": "data and AI infrastructure",
  "raw_text": "Senior Backend Engineer\nDatabricks | San Francisco, CA (Hybrid)\n$180,000 – $240,000 ...",
  "source_url": "https://databricks.com/company/careers/open-positions/senior-backend-engineer-12345",
  "parse_confidence": 0.91
}
```

## Field Reference

### `ParsedJobDescription` (top-level)

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | `string` | yes | Job title as listed in the posting |
| `company` | `string \| null` | no | Company or organization name |
| `location` | `string \| null` | no | Office location, city, or `"Remote"` |
| `remote_type` | `string \| null` | no | Work arrangement: `"remote"`, `"hybrid"`, or `"onsite"` |
| `employment_type` | `string \| null` | no | `"full-time"`, `"part-time"`, `"contract"`, or `"intern"` |
| `min_years_experience` | `integer ≥ 0 \| null` | no | Minimum years of experience required |
| `max_years_experience` | `integer ≥ 0 \| null` | no | Upper bound of an experience range |
| `salary_min` | `integer ≥ 0 \| null` | no | Minimum annual salary in `salary_currency` units |
| `salary_max` | `integer ≥ 0 \| null` | no | Maximum annual salary in `salary_currency` units |
| `salary_currency` | `string \| null` | no | ISO 4217 currency code, e.g. `"USD"`, `"EUR"`, `"GBP"` |
| `responsibilities` | `string[]` | no | Day-to-day duties listed in the posting |
| `skills` | `JDSkillRequirement[]` | no | Required and preferred skills |
| `qualifications` | `string[]` | no | Education requirements, certifications, and formal qualifications |
| `keywords` | `string[]` | no | ATS-relevant terms extracted for resume matching |
| `industry` | `string \| null` | no | Industry or domain sector, e.g. `"fintech"`, `"healthcare"` |
| `raw_text` | `string` | yes | Original job description text preserved for reference |
| `source_url` | `string \| null` | no | URL of the original job posting |
| `parse_confidence` | `float [0.0–1.0]` | yes | Model confidence in parse quality |

### `JDSkillRequirement`

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | yes | Skill name, e.g. `"Python"`, `"Kubernetes"`, `"System Design"` |
| `is_required` | `boolean` | yes | `true` if required; `false` if preferred or nice-to-have |
| `category` | `string` | yes | `"language"`, `"framework"`, `"tool"`, `"cloud"`, `"database"`, `"domain"`, `"soft_skill"`, or similar |

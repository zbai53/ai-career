#!/usr/bin/env python3
"""
Manual integration test script — makes real Anthropic API calls.

Usage:
    python tests/test_real_data.py                  # JD tests only
    python tests/test_real_data.py resume.pdf        # JD + resume tests
"""

import sys
import os

# Allow running from the agent-service/ root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from app.agents.resume_agent import ResumeAgent
from app.agents.jd_agent import JDAgent


# ---------------------------------------------------------------------------
# JD test cases (5 diverse roles)
# ---------------------------------------------------------------------------

JD_CASES = [
    (
        "Backend Engineer (Java/Spring Boot)",
        """\
Backend Engineer — Fintech Platform
Company: ClearPay Inc. | Location: Austin, TX (Hybrid) | Full-time

About the role:
We are looking for a Backend Engineer to join our payments infrastructure team.
You will design, build, and maintain high-throughput microservices that process
millions of transactions daily.

Requirements:
- 3+ years of professional software engineering experience
- Strong proficiency in Java 17+ and Spring Boot (required)
- Experience with relational databases — PostgreSQL preferred (required)
- Familiarity with message queues: Kafka or RabbitMQ (required)
- Experience with Docker and Kubernetes (required)
- AWS cloud experience (preferred)
- Experience with gRPC or REST API design (required)

Nice to have:
- Scala or Kotlin experience
- Financial domain knowledge (PCI-DSS, PSD2)

Compensation: $140,000 – $175,000 USD
""",
    ),
    (
        "Frontend Developer (React/TypeScript)",
        """\
Frontend Developer — Consumer Product
Company: Luminary Labs | Location: Remote (US) | Full-time

We're building the next generation of personal finance tools and need a frontend
engineer who cares deeply about user experience and performance.

What you'll do:
- Build responsive, accessible UIs using React and TypeScript
- Collaborate with designers using Figma specifications
- Write comprehensive unit and integration tests (Jest, React Testing Library)
- Optimise Core Web Vitals and bundle size

Requirements:
- 2+ years of frontend engineering experience (required)
- Expert-level React and TypeScript (required)
- CSS-in-JS or Tailwind CSS (required)
- REST and GraphQL API integration (required)
- Git and GitHub workflow (required)

Preferred:
- Next.js or Remix experience
- Experience with data visualisation libraries (D3.js, Recharts)
- Storybook component documentation

Salary: $110,000 – $145,000
""",
    ),
    (
        "Data Scientist (Python/ML, PhD preferred)",
        """\
Senior Data Scientist — Recommendations
Company: ShopStream | Location: San Francisco, CA | Full-time

We are seeking a Senior Data Scientist to lead development of our personalisation
and recommendation systems. You will work on models that serve 50M+ daily active users.

Minimum Qualifications:
- Master's degree in Statistics, Computer Science, Mathematics, or related field (required)
- 4+ years of industry data science experience (required)
- Proficiency in Python and the ML stack: scikit-learn, PyTorch or TensorFlow (required)
- Experience with large-scale data processing using Spark or similar (required)
- Strong SQL skills for feature engineering and analysis (required)
- Experience deploying models to production (required)

Preferred:
- PhD in a quantitative field
- Experience with recommendation systems (collaborative filtering, matrix factorisation)
- A/B testing and experimentation platform experience
- Familiarity with MLflow or similar experiment tracking tools

Compensation: $160,000 – $210,000 + equity
""",
    ),
    (
        "DevOps Engineer (AWS/Kubernetes/Terraform)",
        """\
DevOps / Platform Engineer
Company: Nexora Cloud | Location: Remote (Global) | Full-time or Contract

Nexora Cloud is looking for a DevOps engineer to own our cloud infrastructure and
developer platform. You will work closely with engineering teams to improve reliability,
deployment velocity, and cost efficiency.

Required Skills:
- Deep experience with AWS (EC2, EKS, RDS, S3, IAM, VPC) — required
- Infrastructure-as-code using Terraform (required)
- Kubernetes administration — cluster setup, scaling, networking (required)
- CI/CD pipelines: GitHub Actions or Jenkins (required)
- Monitoring and observability: Prometheus, Grafana, or Datadog (required)
- Linux system administration (required)

Preferred:
- Experience with service mesh (Istio or Linkerd)
- Helm chart authoring
- Security compliance (SOC 2, ISO 27001)
- Python or Go scripting for automation

Salary: $130,000 – $180,000 (full-time) or $90–$120/hr (contract)
""",
    ),
    (
        "Junior Full Stack Developer (entry level)",
        """\
Junior Full Stack Developer
Company: Brightside Digital | Location: Chicago, IL (Onsite) | Full-time

Are you a recent grad or self-taught developer looking to launch your career?
Brightside Digital builds web apps for small businesses and nonprofits.
We care more about attitude and fundamentals than years of experience.

What we're looking for:
- Solid understanding of HTML, CSS, and JavaScript (required)
- Familiarity with a backend language — Node.js, Python, or PHP acceptable (required)
- Basic experience with any SQL database (required)
- Ability to use Git for version control (required)
- Good communication skills and eagerness to learn (required)

Bonus points:
- Experience with React or Vue.js
- Any exposure to cloud hosting (AWS, GCP, or even Heroku)
- Portfolio of personal or open-source projects

Salary: $55,000 – $75,000
No degree requirement. No minimum years of experience.
""",
    ),
]


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

def test_resume_parse(file_path: str) -> bool:
    print(f"\n{'='*60}")
    print(f"RESUME TEST: {file_path}")
    print("="*60)
    try:
        agent = ResumeAgent()
        result = agent.parse(file_path)
        print(f"  Name:              {result.contact.name or '(not found)'}")
        print(f"  Email:             {result.contact.email or '(not found)'}")
        print(f"  Education count:   {len(result.education)}")
        print(f"  Experience count:  {len(result.experience)}")
        print(f"  Project count:     {len(result.projects)}")
        print(f"  Skills count:      {len(result.skills)}")
        print(f"  Parse confidence:  {result.parse_confidence:.2f}")
        print("  RESULT: PASS")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        print("  RESULT: FAIL")
        return False


def test_jd_parse(text: str, label: str) -> bool:
    print(f"\n{'='*60}")
    print(f"JD TEST: {label}")
    print("="*60)
    try:
        agent = JDAgent()
        result = agent.parse_text(text)
        required_skills = [s for s in result.skills if s.is_required]
        preferred_skills = [s for s in result.skills if not s.is_required]
        print(f"  Title:                  {result.title}")
        print(f"  Company:                {result.company or '(not found)'}")
        print(f"  Remote type:            {result.remote_type or '(not specified)'}")
        print(f"  Required skills count:  {len(required_skills)}")
        print(f"  Preferred skills count: {len(preferred_skills)}")
        print(f"  Keywords count:         {len(result.keywords)}")
        print(f"  Parse confidence:       {result.parse_confidence:.2f}")
        if required_skills:
            print(f"  Required skills:        {', '.join(s.name for s in required_skills[:5])}"
                  + (" ..." if len(required_skills) > 5 else ""))
        print("  RESULT: PASS")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        print("  RESULT: FAIL")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    resume_path = sys.argv[1] if len(sys.argv) > 1 else None

    results: list[bool] = []

    if resume_path:
        results.append(test_resume_parse(resume_path))

    for label, text in JD_CASES:
        results.append(test_jd_parse(text, label))

    passed = sum(results)
    total = len(results)

    print(f"\n{'='*60}")
    print(f"FINAL SUMMARY: {passed}/{total} passed")
    print("="*60)

    sys.exit(0 if passed == total else 1)

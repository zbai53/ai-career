#!/usr/bin/env bash
# demo-data-setup.sh
#
# Creates the data needed for README screenshots.
# Run from the repo root:  bash docs/screenshots/demo-data-setup.sh
#
# Prerequisites:
#   - All services running (docker compose up, or each service started manually)
#   - curl and jq installed
#   - A resume PDF at RESUME_FILE (default: docs/screenshots/sample-resume.pdf)
#
# The script prints a URL for each screenshot at the end.

set -euo pipefail

BACKEND="http://localhost:8080"
AGENT="http://localhost:8001"
RESUME_FILE="${RESUME_FILE:-docs/screenshots/sample-resume.pdf}"
NUM_QUESTIONS=3   # small set so the script finishes quickly

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $*"; }
info() { echo -e "${CYAN}▸${NC} $*"; }
die()  { echo -e "${RED}✗ ERROR:${NC} $*" >&2; exit 1; }

# ─────────────────────────────────────────────
# 0. Preflight checks
# ─────────────────────────────────────────────

info "Checking services..."

curl -sf "$BACKEND/health" > /dev/null \
  || die "Backend is not running at $BACKEND. Start it first."
ok "Backend is up ($BACKEND)"

curl -sf "$AGENT/health" > /dev/null \
  || die "Agent service is not running at $AGENT. Start it first."
ok "Agent service is up ($AGENT)"

[[ -f "$RESUME_FILE" ]] \
  || die "Resume file not found: $RESUME_FILE\n\nSet RESUME_FILE=/path/to/your.pdf or place a PDF at docs/screenshots/sample-resume.pdf"
ok "Resume file found: $RESUME_FILE"

command -v jq > /dev/null \
  || die "'jq' is required. Install: brew install jq"

echo ""

# ─────────────────────────────────────────────
# 1. Parse resume
# ─────────────────────────────────────────────

info "Parsing resume..."

RESUME_RESP=$(curl -sf -X POST "$BACKEND/api/resumes/parse" \
  -F "file=@$RESUME_FILE") \
  || die "Resume parse failed. Check backend logs."

RESUME_ID=$(echo "$RESUME_RESP" | jq -r '.id')
RESUME_NAME=$(echo "$RESUME_RESP" | jq -r '.name // .contact.name // "Unknown"')
RESUME_SKILLS=$(echo "$RESUME_RESP" | jq -r '[.skills[]? | .name // .] | join(", ")' 2>/dev/null || echo "—")

ok "Resume parsed — id=$RESUME_ID  name=$RESUME_NAME"
echo "   Skills: $RESUME_SKILLS"
echo ""

# ─────────────────────────────────────────────
# 2. Parse job description
# ─────────────────────────────────────────────

info "Parsing job description..."

JD_TEXT=$(cat <<'JDEOF'
Senior Backend Engineer — FinTech Platform

We are looking for a Senior Backend Engineer to join our core platform team.

Responsibilities:
- Design and build high-throughput REST APIs using Java and Spring Boot
- Own the microservices architecture for our payments processing pipeline
- Collaborate with frontend teams on API contracts and data models
- Mentor junior engineers and conduct technical interviews
- Drive adoption of Kafka for async event streaming

Required Skills:
- 5+ years of experience with Java and Spring Boot
- Strong understanding of distributed systems and microservices
- Experience with PostgreSQL or other relational databases
- Proficiency with Docker and Kubernetes
- Familiarity with message queues (Kafka, RabbitMQ, or SQS)

Nice to Have:
- Experience with AWS (ECS, RDS, S3)
- Knowledge of Redis for caching
- Background in financial services or payments

We offer competitive compensation, flexible remote work, and strong growth opportunities.
JDEOF
)

JD_RESP=$(curl -sf -X POST "$BACKEND/api/jds/parse" \
  -H "Content-Type: application/json" \
  -d "{\"text\": $(echo "$JD_TEXT" | jq -Rs .)}") \
  || die "JD parse failed. Check backend logs."

JD_ID=$(echo "$JD_RESP" | jq -r '.id')
JD_TITLE=$(echo "$JD_RESP" | jq -r '.title // "Unknown"')
JD_SKILLS=$(echo "$JD_RESP" | jq -r '[.required_skills[]?] | join(", ")' 2>/dev/null || echo "—")

ok "JD parsed — id=$JD_ID  title=$JD_TITLE"
echo "   Required skills: $JD_SKILLS"
echo ""

# ─────────────────────────────────────────────
# 3. Run match
# ─────────────────────────────────────────────

info "Running match (resumeId=$RESUME_ID, jdId=$JD_ID)..."

MATCH_RESP=$(curl -sf -X POST "$BACKEND/api/match" \
  -H "Content-Type: application/json" \
  -d "{\"resumeId\": $RESUME_ID, \"jdId\": $JD_ID}") \
  || die "Match failed. Check backend and agent-service logs."

MATCH_ID=$(echo "$MATCH_RESP" | jq -r '.id')
OVERALL_SCORE=$(echo "$MATCH_RESP" | jq -r '.overallScore // .overall_score // "?"')
SKILL_SCORE=$(echo "$MATCH_RESP"   | jq -r '.skillScore   // .skill_score   // "?"')

ok "Match complete — id=$MATCH_ID  overall=$OVERALL_SCORE  skill=$SKILL_SCORE"
echo ""

# ─────────────────────────────────────────────
# 4. Trigger rewrite (always, for screenshot purposes)
# ─────────────────────────────────────────────

info "Running rewrite (resumeId=$RESUME_ID, jdId=$JD_ID, matchResultId=$MATCH_ID)..."
info "This may take up to 60 seconds..."

REWRITE_RESP=$(curl -sf --max-time 90 -X POST "$BACKEND/api/rewrite" \
  -H "Content-Type: application/json" \
  -d "{\"resumeId\": $RESUME_ID, \"jdId\": $JD_ID, \"matchResultId\": $MATCH_ID}") \
  || die "Rewrite failed. Check backend and agent-service logs."

REWRITE_ID=$(echo "$REWRITE_RESP"      | jq -r '.id')
FIDELITY=$(echo "$REWRITE_RESP"        | jq -r '.fidelity_status // "unknown"')
ATTEMPTS=$(echo "$REWRITE_RESP"        | jq -r '.rewrite_attempts // 1')
KEYWORDS=$(echo "$REWRITE_RESP"        | jq -r '[.keywords_injected[]?] | join(", ")' 2>/dev/null || echo "—")

ok "Rewrite complete — id=$REWRITE_ID  fidelity=$FIDELITY  attempts=$ATTEMPTS"
echo "   Keywords injected: $KEYWORDS"
echo ""

# ─────────────────────────────────────────────
# 5. Start interview (small session for screenshots)
# ─────────────────────────────────────────────

info "Starting interview session (resumeId=$RESUME_ID, jdId=$JD_ID, questions=$NUM_QUESTIONS)..."

START_RESP=$(curl -sf -X POST "$BACKEND/api/interviews/start" \
  -H "Content-Type: application/json" \
  -d "{\"resumeId\": $RESUME_ID, \"jdId\": $JD_ID, \"numQuestions\": $NUM_QUESTIONS}") \
  || die "Interview start failed. Check backend and agent-service logs."

SESSION_ID=$(echo "$START_RESP"  | jq -r '.session_id')
DB_ID=$(echo "$START_RESP"       | jq -r '.db_id')
FIRST_Q=$(echo "$START_RESP"     | jq -r '.question')

ok "Interview started — session_id=$SESSION_ID  db_id=$DB_ID"
echo "   Q1: $FIRST_Q"
echo ""

# ─────────────────────────────────────────────
# 6. Answer question 1
# ─────────────────────────────────────────────

info "Answering question 1..."

ANSWER_1="In my previous role as a backend engineer at a fintech startup, I was responsible for designing our payments processing microservice using Java and Spring Boot. When we hit scaling issues at 10,000 transactions per day, I led the migration from a monolithic architecture to event-driven design using Kafka. I personally wrote the consumer and producer logic, coordinated with the DevOps team to deploy on Kubernetes, and reduced latency by 40%. The service now handles over 50,000 transactions per day with 99.9% uptime."

A1_RESP=$(curl -sf -X POST "$BACKEND/api/interviews/$SESSION_ID/answer" \
  -H "Content-Type: application/json" \
  -d "{\"answer\": $(echo "$ANSWER_1" | jq -Rs .)}") \
  || die "Answer 1 submission failed."

NEXT_ACTION=$(echo "$A1_RESP" | jq -r '.next_action // "unknown"')
IS_COMPLETE=$(echo "$A1_RESP" | jq -r '.is_complete // false')

ok "Answer 1 submitted — next_action=$NEXT_ACTION"

if [[ "$IS_COMPLETE" == "true" ]]; then
  info "Session already complete after Q1 (only 1 question was generated)."
else
  # If there's a follow-up, answer it too so we have visible chat history
  if [[ "$NEXT_ACTION" == "follow_up" ]]; then
    info "Follow-up detected — answering it..."
    FOLLOW_UP_Q=$(echo "$A1_RESP" | jq -r '.next_content // ""')
    echo "   Follow-up: $FOLLOW_UP_Q"

    A_FU_RESP=$(curl -sf -X POST "$BACKEND/api/interviews/$SESSION_ID/answer" \
      -H "Content-Type: application/json" \
      -d '{"answer": "We used Prometheus and Grafana for monitoring, plus custom CloudWatch dashboards for AWS-specific metrics. I set up alerts for p99 latency thresholds so the on-call team got paged before customers noticed issues."}') \
      || die "Follow-up answer failed."

    NEXT_ACTION=$(echo "$A_FU_RESP" | jq -r '.next_action // "unknown"')
    IS_COMPLETE=$(echo "$A_FU_RESP" | jq -r '.is_complete // false')
    ok "Follow-up answered — next_action=$NEXT_ACTION"
  fi

  # Answer question 2 if we're not done
  if [[ "$IS_COMPLETE" != "true" && "$NEXT_ACTION" != "done" ]]; then
    Q2=$(echo "$A1_RESP" | jq -r '.next_content // "Tell me about a challenging system design decision you made."')
    echo ""
    info "Answering question 2..."
    echo "   Q2: $Q2"

    A2_RESP=$(curl -sf -X POST "$BACKEND/api/interviews/$SESSION_ID/answer" \
      -H "Content-Type: application/json" \
      -d '{"answer": "The hardest decision was choosing between a relational and NoSQL database for our user profile service. The profiles had deeply nested preferences and varied structure, which pointed toward MongoDB. But our reporting team needed complex joins across user data. I ran a spike with both approaches, benchmarked queries relevant to our top-10 endpoints, and ultimately chose PostgreSQL with a JSONB column for flexible attributes. This gave us join capability where we needed it while still handling the variable schema. Eighteen months later that decision has held up well."}') \
      || die "Answer 2 submission failed."

    IS_COMPLETE=$(echo "$A2_RESP" | jq -r '.is_complete // false')
    NEXT_ACTION=$(echo "$A2_RESP" | jq -r '.next_action // "unknown"')
    ok "Answer 2 submitted — next_action=$NEXT_ACTION"
  fi
fi

echo ""

# ─────────────────────────────────────────────
# 7. End interview + get review
# ─────────────────────────────────────────────

info "Ending interview and generating coach review..."

END_RESP=$(curl -sf --max-time 60 -X POST "$BACKEND/api/interviews/$SESSION_ID/end") \
  || die "Interview end/review failed."

AVG_SCORE=$(echo "$END_RESP" | jq -r '.average_scores.overall // "?"')
READINESS=$(echo "$END_RESP" | jq -r '.coach_review.readiness // "pending"' 2>/dev/null || echo "pending")

ok "Interview complete — avg_score=$AVG_SCORE  readiness=$READINESS"
echo ""

# ─────────────────────────────────────────────
# 8. Print summary + screenshot URLs
# ─────────────────────────────────────────────

APP="http://localhost:3000"

echo ""
echo -e "${BOLD}════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Demo data ready. IDs and screenshot URLs:${NC}"
echo -e "${BOLD}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Resume ID:    ${CYAN}$RESUME_ID${NC}"
echo -e "  JD ID:        ${CYAN}$JD_ID${NC}"
echo -e "  Match ID:     ${CYAN}$MATCH_ID${NC}    (overall score: $OVERALL_SCORE)"
echo -e "  Rewrite ID:   ${CYAN}$REWRITE_ID${NC}   (fidelity: $FIDELITY)"
echo -e "  Session ID:   ${CYAN}$SESSION_ID${NC}"
echo -e "  DB Session:   ${CYAN}$DB_ID${NC}"
echo ""
echo -e "${BOLD}  Screenshot URLs (open in Chrome at 1280×800):${NC}"
echo ""
echo -e "  a. dashboard.png   →  ${CYAN}$APP/${NC}"
echo -e "  b. upload.png      →  ${CYAN}$APP/upload${NC}  (upload another resume to show parsed result)"
echo -e "  c. jd-input.png    →  ${CYAN}$APP/jd${NC}      (paste JD text, click Parse)"
echo -e "  d. match.png       →  ${CYAN}$APP/match/$MATCH_ID${NC}"
echo -e "  e. rewrite.png     →  ${CYAN}$APP/rewrite/$REWRITE_ID${NC}"
echo -e "  f. interview.png   →  ${CYAN}$APP/interview/$SESSION_ID${NC}"
echo -e "  g. review.png      →  ${CYAN}$APP/review/$SESSION_ID${NC}"
echo -e "  h. workflow.png    →  ${CYAN}$APP/workflow${NC}"
echo ""
echo -e "  See ${BOLD}docs/screenshots/capture-guide.md${NC} for capture instructions."
echo ""

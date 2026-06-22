"""
Full pipeline integration tests for run_full_pipeline().

All agent calls are mocked — no real Anthropic API calls are made.
Each test uses a unique thread_id to keep the module-level MemorySaver
checkpointer namespaces isolated between runs.

Flow under test (happy path with rewrite):
    parse_resume → parse_jd → match → rewrite → match (re-score)
    → interview (placeholder) → review → END
"""

import uuid
from unittest.mock import MagicMock, patch

from app.graph.workflow import run_full_pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_thread() -> str:
    return f"test-full-pipeline-{uuid.uuid4()}"


def _fake_agent_run(agent_name: str) -> dict:
    return {
        "agent_name":     agent_name,
        "input_summary":  "test input",
        "output_summary": "test output",
        "status":         "success",
        "duration_ms":    100,
        "token_count":    50,
        "model_name":     "claude-haiku-4-5-20251001",
        "error_message":  None,
        "created_at":     "2026-06-21T00:00:00+00:00",
    }


def _fake_resume_model() -> MagicMock:
    m = MagicMock()
    m.raw_text = "Jane Doe  jane@example.com\nBackend Developer at Initech"
    m.model_dump.return_value = {
        "contact": {"name": "Jane Doe", "email": "jane@example.com"},
        "skills": [],
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
        "raw_text": m.raw_text,
        "parse_confidence": 0.9,
    }
    return m


def _fake_jd_model() -> MagicMock:
    m = MagicMock()
    m.model_dump.return_value = {
        "title": "Senior Backend Engineer",
        "company": "CloudScale",
        "skills": [],
        "keywords": ["Java", "microservices", "PostgreSQL"],
        "raw_text": "Senior Backend Engineer — CloudScale",
        "parse_confidence": 0.92,
    }
    return m


def _fake_match_model(overall_score: float = 80.0) -> MagicMock:
    m = MagicMock()
    m.model_dump.return_value = {
        "overall_score":             overall_score,
        "skill_score":               75.0,
        "experience_score":          80.0,
        "keyword_score":             85.0,
        "missing_required_skills":   [],
        "missing_preferred_skills":  [],
        "improvement_suggestions":   [],
        "interview_focus_areas":     [],
        "overall_assessment":        "Solid match.",
        "gap_analysis": {
            "missing_required_skills":  [],
            "missing_preferred_skills": [],
            "improvement_suggestions":  [],
        },
    }
    return m


def _fake_rewrite_model(
    fidelity_score: float = 0.92,
    rewrite_attempts: int = 1,
) -> MagicMock:
    passed = fidelity_score >= 0.90
    if fidelity_score >= 0.90:
        fidelity_status = "passed"
    elif fidelity_score >= 0.80:
        fidelity_status = "warning"
    else:
        fidelity_status = "failed"

    m = MagicMock()
    m.model_dump.return_value = {
        "experiences": [
            {
                "company": "Initech",
                "title": "Backend Developer",
                "original_bullets": ["Built REST API using Java"],
                "rewritten_bullets": [
                    {
                        "original": "Built REST API using Java",
                        "rewritten": (
                            "Engineered scalable REST APIs in Java to support "
                            "distributed service communication."
                        ),
                        "changes_made": ["Stronger verb", "Added distributed keyword"],
                    }
                ],
            }
        ],
        "keywords_injected":         ["distributed"],
        "overall_improvement_summary": "Improved keyword coverage and action verbs.",
        "rewrite_confidence":        0.88,
        "fidelity_report": {
            "fidelity_score":          fidelity_score,
            "flags":                   [],
            "total_original_entities": 3,
            "total_rewritten_entities": 3,
            "new_entities_found":      0,
            "passed":                  passed,
            "threshold":               0.85,
        },
        "rewrite_attempts":  rewrite_attempts,
        "fidelity_status":   fidelity_status,
        "improvement_metrics": None,
    }
    return m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPipelineLowScoreTriggersRewrite:
    """Score < 70 on first match → rewrite runs → re-score → completes."""

    def test_pipeline_low_score_triggers_rewrite(self) -> None:
        resume_run  = _fake_agent_run("resume_agent")
        jd_run      = _fake_agent_run("jd_agent")
        match_run   = _fake_agent_run("match_agent")
        rewrite_run = _fake_agent_run("rewrite_agent")

        with patch("app.graph.workflow.ResumeAgent")  as MR, \
             patch("app.graph.workflow.JDAgent")       as MJ, \
             patch("app.graph.workflow.MatchAgent")    as MM, \
             patch("app.graph.workflow.RewriteAgent")  as MW:

            MR.return_value.parse.return_value   = (_fake_resume_model(), resume_run)
            MJ.return_value.parse.return_value   = (_fake_jd_model(),     jd_run)
            MM.return_value.match.side_effect    = [
                (_fake_match_model(50.0), match_run),   # first call  → low score → rewrite
                (_fake_match_model(75.0), match_run),   # second call → high score → interview
            ]
            MW.return_value.rewrite.return_value = (_fake_rewrite_model(0.92, 1), rewrite_run)

            final = run_full_pipeline(
                resume_file_path="/fake/resume.pdf",
                jd_text="We are hiring a senior backend engineer.",
                thread_id=_unique_thread(),
            )

        # Rewrite ran exactly once
        assert final["rewrite_count"] == 1
        MW.return_value.rewrite.assert_called_once()

        # Final match_result reflects the re-scored result (75.0)
        assert final["match_result"]["overall_score"] == 75.0

        # Workflow completed without error
        assert final["workflow_status"] == "completed"
        assert final["error"] is None

        # Fidelity score preserved from rewrite_result
        fidelity = final["rewrite_result"]["fidelity_report"]["fidelity_score"]
        assert fidelity == 0.92

        # agent_runs: resume_agent, jd_agent, match_agent(50), rewrite_agent, match_agent(75)
        agent_names = [r["agent_name"] for r in final["agent_runs"]]
        assert agent_names == [
            "resume_agent",
            "jd_agent",
            "match_agent",
            "rewrite_agent",
            "match_agent",
        ]


class TestPipelineHighScoreSkipsRewrite:
    """Score >= 70 on first match → routes directly to interview, no rewrite."""

    def test_pipeline_high_score_skips_rewrite(self) -> None:
        resume_run = _fake_agent_run("resume_agent")
        jd_run     = _fake_agent_run("jd_agent")
        match_run  = _fake_agent_run("match_agent")

        with patch("app.graph.workflow.ResumeAgent")  as MR, \
             patch("app.graph.workflow.JDAgent")       as MJ, \
             patch("app.graph.workflow.MatchAgent")    as MM, \
             patch("app.graph.workflow.RewriteAgent")  as MW:

            MR.return_value.parse.return_value = (_fake_resume_model(), resume_run)
            MJ.return_value.parse.return_value = (_fake_jd_model(),     jd_run)
            MM.return_value.match.return_value = (_fake_match_model(85.0), match_run)

            final = run_full_pipeline(
                resume_file_path="/fake/resume.pdf",
                jd_text="We are hiring a senior backend engineer.",
                thread_id=_unique_thread(),
            )

        # No rewrite ran
        assert final["rewrite_count"] == 0
        assert final["rewrite_result"] is None
        MW.return_value.rewrite.assert_not_called()

        # Routed to interview placeholder; review_node runs last → step is "reviewing"
        assert final["current_step"] in {"interviewing", "reviewing"}
        assert final["workflow_status"] == "completed"
        assert final["error"] is None

        # Only 3 agent_runs: no rewrite_agent entry
        agent_names = [r["agent_name"] for r in final["agent_runs"]]
        assert "rewrite_agent" not in agent_names
        assert "resume_agent" in agent_names
        assert "jd_agent"     in agent_names
        assert "match_agent"  in agent_names


class TestPipelineRewriteLoopMax2:
    """Score never improves → rewrite runs exactly 2 times (max), then routes to interview."""

    def test_pipeline_rewrite_loop_max_2(self) -> None:
        resume_run  = _fake_agent_run("resume_agent")
        jd_run      = _fake_agent_run("jd_agent")
        match_run   = _fake_agent_run("match_agent")
        rewrite_run = _fake_agent_run("rewrite_agent")

        with patch("app.graph.workflow.ResumeAgent")  as MR, \
             patch("app.graph.workflow.JDAgent")       as MJ, \
             patch("app.graph.workflow.MatchAgent")    as MM, \
             patch("app.graph.workflow.RewriteAgent")  as MW:

            MR.return_value.parse.return_value   = (_fake_resume_model(), resume_run)
            MJ.return_value.parse.return_value   = (_fake_jd_model(),     jd_run)
            # Match always returns low score — never triggers the "interview" branch
            MM.return_value.match.return_value   = (_fake_match_model(40.0), match_run)
            MW.return_value.rewrite.return_value = (_fake_rewrite_model(), rewrite_run)

            final = run_full_pipeline(
                resume_file_path="/fake/resume.pdf",
                jd_text="We are hiring a senior backend engineer.",
                thread_id=_unique_thread(),
            )

        # Loop capped at 2
        assert final["rewrite_count"] == 2
        assert MW.return_value.rewrite.call_count == 2

        # Despite low score, routed to interview after hitting the cap
        assert final["current_step"] in {"interviewing", "reviewing"}
        assert final["workflow_status"] == "completed"
        assert final["error"] is None


class TestPipelineRewriteFidelityFailAndRetry:
    """
    The RewriteAgent internally makes 2 Claude calls (first fails fidelity at 0.70,
    second passes at 0.95).  The final RewriteResult must carry rewrite_attempts=2.
    """

    def test_pipeline_rewrite_fidelity_fail_and_retry(self) -> None:
        resume_run  = _fake_agent_run("resume_agent")
        jd_run      = _fake_agent_run("jd_agent")
        match_run   = _fake_agent_run("match_agent")
        rewrite_run = _fake_agent_run("rewrite_agent")

        with patch("app.graph.workflow.ResumeAgent")  as MR, \
             patch("app.graph.workflow.JDAgent")       as MJ, \
             patch("app.graph.workflow.MatchAgent")    as MM, \
             patch("app.graph.workflow.RewriteAgent")  as MW:

            MR.return_value.parse.return_value   = (_fake_resume_model(), resume_run)
            MJ.return_value.parse.return_value   = (_fake_jd_model(),     jd_run)
            MM.return_value.match.side_effect    = [
                (_fake_match_model(50.0), match_run),   # low score → rewrite
                (_fake_match_model(75.0), match_run),   # after rewrite → interview
            ]
            # Agent internally retried: first attempt had fidelity 0.70 (fail),
            # second attempt produced fidelity 0.95 (pass) — rewrite_attempts=2
            MW.return_value.rewrite.return_value = (
                _fake_rewrite_model(fidelity_score=0.95, rewrite_attempts=2),
                rewrite_run,
            )

            final = run_full_pipeline(
                resume_file_path="/fake/resume.pdf",
                jd_text="We are hiring a senior backend engineer.",
                thread_id=_unique_thread(),
            )

        assert final["rewrite_result"] is not None
        assert final["rewrite_result"]["rewrite_attempts"] == 2
        assert final["rewrite_result"]["fidelity_report"]["fidelity_score"] == 0.95
        assert final["rewrite_result"]["fidelity_report"]["passed"] is True
        assert final["rewrite_result"]["fidelity_status"] == "passed"
        assert final["error"] is None


class TestPipelineReturnsAllResults:
    """Full pipeline run: verify all expected state fields and derived stats are present."""

    def test_pipeline_returns_all_results(self) -> None:
        resume_run  = _fake_agent_run("resume_agent")
        jd_run      = _fake_agent_run("jd_agent")
        match_run   = _fake_agent_run("match_agent")
        rewrite_run = _fake_agent_run("rewrite_agent")

        with patch("app.graph.workflow.ResumeAgent")  as MR, \
             patch("app.graph.workflow.JDAgent")       as MJ, \
             patch("app.graph.workflow.MatchAgent")    as MM, \
             patch("app.graph.workflow.RewriteAgent")  as MW:

            MR.return_value.parse.return_value   = (_fake_resume_model(), resume_run)
            MJ.return_value.parse.return_value   = (_fake_jd_model(),     jd_run)
            MM.return_value.match.side_effect    = [
                (_fake_match_model(50.0), match_run),   # low score → triggers rewrite
                (_fake_match_model(75.0), match_run),   # after rewrite → interview
            ]
            MW.return_value.rewrite.return_value = (_fake_rewrite_model(), rewrite_run)

            final = run_full_pipeline(
                resume_file_path="/fake/resume.pdf",
                jd_text="We are hiring a senior backend engineer.",
                thread_id=_unique_thread(),
            )

        # --- Core state fields ---
        assert final.get("resume")        is not None, "resume must be present"
        assert final.get("jd")            is not None, "jd must be present"
        assert final.get("match_result")  is not None, "match_result must be present"
        assert final.get("rewrite_result") is not None, "rewrite_result must be present (rewrite ran)"
        assert final.get("agent_runs")    is not None, "agent_runs must be present"
        assert final.get("workflow_status") is not None, "workflow_status must be present"

        # --- Derived stats (computable from agent_runs) ---
        agent_runs = final["agent_runs"]

        steps_completed = [
            r["agent_name"] for r in agent_runs if r.get("status") == "success"
        ]
        total_duration_ms = sum(r.get("duration_ms", 0) for r in agent_runs)
        total_tokens      = sum(r.get("token_count", 0) for r in agent_runs)

        # All four agent types ran
        assert "resume_agent"  in steps_completed
        assert "jd_agent"      in steps_completed
        assert "match_agent"   in steps_completed
        assert "rewrite_agent" in steps_completed

        # Aggregates are non-zero (each fake run contributes 100 ms and 50 tokens)
        assert total_duration_ms > 0
        assert total_tokens > 0

        # Sanity-check the workflow completed without error
        assert final["workflow_status"] == "completed"
        assert final["error"] is None

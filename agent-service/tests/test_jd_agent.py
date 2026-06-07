"""
Tests for JDAgent.

No real Anthropic API calls or HTTP requests are ever made — all external
calls are mocked with unittest.mock.
"""

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

from app.agents.jd_agent import JDAgent, JDFetchError, JDParseError
from app.models.job_description import ParsedJobDescription

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_VALID_JD_PAYLOAD = {
    "title": "Backend Engineer",
    "company": "Acme Corp",
    "location": "New York, NY",
    "remote_type": "hybrid",
    "employment_type": "full-time",
    "min_years_experience": 3,
    "max_years_experience": 6,
    "salary_min": 130000,
    "salary_max": 170000,
    "salary_currency": "USD",
    "responsibilities": [
        "Design and ship scalable REST APIs",
        "Participate in on-call rotation",
    ],
    "skills": [
        {"name": "Python", "is_required": True, "category": "language"},
        {"name": "Docker", "is_required": True, "category": "tool"},
        {"name": "Kubernetes", "is_required": False, "category": "tool"},
    ],
    "qualifications": [
        "Bachelor's degree in CS or equivalent experience",
        "3+ years of backend engineering experience",
    ],
    "keywords": ["Python", "REST", "Docker", "Kubernetes", "microservices"],
    "industry": "SaaS",
    "raw_text": "Backend Engineer at Acme Corp...",
    "source_url": None,
    "parse_confidence": 0.88,
}

_SAMPLE_HTML = """
<html>
<head><title>Jobs at Acme</title></head>
<body>
  <nav>Site navigation here</nav>
  <main>
    <h1>Backend Engineer</h1>
    <p>We are looking for a backend engineer to join our team.</p>
    <ul>
      <li>Required: Python, Docker</li>
      <li>Preferred: Kubernetes</li>
    </ul>
  </main>
  <footer>Footer content</footer>
  <script>alert('should be stripped')</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_response(text: str) -> SimpleNamespace:
    content_block = SimpleNamespace(text=text)
    usage = SimpleNamespace(input_tokens=80, output_tokens=150)
    return SimpleNamespace(content=[content_block], usage=usage)


def _make_agent() -> JDAgent:
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic"):
            return JDAgent()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseTextReturnsValidSchema:
    def test_returns_parsed_jd_instance(self) -> None:
        agent = _make_agent()
        agent._client.messages.create.return_value = _make_fake_response(
            json.dumps(_VALID_JD_PAYLOAD)
        )

        result = agent.parse_text("Backend Engineer at Acme Corp...")

        assert isinstance(result, ParsedJobDescription)

    def test_title_populated(self) -> None:
        agent = _make_agent()
        agent._client.messages.create.return_value = _make_fake_response(
            json.dumps(_VALID_JD_PAYLOAD)
        )

        result = agent.parse_text("Backend Engineer at Acme Corp...")

        assert result.title == "Backend Engineer"

    def test_skills_populated_with_required_flag(self) -> None:
        agent = _make_agent()
        agent._client.messages.create.return_value = _make_fake_response(
            json.dumps(_VALID_JD_PAYLOAD)
        )

        result = agent.parse_text("Backend Engineer at Acme Corp...")

        required = [s.name for s in result.skills if s.is_required]
        preferred = [s.name for s in result.skills if not s.is_required]
        assert "Python" in required
        assert "Docker" in required
        assert "Kubernetes" in preferred

    def test_responsibilities_populated(self) -> None:
        agent = _make_agent()
        agent._client.messages.create.return_value = _make_fake_response(
            json.dumps(_VALID_JD_PAYLOAD)
        )

        result = agent.parse_text("Backend Engineer at Acme Corp...")

        assert len(result.responsibilities) == 2
        assert any("API" in r for r in result.responsibilities)

    def test_raw_text_is_input_not_claude_truncation(self) -> None:
        """raw_text must be overwritten with the caller's input, not Claude's placeholder."""
        agent = _make_agent()
        payload = dict(_VALID_JD_PAYLOAD)
        payload["raw_text"] = "Claude truncated this ...[truncated]"
        agent._client.messages.create.return_value = _make_fake_response(
            json.dumps(payload)
        )
        full_text = "Backend Engineer at Acme Corp. We are hiring a great engineer."

        result = agent.parse_text(full_text)

        assert result.raw_text == full_text

    def test_parse_confidence_within_bounds(self) -> None:
        agent = _make_agent()
        agent._client.messages.create.return_value = _make_fake_response(
            json.dumps(_VALID_JD_PAYLOAD)
        )

        result = agent.parse_text("Backend Engineer at Acme Corp...")

        assert 0.0 <= result.parse_confidence <= 1.0

    def test_markdown_fences_stripped(self) -> None:
        agent = _make_agent()
        fenced = f"```json\n{json.dumps(_VALID_JD_PAYLOAD)}\n```"
        agent._client.messages.create.return_value = _make_fake_response(fenced)

        result = agent.parse_text("Backend Engineer at Acme Corp...")

        assert isinstance(result, ParsedJobDescription)
        assert result.title == "Backend Engineer"


class TestParseUrlExtractsText:
    def _mock_requests_get(self) -> MagicMock:
        mock_response = MagicMock()
        mock_response.text = _SAMPLE_HTML
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_response.raise_for_status.return_value = None
        return mock_response

    def test_strips_nav_and_footer(self) -> None:
        agent = _make_agent()
        agent._client.messages.create.return_value = _make_fake_response(
            json.dumps(_VALID_JD_PAYLOAD)
        )
        mock_resp = self._mock_requests_get()

        with patch("app.agents.jd_agent.requests.get", return_value=mock_resp):
            result = agent.parse_url("https://acme.com/jobs/backend-engineer")

        # The Claude call received text that excludes nav/footer/script content
        call_args = agent._client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "Site navigation here" not in user_msg
        assert "Footer content" not in user_msg
        assert "alert(" not in user_msg

    def test_main_content_is_passed_to_claude(self) -> None:
        agent = _make_agent()
        agent._client.messages.create.return_value = _make_fake_response(
            json.dumps(_VALID_JD_PAYLOAD)
        )
        mock_resp = self._mock_requests_get()

        with patch("app.agents.jd_agent.requests.get", return_value=mock_resp):
            agent.parse_url("https://acme.com/jobs/backend-engineer")

        call_args = agent._client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "Backend Engineer" in user_msg
        assert "Python" in user_msg

    def test_source_url_is_set_on_result(self) -> None:
        agent = _make_agent()
        agent._client.messages.create.return_value = _make_fake_response(
            json.dumps(_VALID_JD_PAYLOAD)
        )
        mock_resp = self._mock_requests_get()
        url = "https://acme.com/jobs/backend-engineer"

        with patch("app.agents.jd_agent.requests.get", return_value=mock_resp):
            result = agent.parse_url(url)

        assert result.source_url == url

    def test_raises_jd_fetch_error_on_http_failure(self) -> None:
        import requests as req_lib

        agent = _make_agent()

        with patch(
            "app.agents.jd_agent.requests.get",
            side_effect=req_lib.ConnectionError("DNS failure"),
        ):
            with pytest.raises(JDFetchError) as exc_info:
                agent.parse_url("https://acme.com/jobs/backend-engineer")

        assert "acme.com" in str(exc_info.value)

    def test_raises_jd_fetch_error_when_page_has_no_text(self) -> None:
        agent = _make_agent()
        mock_resp = MagicMock()
        mock_resp.text = "<html><body><nav>nav only</nav><footer>footer only</footer></body></html>"
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.raise_for_status.return_value = None

        with patch("app.agents.jd_agent.requests.get", return_value=mock_resp):
            with pytest.raises(JDFetchError):
                agent.parse_url("https://acme.com/empty")


class TestParseAutoDetectsUrl:
    def test_https_url_routes_to_parse_url(self) -> None:
        agent = _make_agent()
        agent.parse_url = MagicMock(return_value=MagicMock(spec=ParsedJobDescription))
        agent.parse_text = MagicMock(return_value=MagicMock(spec=ParsedJobDescription))

        agent.parse("https://example.com/job/123")

        agent.parse_url.assert_called_once_with("https://example.com/job/123")
        agent.parse_text.assert_not_called()

    def test_http_url_routes_to_parse_url(self) -> None:
        agent = _make_agent()
        agent.parse_url = MagicMock(return_value=MagicMock(spec=ParsedJobDescription))
        agent.parse_text = MagicMock(return_value=MagicMock(spec=ParsedJobDescription))

        agent.parse("http://example.com/job/123")

        agent.parse_url.assert_called_once_with("http://example.com/job/123")
        agent.parse_text.assert_not_called()

    def test_plain_text_routes_to_parse_text(self) -> None:
        agent = _make_agent()
        agent.parse_url = MagicMock(return_value=MagicMock(spec=ParsedJobDescription))
        agent.parse_text = MagicMock(return_value=MagicMock(spec=ParsedJobDescription))
        jd_text = "We are looking for a senior backend engineer with 5 years of Python."

        agent.parse(jd_text)

        agent.parse_text.assert_called_once_with(jd_text)
        agent.parse_url.assert_not_called()

    def test_non_http_url_like_string_routes_to_parse_text(self) -> None:
        """Strings starting with ftp:// or bare domains go to parse_text."""
        agent = _make_agent()
        agent.parse_url = MagicMock(return_value=MagicMock(spec=ParsedJobDescription))
        agent.parse_text = MagicMock(return_value=MagicMock(spec=ParsedJobDescription))

        agent.parse("ftp://example.com/job.txt")

        agent.parse_text.assert_called_once()
        agent.parse_url.assert_not_called()


class TestParseRetryOnInvalidJson:
    def test_retries_and_succeeds_on_second_call(self) -> None:
        agent = _make_agent()
        agent._client.messages.create.side_effect = [
            _make_fake_response("not valid json {{{{"),
            _make_fake_response(json.dumps(_VALID_JD_PAYLOAD)),
        ]

        result = agent.parse_text("Backend Engineer role...")

        assert isinstance(result, ParsedJobDescription)
        assert agent._client.messages.create.call_count == 2

    def test_retry_prompt_contains_important_marker(self) -> None:
        agent = _make_agent()
        agent._client.messages.create.side_effect = [
            _make_fake_response("bad json"),
            _make_fake_response(json.dumps(_VALID_JD_PAYLOAD)),
        ]

        agent.parse_text("Backend Engineer role...")

        second_call = agent._client.messages.create.call_args_list[1]
        user_msg = second_call.kwargs["messages"][0]["content"]
        assert "IMPORTANT" in user_msg

    def test_raises_jd_parse_error_after_two_failures(self) -> None:
        agent = _make_agent()
        agent._client.messages.create.side_effect = [
            _make_fake_response("not json"),
            _make_fake_response("still not json"),
        ]

        with pytest.raises(JDParseError):
            agent.parse_text("Backend Engineer role...")

        assert agent._client.messages.create.call_count == 2

    def test_invalid_schema_triggers_retry(self) -> None:
        """Valid JSON that fails Pydantic validation (missing title) also retries."""
        agent = _make_agent()
        bad_payload = {"raw_text": "text", "parse_confidence": 99.9}  # missing title, bad confidence
        agent._client.messages.create.side_effect = [
            _make_fake_response(json.dumps(bad_payload)),
            _make_fake_response(json.dumps(_VALID_JD_PAYLOAD)),
        ]

        result = agent.parse_text("Backend Engineer role...")

        assert isinstance(result, ParsedJobDescription)
        assert agent._client.messages.create.call_count == 2


class TestParseTextShortInput:
    def test_empty_string_raises_jd_parse_error(self) -> None:
        """Text shorter than 20 chars should raise JDParseError before calling Claude."""
        agent = _make_agent()

        with pytest.raises(JDParseError) as exc_info:
            agent.parse_text("")

        assert "too short" in str(exc_info.value).lower()
        agent._client.messages.create.assert_not_called()

    def test_short_text_raises_jd_parse_error(self) -> None:
        agent = _make_agent()

        with pytest.raises(JDParseError):
            agent.parse_text("Too short.")

        agent._client.messages.create.assert_not_called()

    def test_exactly_threshold_passes_through(self) -> None:
        """Text of exactly 20 non-whitespace chars should reach Claude."""
        agent = _make_agent()
        agent._client.messages.create.return_value = _make_fake_response(
            json.dumps(_VALID_JD_PAYLOAD)
        )
        # 20 printable chars
        text = "A" * 20

        result = agent.parse_text(text)

        assert isinstance(result, ParsedJobDescription)
        agent._client.messages.create.assert_called_once()


class TestEdgeCases:
    def test_short_jd_raises_error(self) -> None:
        """Text under 20 chars raises JDParseError without calling Claude."""
        agent = _make_agent()

        with pytest.raises(JDParseError) as exc_info:
            agent.parse_text("Hire me!")

        assert "too short" in str(exc_info.value).lower()
        agent._client.messages.create.assert_not_called()

    def test_url_404_raises_error(self) -> None:
        """A 404 response must raise JDFetchError with the status code in the message."""
        agent = _make_agent()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.raise_for_status.return_value = None

        with patch("app.agents.jd_agent.requests.get", return_value=mock_resp):
            with pytest.raises(JDFetchError) as exc_info:
                agent.parse_url("https://example.com/jobs/expired")

        assert "404" in str(exc_info.value)

    def test_url_403_raises_error(self) -> None:
        """A 403 response must raise JDFetchError with the status code in the message."""
        agent = _make_agent()
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.raise_for_status.return_value = None

        with patch("app.agents.jd_agent.requests.get", return_value=mock_resp):
            with pytest.raises(JDFetchError) as exc_info:
                agent.parse_url("https://example.com/jobs/blocked")

        assert "403" in str(exc_info.value)

    def test_non_html_content_type_raises_error(self) -> None:
        """A URL returning a PDF (non-HTML Content-Type) must raise JDFetchError."""
        agent = _make_agent()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/pdf"}
        mock_resp.raise_for_status.return_value = None

        with patch("app.agents.jd_agent.requests.get", return_value=mock_resp):
            with pytest.raises(JDFetchError) as exc_info:
                agent.parse_url("https://example.com/jobs/posting.pdf")

        assert "application/pdf" in str(exc_info.value)

    def test_html_entities_cleaned(self) -> None:
        """HTML entities (&amp; &nbsp; &lt; etc.) must be decoded before Claude receives the text."""
        agent = _make_agent()
        agent._client.messages.create.return_value = _make_fake_response(
            json.dumps(_VALID_JD_PAYLOAD)
        )

        html_with_entities = """
        <html><body>
          <h1>Senior Engineer &amp; Tech Lead</h1>
          <p>Salary:&nbsp;$120,000&nbsp;&ndash;&nbsp;$150,000</p>
          <p>Requirements: Python &gt;= 3.10 &amp; experience with AWS&lt;br&gt;</p>
        </body></html>
        """
        mock_resp = MagicMock()
        mock_resp.text = html_with_entities
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.raise_for_status.return_value = None

        with patch("app.agents.jd_agent.requests.get", return_value=mock_resp):
            agent.parse_url("https://example.com/jobs/senior-engineer")

        call_args = agent._client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]

        # Entities must be decoded — raw entity strings must not appear
        assert "&amp;" not in user_msg
        assert "&nbsp;" not in user_msg
        assert "&gt;" not in user_msg
        assert "&lt;" not in user_msg
        # Decoded content must be present
        assert "&" in user_msg
        assert "$120,000" in user_msg

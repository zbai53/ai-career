import html
import json
import logging
import os
import re
import time

import anthropic
import requests
from bs4 import BeautifulSoup
from pydantic import ValidationError

from app.models.job_description import ParsedJobDescription
from app.utils.agent_logger import log_agent_run

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 4096
_MIN_JD_CHARS = 20

_JD_SCHEMA = json.dumps(ParsedJobDescription.model_json_schema(), indent=2)

_SYSTEM_PROMPT = f"""\
You are an expert job description parser. Given the raw text of a job posting, \
extract all information and return ONLY a single valid JSON object that matches \
the schema below — no prose, no markdown fences, no extra keys.

SCHEMA:
{_JD_SCHEMA}

RULES:
1. Return only the JSON object, nothing else.
2. For each skill, set is_required to true if the posting uses language like \
   "required", "must have", "you will need", or "minimum qualifications". \
   Set is_required to false for "preferred", "nice to have", "bonus", or \
   "desired" qualifications.
3. Extract keywords: ATS-relevant terms including technologies, methodologies, \
   domain vocabulary, and role-specific phrases that a recruiter's system would \
   scan for. Include both required and preferred skill names.
4. salary_min and salary_max must be integers (annual, in salary_currency units). \
   Omit (null) if not stated.
5. remote_type must be one of: "remote", "hybrid", "onsite", or null if unclear.
6. employment_type must be one of: "full-time", "part-time", "contract", "intern", \
   or null if unclear.
7. Set parse_confidence to a float between 0.0 and 1.0: 0.9–1.0 for clean, \
   complete postings; 0.6–0.9 for postings with some ambiguity or missing sections; \
   below 0.6 for sparse or poorly structured postings.
8. raw_text: include only the first 500 characters of the input followed by \
   '...[truncated]'. Do NOT include the full text.\
"""

_RETRY_SUFFIX = """

IMPORTANT: Your previous response could not be validated against the schema. \
Common mistakes:
- Missing required fields: title (string), raw_text (string), parse_confidence (float).
- salary fields must be integers or null, not strings.
- parse_confidence must be a float between 0.0 and 1.0.
- is_required in each skill entry must be a boolean.
Return ONLY the corrected JSON object.\
"""

_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_STRIP_TAGS = {"nav", "footer", "header", "script", "style", "noscript", "aside"}


class JDFetchError(Exception):
    pass


class JDParseError(Exception):
    pass


class JDAgent:
    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._token_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, input_text: str) -> tuple[ParsedJobDescription, dict]:
        """Route to parse_url or parse_text based on whether input looks like a URL."""
        if input_text.startswith("http://") or input_text.startswith("https://"):
            return self.parse_url(input_text)
        return self.parse_text(input_text)

    def parse_text(self, raw_text: str) -> tuple[ParsedJobDescription, dict]:
        """
        Parse a raw job description string.

        Returns:
            (ParsedJobDescription, agent_run_log)
        """
        if len(raw_text.strip()) < _MIN_JD_CHARS:
            raise JDParseError(
                f"JD text too short to parse ({len(raw_text.strip())} chars, minimum {_MIN_JD_CHARS})."
            )

        self._token_count = 0
        t0 = time.perf_counter()
        result = self._call_claude(raw_text, strict=False)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.info("JD parsed in %d ms (confidence=%.2f)", duration_ms, result.parse_confidence)

        agent_run = log_agent_run(
            agent_name="jd_agent",
            input_summary=raw_text[:100],
            output_summary=(
                f"Parsed {result.title or 'Unknown'} at {result.company or 'Unknown'}, "
                f"{len(result.skills)} skills"
            ),
            status="success",
            duration_ms=duration_ms,
            token_count=self._token_count,
            model_name=_MODEL,
        )
        return result, agent_run

    def parse_url(self, url: str) -> tuple[ParsedJobDescription, dict]:
        """
        Fetch a job posting URL, extract its text content, then parse it.

        Returns:
            (ParsedJobDescription, agent_run_log)
        """
        self._token_count = 0
        t0 = time.perf_counter()
        raw_text = self._fetch_text_from_url(url)
        fetch_ms = (time.perf_counter() - t0) * 1000
        logger.info("Fetched %s in %.0f ms (%d chars)", url, fetch_ms, len(raw_text))

        result = self._call_claude(raw_text, strict=False)
        result.source_url = url

        duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "JD from URL parsed in %d ms total (confidence=%.2f)",
            duration_ms,
            result.parse_confidence,
        )

        agent_run = log_agent_run(
            agent_name="jd_agent",
            input_summary=url[:100],
            output_summary=(
                f"Parsed {result.title or 'Unknown'} at {result.company or 'Unknown'}, "
                f"{len(result.skills)} skills"
            ),
            status="success",
            duration_ms=duration_ms,
            token_count=self._token_count,
            model_name=_MODEL,
        )
        return result, agent_run

    # ------------------------------------------------------------------
    # Web fetch helper
    # ------------------------------------------------------------------

    def _fetch_text_from_url(self, url: str) -> str:
        try:
            response = requests.get(url, headers=_FETCH_HEADERS, timeout=15)
        except requests.RequestException as exc:
            raise JDFetchError(f"Failed to fetch '{url}': {exc}") from exc

        # Surface 403/404 and other HTTP errors with a clear status code message
        if isinstance(response.status_code, int) and response.status_code in (403, 404):
            raise JDFetchError(
                f"URL returned HTTP {response.status_code}: '{url}'. "
                f"{'Access denied.' if response.status_code == 403 else 'Page not found.'}"
            )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise JDFetchError(
                f"URL returned HTTP {response.status_code}: '{url}'"
            ) from exc

        # Reject non-HTML content types (PDFs, JSON APIs, etc.)
        content_type = response.headers.get("Content-Type", "")
        if isinstance(content_type, str) and content_type and "text/html" not in content_type:
            raise JDFetchError(
                f"URL returned non-HTML content (Content-Type: '{content_type}'). "
                f"Only HTML job posting pages are supported."
            )

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup.find_all(_STRIP_TAGS):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Decode HTML entities (&amp; &nbsp; &lt; etc.)
        text = html.unescape(text)
        # Normalise non-breaking spaces and other unicode whitespace to regular spaces
        text = re.sub(r"[\xa0\u2009\u200b\u200c\u200d\ufeff]", " ", text)
        # Collapse runs of blank lines
        lines = [line for line in text.splitlines() if line.strip()]
        cleaned = "\n".join(lines)

        if not cleaned:
            raise JDFetchError(f"No readable text could be extracted from '{url}'")
        return cleaned

    # ------------------------------------------------------------------
    # Claude interaction
    # ------------------------------------------------------------------

    def _call_claude(self, raw_text: str, strict: bool) -> ParsedJobDescription:
        user_content = f"Parse the following job description:\n\n{raw_text}"
        if strict:
            user_content += _RETRY_SUFFIX

        t0 = time.perf_counter()
        response = self._client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        usage = response.usage
        self._token_count += usage.input_tokens + usage.output_tokens
        logger.info(
            "Claude responded in %.0f ms | input_tokens=%d output_tokens=%d",
            elapsed_ms,
            usage.input_tokens,
            usage.output_tokens,
        )

        raw_json = response.content[0].text.strip()

        # Strip accidental markdown fences
        if raw_json.startswith("```"):
            lines = raw_json.splitlines()
            raw_json = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        try:
            data = json.loads(raw_json)
            # Always store the full extracted text, not Claude's truncated placeholder
            data["raw_text"] = raw_text
            return ParsedJobDescription.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            if strict:
                raise JDParseError(
                    f"Claude response failed validation after retry: {exc}\n\nResponse:\n{raw_json}"
                ) from exc
            logger.warning("Initial JD parse failed (%s), retrying with stricter prompt", exc)
            return self._call_claude(raw_text, strict=True)

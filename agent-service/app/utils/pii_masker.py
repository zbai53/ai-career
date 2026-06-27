"""
PiiMasker — replace personal identifiable information in resume text with
stable placeholders before sending to Claude, then restore the originals
from the mapping after receiving a response.

Supported PII categories
------------------------
  [NAME_n]     — Candidate name (capitalized words on the first non-empty line)
  [EMAIL_n]    — Email addresses
  [PHONE_n]    — Phone numbers (various North American / international formats)
  [ADDRESS_n]  — City + state/province patterns
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Email: anything@anything.tld
_RE_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# Phone: handles +1-xxx-xxx-xxxx, (xxx) xxx-xxxx, xxx.xxx.xxxx, etc.
_RE_PHONE = re.compile(
    r"""
    (?:\+?1[\s.\-]?)?          # optional country code +1
    (?:\(\d{3}\)|\d{3})        # area code — with or without parens
    [\s.\-]?                   # separator
    \d{3}                      # exchange
    [\s.\-]?                   # separator
    \d{4}                      # subscriber
    (?!\d)                     # not followed by more digits
    """,
    re.VERBOSE,
)

# US/Canadian address: "City, ST" or "City, State" (2-letter code or full name)
_US_STATES = (
    r"AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|"
    r"MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|"
    r"WA|WV|WI|WY|DC|"
    r"ON|BC|AB|QC|MB|SK|NS|NB|NL|PE|NT|NU|YT"   # Canadian provinces
)
_RE_ADDRESS = re.compile(
    rf"""
    \b
    ([A-Z][a-z]+(?: [A-Z][a-z]+)*)   # city (one or more title-case words)
    ,\s*
    (?:{_US_STATES}                   # 2-letter state/province code
    |[A-Z][a-z]{{3,}})               # or full state name (>= 4 chars, title-case)
    \b
    """,
    re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Name detection helper
# ---------------------------------------------------------------------------

def _extract_candidate_name(text: str) -> Optional[str]:
    """
    Heuristic: the candidate name is typically the first non-empty line of a
    resume and consists of 2–4 capitalized words (no digits, no symbols).

    Returns the matched string or None.
    """
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Accept 2–4 words where every word starts with a capital letter
        # and contains only letters, hyphens, or apostrophes.
        parts = line.split()
        if 2 <= len(parts) <= 4 and all(
            re.fullmatch(r"[A-Z][A-Za-z\-']+", p) for p in parts
        ):
            return line
        # Stop after the first non-empty line — if it doesn't look like a
        # name we won't try to guess further.
        break
    return None


# ---------------------------------------------------------------------------
# PiiMasker
# ---------------------------------------------------------------------------

class PiiMasker:
    """
    Stateless helper — each call to mask() produces a fresh mapping dict.
    The caller is responsible for storing the mapping and passing it to
    unmask() after the LLM response is received.

    Example
    -------
    ::

        masker = PiiMasker()
        masked_text, mapping = masker.mask(raw_resume_text)
        # send masked_text to Claude …
        response_text = call_claude(masked_text)
        # restore real values
        clean_response = masker.unmask(response_text, mapping)
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mask(self, text: str) -> tuple[str, dict[str, str]]:
        """
        Replace PII in *text* with stable placeholders.

        Returns
        -------
        (masked_text, mapping)
            mapping: placeholder → original value (use with unmask())
        """
        mapping: dict[str, str] = {}   # placeholder → original
        result = text

        # 1. Candidate name — must run first so it doesn't clash with email
        #    or address detection.
        name = _extract_candidate_name(result)
        if name:
            placeholder = "[NAME_1]"
            mapping[placeholder] = name
            # Replace all occurrences (the name may appear in multiple places)
            result = result.replace(name, placeholder)
            logger.debug("PiiMasker: masked name '%s' → %s", name, placeholder)

        # 2. Emails
        result = self._replace_matches(result, _RE_EMAIL, "EMAIL", mapping)

        # 3. Phone numbers — after email so "user@1-800-foo.com" is handled
        #    by email first.
        result = self._replace_matches(result, _RE_PHONE, "PHONE", mapping)

        # 4. Addresses
        result = self._replace_matches(result, _RE_ADDRESS, "ADDRESS", mapping)

        logger.info(
            "PiiMasker.mask: %d PII token(s) replaced (%s)",
            len(mapping),
            ", ".join(mapping.keys()),
        )
        return result, mapping

    @staticmethod
    def unmask(text: str, mapping: dict[str, str]) -> str:
        """
        Restore all placeholders in *text* back to their original values
        using *mapping* produced by a previous mask() call.

        Unknown placeholders are left as-is so the caller can inspect them.
        """
        result = text
        for placeholder, original in mapping.items():
            result = result.replace(placeholder, original)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _replace_matches(
        text: str,
        pattern: re.Pattern,
        label: str,
        mapping: dict[str, str],
    ) -> str:
        """
        Replace all regex matches with ``[LABEL_n]`` placeholders, reusing
        the same placeholder when the same original value appears again.

        Updates *mapping* in-place.
        """
        # Reverse mapping: original → placeholder (for deduplication)
        rev: dict[str, str] = {v: k for k, v in mapping.items() if k.startswith(f"[{label}_")}

        def replacer(m: re.Match) -> str:
            original = m.group(0)
            if original in rev:
                return rev[original]
            n = sum(1 for k in mapping if k.startswith(f"[{label}_")) + 1
            placeholder = f"[{label}_{n}]"
            mapping[placeholder] = original
            rev[original] = placeholder
            logger.debug("PiiMasker: masked %s '%s' → %s", label, original, placeholder)
            return placeholder

        return pattern.sub(replacer, text)

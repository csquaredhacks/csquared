"""The only LLM call in the product: one short icebreaker for a suggested pair.
Optional by design. With no OPENAI_API_KEY, or on any error, it returns "" and the
app falls back to a template (matching.default_icebreaker)."""

import logging

from openai import OpenAI

from .config import settings
from .telemetry import tracer

log = logging.getLogger("hallway.llm")

PROMPT = """Two people are about to meet at a tech conference. Write ONE friendly opening
question (max 25 words) that either of them could ask the other. Be specific to their
profiles, no flattery, no emoji, no quotation marks.

{a_name} is working on: {a_work}. Needs: {a_asks}. Offers: {a_offers}.
{b_name} is working on: {b_work}. Needs: {b_asks}. Offers: {b_offers}.
Why they were matched: {reason}"""


def icebreaker(a: dict, b: dict, reason: str) -> str:
    if not settings.openai_api_key:
        return ""
    prompt = PROMPT.format(
        a_name=a["name"], a_work=a["working_on"], a_asks=a["asks"], a_offers=a["offers"],
        b_name=b["name"], b_work=b["working_on"], b_asks=b["asks"], b_offers=b["offers"],
        reason=reason,
    )  # fmt: skip
    with tracer.start_as_current_span("match.icebreaker"):
        try:
            client = OpenAI(api_key=settings.openai_api_key, timeout=8, max_retries=0)
            reply = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=60,
                messages=[{"role": "user", "content": prompt}],
            )
            return (reply.choices[0].message.content or "").strip().strip('"')
        except Exception as error:  # noqa: BLE001 - an icebreaker must never break matching
            log.warning("icebreaker failed: %s", error)
            return ""

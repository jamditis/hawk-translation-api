import subprocess
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SCORE_THRESHOLD = 3.0   # segments below this get flagged for human review
SUBPROCESS_TIMEOUT = 30  # seconds — non-blocking: timeout returns None, not a job failure


@dataclass
class ScoreResult:
    overall: float
    fluency: float
    accuracy: float
    flags: list[str] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return self.overall < SCORE_THRESHOLD


SCORING_PROMPT_TEMPLATE = """Score this translation from English to {target_lang}.

Original English:
{original}

Translation:
{translated}

Evaluate on:
- Fluency: Does it read naturally in {target_lang}? (1-5)
- Accuracy: Is the meaning preserved? (1-5)
- Overall: Combined quality score (1-5)

Flag any issues (awkward phrasing, mistranslated terms, changed meaning, etc.)

Respond with ONLY valid JSON, no other text:
{{"overall": <number>, "fluency": <number>, "accuracy": <number>, "flags": [<strings>]}}"""


def score_translation(original: str, translated: str, target_lang: str) -> "ScoreResult | None":
    """
    Score a translation using claude -p subprocess.

    Returns None on timeout or invalid output — scoring is advisory.
    A None result means the job still completes; scores are just absent.
    """
    prompt = SCORING_PROMPT_TEMPLATE.format(
        target_lang=target_lang,
        original=original[:2000].replace("{", "{{").replace("}", "}}"),
        translated=translated[:2000].replace("{", "{{").replace("}", "}}"),
    )

    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        data = json.loads(result.stdout.strip())
        return ScoreResult(
            overall=float(data["overall"]),
            fluency=float(data["fluency"]),
            accuracy=float(data["accuracy"]),
            flags=data.get("flags") or [],
        )
    except subprocess.TimeoutExpired:
        logger.warning("Quality scoring timed out for translation to %s", target_lang)
        return None
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning("Quality scoring returned invalid output: %s", e)
        return None

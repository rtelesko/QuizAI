import logging
import random
from collections import defaultdict, deque
from os import getenv
from typing import Dict, List, Optional, Iterable

from openai import OpenAI
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _filter_chunks(chunks: Iterable[str], exclude_terms: list[str]) -> list[str]:
    if not exclude_terms:
        return list(chunks)
    lows = [t.lower() for t in exclude_terms]
    return [c for c in chunks if not any(t in c.lower() for t in lows)]


def _violates_exclusions(text: str, exclude_terms: list[str]) -> bool:
    if not exclude_terms:
        return False
    low = text.lower()
    return any(t in low for t in exclude_terms)


class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    answer: str
    explanation: str


# Keep a SMALL, per-topic memory of recent question stems to avoid repeats.
_RECENT_QUESTION_STEMS: Dict[str, deque] = defaultdict(lambda: deque(maxlen=15))

# Single, stable system message (no ever-growing chat log)
_BASE_SYSTEM = {
    "role": "system",
    "content": (
        "You are a REST API server with an endpoint /generate-random-question/:topic. "
        "The endpoint returns a Python quiz question as strict JSON with fields:\n"
        "- question (string)\n"
        "- options (array of 4 strings)\n"
        "- answer (string, exactly one of options)\n"
        "- explanation (string)\n\n"
        "Vary question STYLE and DIFFICULTY across calls. Styles to rotate among include:\n"
        "• Concept check • Predict the output • Spot the bug • Fill-in-the-blank • Which option is true?\n"
        "If the provided study material lacks details for a style, pick another style.\n"
        "The question MUST be grounded in the provided study material.\n"
        "Return ONLY a JSON object."
    ),
}


def _sample_context(context_chunks: List[str], max_chunks: int = 3) -> str:
    """Randomly sample up to max_chunks distinct chunks and join them."""
    if not context_chunks:
        return ""
    k = min(max_chunks, len(context_chunks))
    sample = random.sample(context_chunks, k=k)
    # Light shuffle to avoid deterministic ordering
    random.shuffle(sample)
    return "\n\n---\n\n".join(sample)


def _make_prompt(topic: str, study_text: str, recent_stems: List[str], exclude_terms: List[str]) -> str:
    difficulty = random.choice(["easy", "medium", "hard"])
    style = random.choice(
        ["concept check", "predict the output", "spot the bug", "fill-in-the-blank", "true vs false"]
    )
    avoid_block = "\n".join(f"- {s}" for s in recent_stems) if recent_stems else "None"
    exclude_block = ", ".join(sorted(set(exclude_terms))) if exclude_terms else "None"

    return f"""
Use the following study material to create one quiz question about "{topic}".

Study Material:
{study_text}

Constraints:
- Style this time: {style}
- Difficulty this time: {difficulty}
- Provide exactly 4 options (short and plausible), one correct.
- The "answer" must match one of the options exactly.
- Do not reuse these recent stems (or anything too similar):
{avoid_block}
- Do not write about ANY of these excluded subtopics (or close variants / synonyms):
{exclude_block}

Return ONLY a JSON object with keys "question", "options", "answer", "explanation".
""".strip()


def get_quiz_from_topic(
        topic: str,
        api_key: str,
        context_chunks: Optional[List[str]] = None,
        exclude_terms: Optional[List[str]] = None,
        max_retries: int = 2,
) -> Optional[Dict[str, str]]:
    context_chunks = context_chunks or []
    exclude_terms = [t.strip().lower() for t in (exclude_terms or [])]

    usable_chunks = _filter_chunks(context_chunks, exclude_terms)
    if not usable_chunks:
        logger.info("All context chunks were excluded by 'exclude_terms'. Aborting generation.")
        return None

    study_text = _sample_context(usable_chunks, max_chunks=3)
    client = OpenAI(api_key=api_key)
    recent_stems = list(_RECENT_QUESTION_STEMS[topic])
    model_id = getenv("MODEL_ID", "chatgpt-4o-latest")

    for attempt in range(max_retries):
        prompt = _make_prompt(topic, study_text, recent_stems, exclude_terms)
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=[_BASE_SYSTEM, {"role": "user", "content": prompt}],
                temperature=0.9,
                top_p=1.0,
                presence_penalty=0.7,
                frequency_penalty=0.2,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            quiz = QuizQuestion.parse_raw(content)

            haystack = " ".join([quiz.question] + quiz.options + [quiz.explanation])
            if _violates_exclusions(haystack, exclude_terms):
                logger.debug("Quiz mentions an excluded subtopic; retrying…")
                continue

            if quiz.answer not in quiz.options:
                raise ValueError("Answer is not among the provided options.")

            opts = quiz.options[:]
            random.shuffle(opts)
            quiz.options = opts

            _RECENT_QUESTION_STEMS[topic].append(quiz.question.strip())
            return quiz.dict()

        except Exception as e:
            logger.debug(f"Attempt {attempt + 1} failed: {e}")

    return None

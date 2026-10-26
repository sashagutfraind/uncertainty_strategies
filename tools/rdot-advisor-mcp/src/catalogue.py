"""Load and search the public RDOT strategy catalogue (CSV, no pivotal properties)."""
from __future__ import annotations

import csv
import io
import math
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

REPO = "sashagutfraind/uncertainty_strategies"
CSV_PATH = "strategies_uncertainty_latest.csv"
# The catalogue ships in the same repo, two levels above this tool (tools/rdot-advisor-mcp/).
LOCAL_CSV = Path(__file__).resolve().parents[3] / CSV_PATH
# Set RDOT_CSV_REF to a branch, tag or commit to fetch that version from GitHub instead of the local file.
CSV_REF = os.environ.get("RDOT_CSV_REF")
CSV_URL = f"https://raw.githubusercontent.com/{REPO}/{CSV_REF or 'main'}/{CSV_PATH}"

CACHE_FILE = Path(__file__).resolve().parent.parent / ".cache" / "strategies.csv"


STOPWORDS = frozenset(
    """a an and are as at be been being but by can could do does for from had has have how i if in into is it its
    may might more most must no not of on or our over should so such than that the their them then there these
    they this those through to too under up us use used using very was we were what when where which while who
    why will with within would you your""".split()
)

# Field weights for BM25: a match in the name counts most, then the definition, then everything else.
FIELD_WEIGHTS = {"name": 3, "definition": 2, "related": 1, "examples": 1, "category": 1}
BM25_K1, BM25_B = 1.5, 0.75
# Only drops near-zero noise. Measured on labeled queries, no cutoff separates on-topic from off-topic queries
# ("write a poem about cats" outscores many real ones), so callers must judge relevance themselves.
MIN_SCORE = 1.0


def _stem(token: str) -> str:
    """Crude suffix stripping so 'breaches'/'breach' and 'failing'/'fail' match; applied to queries and docs alike."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1 and t not in STOPWORDS]


@dataclass
class Strategy:
    name: str
    definition: str
    category: str
    examples: list[str]
    related: str
    notes: str
    references: list[str]

    def weighted_tokens(self) -> list[str]:
        fields = {
            "name": self.name,
            "definition": self.definition,
            "related": self.related,
            "examples": " ".join(self.examples),
            "category": self.category,
        }
        return [t for key, text in fields.items() for t in tokenize(text) * FIELD_WEIGHTS[key]]


@dataclass
class Catalogue:
    strategies: list[Strategy]
    source: str  # the local file path or the GitHub URL the CSV was read from
    loaded_at: str
    from_cache: bool
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._doc_tf = []
        df: dict[str, int] = {}
        for s in self.strategies:
            tf: dict[str, int] = {}
            for t in s.weighted_tokens():
                tf[t] = tf.get(t, 0) + 1
            self._doc_tf.append(tf)
            for t in tf:
                df[t] = df.get(t, 0) + 1
        n = len(self.strategies)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
        self._doc_len = [sum(tf.values()) for tf in self._doc_tf]
        self._avg_len = sum(self._doc_len) / n if n else 0.0

    def info(self) -> dict:
        return {
            "source": self.source,
            "loaded_at": self.loaded_at,
            "strategy_count": len(self.strategies),
            "from_cache": self.from_cache,
            "errors": self.errors,
        }

    def get(self, name: str) -> Strategy | None:
        """Exact (case-insensitive) match first, then a substring match if exactly one strategy qualifies."""
        lowered = name.strip().lower()
        for s in self.strategies:
            if s.name.lower() == lowered:
                return s
        matches = [s for s in self.strategies if lowered in s.name.lower()]
        return matches[0] if len(matches) == 1 else None

    def search(self, query: str, limit: int = 10, min_score: float = MIN_SCORE) -> list[tuple[Strategy, float]]:
        """BM25 over weighted fields, best first; results below `min_score` (near-zero noise) are dropped."""
        terms = set(tokenize(query))
        scored = []
        for s, tf, dl in zip(self.strategies, self._doc_tf, self._doc_len):
            score = 0.0
            for t in terms:
                f = tf.get(t, 0)
                if f:
                    norm = BM25_K1 * (1 - BM25_B + BM25_B * dl / self._avg_len)
                    score += self._idf[t] * f * (BM25_K1 + 1) / (f + norm)
            if score >= min_score:
                scored.append((s, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]


def _parse_csv(text: str) -> list[Strategy]:
    reader = csv.DictReader(io.StringIO(text))
    strategies = []
    for row in reader:
        name = (row.get("Strategy for uncertainty") or "").strip()
        if not name:
            continue
        examples = [row.get(f"Example {i}", "").strip() for i in (1, 2, 3)]
        references = [row.get(k, "").strip() for k in ("reference1", "reference2")]
        strategies.append(
            Strategy(
                name=name,
                definition=(row.get("Definition") or "").strip(),
                category=(row.get("category") or "").strip(),
                examples=[e for e in examples if e],
                related=(row.get("Related strategies and aliases") or "").strip(),
                notes=(row.get("Notes") or "").strip(),
                references=[r for r in references if r],
            )
        )
    return strategies


def _fetch() -> tuple[str, bool, list[str]]:
    """Fetch the CSV from GitHub, falling back to the last cached copy if the fetch fails."""
    try:
        response = httpx.get(CSV_URL, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(response.text)
        return response.text, False, []
    except httpx.HTTPError as error:
        errors = [f"fetch failed ({type(error).__name__}): {error}"]
        if CACHE_FILE.exists():
            return CACHE_FILE.read_text(), True, errors
        raise RuntimeError(f"Could not fetch {CSV_URL} and no cached copy exists at {CACHE_FILE}. {errors}")


def load() -> Catalogue:
    """Read the CSV that ships in this repo; fetch from GitHub only if RDOT_CSV_REF is set or the tool has been
    copied out of the repo."""
    if CSV_REF is None and LOCAL_CSV.exists():
        text, source, from_cache, errors = LOCAL_CSV.read_text(), str(LOCAL_CSV), False, []
    else:
        text, from_cache, errors = _fetch()
        source = CSV_URL
    return Catalogue(
        strategies=_parse_csv(text),
        source=source,
        loaded_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        from_cache=from_cache,
        errors=errors,
    )

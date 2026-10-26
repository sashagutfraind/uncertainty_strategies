"""Load and search the public RDOT strategy catalogue (CSV, no pivotal properties)."""
from __future__ import annotations

import csv
import hashlib
import io
import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

# The catalogue ships in the same repo, two levels above this tool (tools/rdot-advisor-mcp/). The server never
# downloads anything: RDOT_CSV_PATH can point at another local copy, e.g. when the tool is used outside the repo.
REPO_CSV = Path(__file__).resolve().parents[3] / "strategies_uncertainty_latest.csv"
CSV_FILE = Path(os.environ["RDOT_CSV_PATH"]).expanduser() if os.environ.get("RDOT_CSV_PATH") else REPO_CSV


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
    source: str
    sha256: str
    loaded_at: str

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
            "sha256": self.sha256,
            "loaded_at": self.loaded_at,
            "strategy_count": len(self.strategies),
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


def load(path: Path = CSV_FILE) -> Catalogue:
    """Read the catalogue CSV from local disk (by default the copy shipped in this repo)."""
    if not path.is_file():
        raise FileNotFoundError(
            f"RDOT catalogue not found at {path}. Run the server from a checkout of the uncertainty_strategies repo, "
            "or set RDOT_CSV_PATH to a local copy of strategies_uncertainty_latest.csv."
        )
    data = path.read_bytes()
    return Catalogue(
        strategies=_parse_csv(data.decode("utf-8-sig")),
        source=str(path),
        sha256=hashlib.sha256(data).hexdigest(),
        loaded_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )

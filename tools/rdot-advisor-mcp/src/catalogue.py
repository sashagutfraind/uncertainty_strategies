"""Load the public RDOT strategy catalogue (CSV, no pivotal properties) and look up entries by name."""
from __future__ import annotations

import csv
import hashlib
import io
import os
import time
from dataclasses import dataclass
from pathlib import Path

# The catalogue ships in the same repo, two levels above this tool (tools/rdot-advisor-mcp/). The server never
# downloads anything: RDOT_CSV_PATH can point at another local copy, e.g. when the tool is used outside the repo.
REPO_CSV = Path(__file__).resolve().parents[3] / "strategies_uncertainty_latest.csv"
CSV_FILE = Path(os.environ["RDOT_CSV_PATH"]).expanduser() if os.environ.get("RDOT_CSV_PATH") else REPO_CSV


@dataclass
class Strategy:
    name: str
    definition: str
    category: str
    examples: list[str]
    related: str
    notes: str
    references: list[str]


@dataclass
class Catalogue:
    strategies: list[Strategy]
    source: str
    sha256: str
    loaded_at: str

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

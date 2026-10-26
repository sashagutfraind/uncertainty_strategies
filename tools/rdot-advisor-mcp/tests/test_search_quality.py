"""Retrieval quality of search_strategies on the labeled issue queries in answer_keys.py.

Keyword search can't bridge the vocabulary gap between problem descriptions and strategy definitions, which is
why the server steers host models to list_strategies. These thresholds are regression floors, set just under
what BM25 measured when introduced (23/34 issues with a fitting strategy in the top 10; the old token-overlap
search managed 21/34).
"""
import server
from answer_keys import ANSWER_KEYS

ISSUES = [issue for issues in ANSWER_KEYS.values() for issue in issues]


def _top10(query: str) -> set[str]:
    return {s.name for s, _ in server._get_catalogue().search(query, limit=10)}


def test_answer_key_names_exist_in_catalogue():
    names = {s.name for s in server._get_catalogue().strategies}
    missing = [(i["id"], a) for i in ISSUES for a in i["acceptable"] if a not in names]
    assert not missing


def test_search_finds_a_fitting_strategy_for_most_issues():
    hits = sum(1 for i in ISSUES if _top10(i["query"]) & set(i["acceptable"]))
    assert hits >= 22, f"only {hits}/{len(ISSUES)} issues have a fitting strategy in the top 10"


def test_search_ranks_name_matches_first():
    results = server._get_catalogue().search("kill switch", limit=3)
    assert results[0][0].name == "Kill switch"


def test_list_strategies_includes_definitions():
    entries = [{"name": s.name, "definition": s.definition} for s in server._get_catalogue().strategies]
    assert all(e["definition"] for e in entries[:10])

"""Deterministic in-process tool tests, plus one real LLM-in-the-loop test (skipped without an API key)."""
import json
import os
import re

import pytest
from fastmcp import Client

import catalogue
import server
from fixtures import FIXTURES

pytestmark = pytest.mark.asyncio


async def _call(tool_name: str, **kwargs) -> list | dict:
    async with Client(server.mcp) as client:
        result = await client.call_tool(tool_name, kwargs)
    return result.data


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f["name"] for f in FIXTURES])
async def test_search_returns_catalogue_entries(fixture):
    names = {s.name for s in server._get_catalogue().strategies}
    results = await _call("search_strategies", query=fixture["goal"], limit=10)
    assert results, f"no results for goal: {fixture['goal']}"
    for entry in results:
        assert entry["name"] in names


async def test_get_strategy_known_name():
    any_name = server._get_catalogue().strategies[0].name
    entry = await _call("get_strategy", name=any_name)
    assert entry["name"] == any_name
    assert entry["definition"]


async def test_get_strategy_unknown_name_raises():
    with pytest.raises(Exception):
        await _call("get_strategy", name="definitely not a real strategy name 12345")


async def test_list_strategies_matches_catalogue_count():
    listed = await _call("list_strategies")
    assert len(listed) == len(server._get_catalogue().strategies)


async def test_catalogue_info_sane():
    info = await _call("catalogue_info")
    assert info["strategy_count"] > 50  # the public CSV has ~111 rows; a generous floor
    assert info["source"]
    assert info["loaded_at"]


@pytest.mark.skipif(not catalogue.LOCAL_CSV.exists() or catalogue.CSV_REF, reason="only inside the repo checkout")
async def test_reads_the_csv_shipped_in_the_repo():
    info = await _call("catalogue_info")
    assert info["source"] == str(catalogue.LOCAL_CSV)
    assert not info["from_cache"]


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="requires ANTHROPIC_API_KEY (test-only)")
async def test_llm_in_the_loop_stays_within_catalogue():
    """A real model, given this server's tools and instructions, should cite only real catalogue names."""
    import anthropic

    client_anthropic = anthropic.Anthropic()
    fixture = FIXTURES[0]
    catalogue_names = {s.name.lower() for s in server._get_catalogue().strategies}

    messages = [
        {
            "role": "user",
            "content": (
                f"Architecture:\n{fixture['description']}\n\nGoal: {fixture['goal']}\n\n"
                "Recommend risk-reducing strategies for this architecture. End your answer with a fenced ```json "
                'block of the form {"citations": ["<exact strategy name>", ...]} listing every strategy you recommended.'
            ),
        }
    ]

    async with Client(server.mcp) as mcp_client:
        tools = [{"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
                 for t in await mcp_client.list_tools()]
        for _ in range(8):  # bounded tool-call loop
            reply = client_anthropic.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=8000,
                system=server.INSTRUCTIONS,
                tools=tools,
                messages=messages,
            )
            tool_uses = [b for b in reply.content if b.type == "tool_use"]
            if not tool_uses:
                final_text = "".join(b.text for b in reply.content if b.type == "text")
                break
            messages.append({"role": "assistant", "content": reply.content})
            tool_results = []
            for call in tool_uses:
                result = await mcp_client.call_tool(call.name, call.input)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(result.data)}
                )
            messages.append({"role": "user", "content": tool_results})
        else:
            final_text = "".join(
                b.text for b in reply.content if b.type == "text"
            )

    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", final_text, flags=re.DOTALL)
    assert blocks, f"no citation block in: {final_text[-500:]}"
    citations = json.loads(blocks[-1])["citations"]
    assert citations, "model cited no strategies"
    for name in citations:
        assert name.lower() in catalogue_names, f"model cited '{name}', which is not in the RDOT catalogue"

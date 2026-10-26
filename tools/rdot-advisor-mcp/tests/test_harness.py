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


async def test_exposes_exactly_the_documented_tools():
    async with Client(server.mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert names == {"list_strategies", "get_strategy", "catalogue_info"}


async def test_get_strategy_known_name():
    any_name = server._get_catalogue().strategies[0].name
    entry = await _call("get_strategy", name=any_name)
    assert entry["name"] == any_name
    assert entry["definition"]


async def test_get_strategy_unknown_name_raises():
    with pytest.raises(Exception):
        await _call("get_strategy", name="definitely not a real strategy name 12345")


async def test_list_strategies_returns_whole_catalogue_with_definitions():
    listed = await _call("list_strategies")
    assert len(listed) == len(server._get_catalogue().strategies)
    assert all(entry["name"] and entry["definition"] for entry in listed)


async def test_catalogue_info_sane():
    info = await _call("catalogue_info")
    assert info["strategy_count"] > 50  # the public CSV has ~111 rows; a generous floor
    assert info["source"] == str(catalogue.CSV_FILE)
    assert len(info["sha256"]) == 64
    assert info["loaded_at"]


async def test_missing_catalogue_fails_with_clear_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="RDOT_CSV_PATH"):
        catalogue.load(tmp_path / "missing.csv")


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

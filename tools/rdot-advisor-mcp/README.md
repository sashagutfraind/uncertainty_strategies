# RDOT Advisor — MCP server (tool/data only)

Exposes the public [RDOT](https://github.com/sashagutfraind/uncertainty_strategies) strategy catalogue through MCP tools,
enabling easier use across usage scenarios, e.g.
- a human with AI coding agent (VS Code, Kiro, or anything else that speaks MCP) receives design improvements
- a fully autonomous AI coding agent consults with RDOT advisor and continues to build the solution
- a human designing physical (non-software, e.g. structural, electrical etc) system submits the design to the MCP server

## Known limits
- **Advisor is generic, not domain specific** - you are best to apply other techniques specific to your domain
- **This server does no reasoning of its own and needs no model credentials.** The connecting client's model
  reads the catalogue through these tools and writes the advice. "Recommend only RDOT strategies" is therefore
  enforced by the server's `instructions` and tool descriptions alone: a host model can still ignore them.
- **Search is lexical, not semantic.** `search_strategies` is BM25 over the catalogue text. On 34 labeled
  issue queries it puts a fitting strategy in the top 10 for 23 of them. Engineers describe problems ("race
  condition") while the catalogue describes strategies in abstract terms, and no score cutoff separates relevant
  from irrelevant results ("write a poem about cats" outscores many real queries). That is why the instructions
  send host models to `list_strategies` first; the catalogue is small enough to read whole.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/sashagutfraind/uncertainty_strategies.git
cd uncertainty_strategies/tools/rdot-advisor-mcp
uv sync
```

## Running it standalone

```bash
uv run src/server.py
```

This starts the MCP server over stdio. To try it by hand, use any MCP inspector/client, or wire it into an
editor as below.

## Connecting from VS Code

Add to `.vscode/mcp.json` in your workspace (or the equivalent user-profile file — see the
[VS Code MCP configuration reference](https://code.visualstudio.com/docs/copilot/reference/mcp-configuration)).
Note the root key is `servers`, not `mcpServers`:

```json
{
  "servers": {
    "rdot-advisor": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/uncertainty_strategies/tools/rdot-advisor-mcp", "src/server.py"]
    }
  }
}
```

Reload the MCP connection (or restart VS Code) after editing. MCP tools only run when Copilot Chat is in Agent
mode.

## Connecting from Kiro

Add to `.kiro/settings/mcp.json` in your workspace, or `~/.kiro/settings/mcp.json` for all your projects (see
[Kiro's MCP configuration docs](https://kiro.dev/docs/mcp/configuration/)). Note the root key is `mcpServers`:

```json
{
  "mcpServers": {
    "rdot-advisor": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/uncertainty_strategies/tools/rdot-advisor-mcp", "src/server.py"],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

Kiro reconnects automatically when you save the file. Check Kiro's MCP Logs (Output tab) if it doesn't show up.

## Tools exposed

| Tool | Purpose |
|---|---|
| `list_strategies()` | The whole catalogue: every strategy's name, category and definition (about 5K tokens). The recommended first call, so the host model matches problems to strategies by meaning |
| `get_strategy(name)` | One strategy's full entry (definition, category, examples, related/aliases, references) |
| `search_strategies(query, limit=10)` | Keyword (BM25) shortcut with a relevance score per result; misses strategies described in different words than the query |
| `catalogue_info()` | Which copy of the catalogue is loaded: the CSV file path, its SHA-256, load time and strategy count |

## Catalogue source

The server reads [`strategies_uncertainty_latest.csv`](../../strategies_uncertainty_latest.csv) from this repo.
It makes no network requests and writes no files; the catalogue version is the commit you have checked out, so
`git pull` gets the latest strategies, after you've had the chance to review them.

To use a different copy of the CSV, for example when running the tool outside this repo, point
`RDOT_CSV_PATH` at it:

```bash
RDOT_CSV_PATH=/path/to/strategies_uncertainty_latest.csv uv run src/server.py
```

## Testing

```bash
uv run pytest tests/
```

The deterministic tests (tool calls over the in-process catalogue, no credentials needed) always run. One
additional test — `test_llm_in_the_loop_stays_within_catalogue` — drives a real Claude model through this
server's tools against a sample architecture and asserts every strategy it cites is a real catalogue entry; it's
skipped automatically unless `ANTHROPIC_API_KEY` is set (it's a test-only dependency, never something the server
itself needs):

```bash
ANTHROPIC_API_KEY=sk-... uv run pytest tests/
```

`tests/fixtures.py` holds the three sample architectures (a payments microservice system, a healthcare data
pipeline, an internal admin tool) used by both the deterministic and the LLM-in-the-loop tests.
`tests/test_search_quality.py` measures search retrieval against labeled issue queries in
`tests/answer_keys.py`, with a regression floor.

## License

MIT, see [LICENSE](../../LICENSE).

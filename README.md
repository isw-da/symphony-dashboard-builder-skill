# Symphony Dashboard Builder Skill

A Claude Code skill for building **Logi Composer** dashboards programmatically, and for
assembling the page that embeds them. The repository name carries the old product name,
Logi Symphony, which is deprecated; the product is Logi Composer.

## What it does

Two halves, both in `SKILL.md`.

- **Server side.** A structured interview that turns "I want a dashboard showing X" into
  importable Composer JSON: sources, visuals, the dashboard layout, forced filters. It
  handles the deeply nested structures so you do not hand-write them.
- **Client side**, under `## Client-Side Assembly`. The host page: the embed SDK, the token
  exchange, the chatbot drawer, the event wiring, and the CSS that decides whether anything
  paints.

## Who it is for

Anyone at insightsoftware demoing or building on Composer who would rather describe a
dashboard than assemble its JSON, and anyone embedding a Composer dashboard in their own
page and hitting the parts the product documentation does not cover.

## Using it

Pin a tag rather than tracking `master`:

```bash
git clone --branch v0.1.0 --depth 1 https://github.com/isw-da/symphony-dashboard-builder-skill.git
```

Install as a Claude Code skill by copying the checkout into `~/.claude/skills/`, or point a
session at `SKILL.md` directly. The skill triggers when you mention Composer dashboards,
Logi Symphony dashboards, or ask to create, scope or configure a dashboard.

Example prompts:

- "Build me a KPI dashboard for sales data"
- "Create a Composer dashboard with filters and drill-through"
- "Scope a dashboard layout for embedded analytics"

**[`CONSUMING.md`](CONSUMING.md)** has the full picture: how to pin, how to run the gates,
what is deliberately not in here, and how to contribute.

## Checking it before you trust it

```bash
python3 _run/verify-against-sdk.py   # every SDK symbol taught exists in the shipped bundle
echo $?
python3 _run/verify-runnable.py      # the assembled page parses and sizes every render target
echo $?
```

Both run from a fresh clone with no Composer and no network. `verify-runnable.py` needs
`node` on PATH. Every tagged release runs both before it is cut.

## Files

- `SKILL.md`: the skill definition (interview flow, API rules, JSON templates, client-side assembly)
- `_run/embed-26.2.1.js`: the embed SDK pulled from a running Composer 26.2.1 instance, and what the SDK gate reads
- `_run/verify-against-sdk.py`, `_run/verify-runnable.py`: the two gates
- `CONSUMING.md`: how to depend on this repo
- `NOTICE`: who owns what in here. The SDK bundle is insightsoftware's, held as
  verification evidence and not offered for reuse. Read it before you copy that file
  anywhere.

## See also

Other Logi Composer / Simba Intelligence developer toolkit components in the same org:

- [`isw-da/composer-mcp`](https://github.com/isw-da/composer-mcp): MCP
  server that turns this skill's patterns into runtime tools any Claude
  session can call directly. Use it when you want Claude to drive Composer
  end-to-end rather than hand-generating JSON.
- [`isw-da/simba-intelligence-skill`](https://github.com/isw-da/simba-intelligence-skill):
  Claude skill for installing, configuring, and troubleshooting Simba
  Intelligence on Kubernetes.
- [`isw-da/edc-graphql`](https://github.com/isw-da/edc-graphql): Java
  Enterprise Data Connector that lets Composer / Simba Intelligence query
  any GraphQL API.

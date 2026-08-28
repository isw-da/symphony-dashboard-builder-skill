# Using this repo, and the others alongside it

These repositories are a shared knowledge base for insightsoftware's Logi Composer, Simba
Intelligence and Logi Report. They are maintained by Amin Hasan and anyone on the team is
welcome to clone, pin, fork or open an issue against them.

## The set

| Repo | What it holds | Refresh |
|---|---|---|
| [`isw-da/logi-si-docs`](https://github.com/isw-da/logi-si-docs) | Documentation mirror: SI, Composer v25 and v26, the legacy devnet archive, and the Composer OpenAPI specs | **Automatic**, weekly |
| [`isw-da/composer-mcp`](https://github.com/isw-da/composer-mcp) | Composer REST API as MCP tools, with guards, plus the reference docs | Manual |
| [`isw-da/simba-intelligence-skill`](https://github.com/isw-da/simba-intelligence-skill) | SI install, configuration and troubleshooting skills | Manual |
| [`isw-da/symphony-dashboard-builder-skill`](https://github.com/isw-da/symphony-dashboard-builder-skill) | Building Composer dashboards server side, and the client-side assembly around them | Manual |
| [`isw-da/simba-intelligence-mcp`](https://github.com/isw-da/simba-intelligence-mcp) | SI API as MCP tools (private) | Manual |
| [`isw-da/logi-report-kb`](https://github.com/isw-da/logi-report-kb) | Logi Report and JReport documentation and API surface (private) | Manual |

## Pin a version, do not track a branch

Every repo cuts tagged releases. The default branch moves, sometimes several times a day,
and it moves because something turned out to be wrong. Pin unless you want that.

```bash
git clone --branch v0.1.0 --depth 1 https://github.com/isw-da/symphony-dashboard-builder-skill.git
```

Release notes name what changed and, where it matters, what was found to be **wrong** in the
previous version. That second part is the useful one.

## What this repo holds

One skill, `SKILL.md`, in two halves.

- **The server-side half.** An interview that turns "I want a dashboard showing X" into
  importable Composer JSON: sources, visuals, the dashboard layout, forced filters. This is
  the half that stops you hand-writing deeply nested configuration.
- **The client-side half**, under `## Client-Side Assembly`. The page that hosts the
  dashboard: the embed SDK, the token exchange, the chatbot drawer, the event wiring and the
  CSS that decides whether anything paints at all.

`_run/embed-26.2.1.js` is the embed SDK pulled from a running Composer 26.2.1 instance. It is
committed on purpose. It is what the SDK gate reads, so the gate answers from the shipped
bundle rather than from another document that might be repeating the same mistake.

Install it as a Claude Code skill by copying the repo into `~/.claude/skills/`, or point a
session at `SKILL.md` directly.

## How to trust what you read here

Two gates, both runnable from a fresh clone with no Composer and no network:

```bash
python3 _run/verify-against-sdk.py   # every SDK symbol the skill teaches exists in embed-26.2.1.js
echo $?                              # on its own line: a pipe reports the pipe's status, not the gate's

python3 _run/verify-runnable.py      # the assembled page parses as a module and sizes every render target
echo $?
```

`verify-runnable.py` needs `node` on PATH; it uses `node --check` and nothing else.

Neither gate is decoration. Each was written after something in this skill turned out to be
confidently wrong: `trigger` documented as a method that does not exist, `forTopic` accepted
and silently ignored, `EMBED/PUBLISH` presented as an event name when the SDK carries it as
an inner discriminator, and an assembled page that hit four blockers before anything
rendered. If a gate is red, the documentation is wrong, not the gate.

Some checks report **NOT APPLICABLE** rather than passing or failing. That means the thing
they check is real but not present in your checkout, usually because it is internal material
that is never published. A skip is always named and counted, never silent.

## What is deliberately not here

- **No Composer instance, and no credentials for one.** The gates run against the committed
  SDK bundle, never against a server. Nothing here will authenticate anywhere.
- **No customer names, deployed customer artefacts, or NDA-tagged material.** Where a real
  deployment is used as evidence it appears as "deployed theme A", and the identifying copy
  stays in a private working tree.
- **No generated dashboard JSON.** The skill produces it per interview; committing a sample
  would rot against the API and invite copying rather than asking.

If you spot something that should not be public, say so and it comes out the same day.

## Contributing

Open an issue or a pull request. Two asks:

1. **Run the gates before you open it.** If your change makes a claim, the gate should be
   the thing that proves it, and if no existing check covers your claim, add one.
2. **Say how you know.** A file and line, a command and its output, a Confluence page id or
   a Jira key. "I believe" is fine as long as it says so; the corpus already contains several
   confident claims that turned out to be wrong, and each one cost somebody a day.

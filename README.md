# Symphony Dashboard Builder Skill

A Claude Code skill for building Logi Symphony (Composer) dashboards programmatically via the initial-visual API workflow.

## What it does

This skill guides you through a structured interview to define dashboard requirements, then generates importable JSON configuration files for Logi Composer. It handles the complex, deeply nested JSON structures (dashboards, visuals, sources, forced filters) so you don't have to write them by hand.

## Usage

Install as a Claude Code skill. The skill triggers when you mention Logi Symphony dashboards, Composer dashboards, or ask to create/scope/configure a dashboard.

Example prompts:
- "Build me a KPI dashboard for sales data"
- "Create a Composer dashboard with filters and drill-through"
- "Scope a dashboard layout for embedded analytics"

## Files

- `SKILL.md` — the skill definition (interview flow, API rules, JSON generation templates)

## See also

Other Logi Symphony / Simba Intelligence developer toolkit components in the
same org:

- [`isw-da/composer-mcp`](https://github.com/isw-da/composer-mcp) — MCP
  server that turns this skill's patterns into runtime tools any Claude
  session can call directly. Use it when you want Claude to drive Composer
  end-to-end rather than hand-generating JSON.
- [`isw-da/simba-intelligence-skill`](https://github.com/isw-da/simba-intelligence-skill)
  — Claude skill for installing, configuring, and troubleshooting Simba
  Intelligence on Kubernetes.
- [`isw-da/edc-graphql`](https://github.com/isw-da/edc-graphql) — Java
  Enterprise Data Connector that lets Composer / Simba Intelligence query
  any GraphQL API.

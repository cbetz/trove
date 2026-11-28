# trove skills

Claude skill bundles that wrap trove's data so an agent can answer natural-language questions about it. Two skills ship today, one per area at troveproject.com. Both are in trove plugin 1.3.0.

| Skill | Domain | Source data | When to invoke |
|-------|--------|-------------|----------------|
| [`hcris-analyst/`](hcris-analyst/) | Hospital reporting | CMS cost reports (HCRIS form 2552-10, FY2022 and FY2023 files, incl. Worksheet S-10), IRS 990 Schedule H (tax year 2022), CCN↔EIN crosswalk, CDC SVI | A hospital's IRS line 7a and CMS S-10 line 23 side by side with the components each filing publishes; the ranked index; a hospital's cost-report profile; glossary lookups (worksheet/line/column); NL→SQL over the published Parquet bundles |
| [`fda-analyst/`](fda-analyst/) | FDA drug approvals | Index of 331 FDA novel drug approvals 2021–2026 (295 CDER + 36 CBER); reads approval-package PDFs at query time | "What was the basis for [drug] approval?", "What adverse events did the FDA flag?", "Was this drug approved via accelerated approval?" |

Each skill is self-contained: a `SKILL.md` (frontmatter + instructions), a `references/` directory (data layout, glossary, examples, etc.), and no Python dependencies. The skills query trove's published bundles at `https://troveproject.com/data/` with DuckDB (or `curl` and the Python standard library), and fetch FDA PDFs at runtime. No local trove install is required.

Every query in `hcris-analyst/references/` is run against the current bundles before a release. The skill checks that the bundle it reaches has the current columns and says so if it meets an older build.

## Install (Claude Code, plugin path)

trove is packaged as a Claude Code plugin in this repo (`.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`). Inside Claude Code:

```
/plugin marketplace add anthropics/claude-plugins-community
/plugin install trove@claude-community
```

This is the canonical install path through Anthropic's public community marketplace. Plugin install gives you versioning, namespaced commands (`/trove:hcris-analyst`, `/trove:fda-analyst`), and marketplace-managed updates. This is the community marketplace (`claude-community`), not the separate official `claude-plugins-official` marketplace.

Already installed? Refresh the marketplace with `/plugin marketplace update claude-community`, then update trove from the `/plugin` menu. The version is set in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`; bump both together.

## Install (Claude Code, filesystem path)

If you'd rather copy the skill directories directly (bypasses the plugin layer, useful for development or for environments without the plugin command):

```bash
git clone https://github.com/cbetz/trove
cp -r trove/skills/hcris-analyst ~/.claude/skills/
cp -r trove/skills/fda-analyst ~/.claude/skills/
```

Restart Claude Code and the skills load. Each skill's `description` field tells Claude when to invoke — no need to call them by name.

To install just one skill, copy only that subdirectory. To install for a single project rather than user-wide, use `.claude/skills/` inside the project root instead of `~/.claude/skills/`.

## Install (Claude.ai)

Claude.ai supports skills via uploaded skill bundles. Zip the skill directory you want and upload through the Claude.ai skills UI:

```bash
cd skills && zip -r hcris-analyst.zip hcris-analyst
```

## What each skill needs

Both skills read trove's public bundles served from troveproject.com. No local trove repo or Python environment is required.

- **Network.** The skills need to reach `troveproject.com`; `fda-analyst` also needs `www.accessdata.fda.gov` and `www.fda.gov`. Some sandboxes (claude.ai and Cowork code execution among them) only reach allow-listed domains. The fallback for the data bundles is `git clone --depth 1 https://github.com/cbetz/trove` and reading `trove/web/data/`; FDA documents have no mirror.
- **A query engine.** DuckDB (`duckdb` CLI, or `uv run --with duckdb python`). Without it, `hcris-analyst` falls back to the JSON bundles with `curl` and `python3`.
- **Local data.** With the repo cloned, both skills can read `web/data/` by path instead of over HTTPS.

## Authoring conventions

If you want to add a new skill (matching trove's pattern):

- One skill per area. Narrow scope = better invocation accuracy.
- `SKILL.md` frontmatter has `name` and `description`. The description should describe both the domain and the type of question — Claude uses it to decide when to invoke.
- `references/` for data layout, glossary, examples. Keep them readable as standalone Markdown.
- Put query examples in `references/examples.md` rather than inline in `SKILL.md`. The skill loader doesn't always pull example content into context, but the references directory is browsable.
- Cite sources for any data the skill outputs.
- Do not advertise data the bundles do not hold. Check each claimed column against the published schema.
- Test every query in the skill against the current bundles, in both bash and zsh for shell snippets, before bumping the plugin version.

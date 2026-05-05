# trove skills

Claude skill bundles that wrap trove's data so an agent can answer natural-language questions about it. Two skills ship today — one per area at troveproject.com — and adding new skills as new areas land is the same pattern.

| Skill | Domain | Source data | When to invoke |
|-------|--------|-------------|----------------|
| [`hcris-analyst/`](hcris-analyst/) | Hospital reporting | HCRIS Worksheet S-10, IRS 990 Schedule H, CCN↔EIN crosswalk, CDC SVI | Profile a hospital, peer-compare, glossary lookups (worksheet/line/column), reconciliation gap detection, NL→SQL over the published Parquet bundles |
| [`fda-analyst/`](fda-analyst/) | FDA drug approvals | Index of FDA Novel Drug Approvals 2021–2024; reads approval-package PDFs at query time | "What was the basis for [drug] approval?", "What adverse events did the FDA flag?", "Was this drug approved via accelerated approval?" |

Each skill is self-contained: a `SKILL.md` (frontmatter + instructions), a `references/` directory (data layout, glossary, examples, etc.), and no Python dependencies. The skills query trove's published Parquet bundles directly over HTTPS via DuckDB or fetch FDA PDFs at runtime — no local trove install required.

## Install (Claude Code, plugin path)

trove is packaged as a Claude Code plugin in this repo (`.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`). Inside Claude Code:

```
/plugin marketplace add cbetz/trove
/plugin install trove@trove
```

This is the canonical install path. Plugin install gives you versioning, namespaced commands (`/trove:hcris-analyst`, `/trove:fda-analyst`), and auto-updates from git. The plugin will also be listed in the official marketplace at <https://claude.com/plugins> once Anthropic completes the submission review.

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

Both skills query trove's public Parquet bundles served from troveproject.com — no local trove repo or Python environment required for the skill to work. The data layer is fully separable from the skill bundle.

If you have the trove repo cloned locally and want the skills to use your local Parquet directly (faster for repeated queries), the `hcris-analyst` references explicitly call this out as an alternative path. The `fda-analyst` skill always fetches FDA PDFs at runtime regardless of local state.

## Authoring conventions

If you want to add a new skill (matching trove's pattern):

- One skill per area. Narrow scope = better invocation accuracy.
- `SKILL.md` frontmatter has `name` and `description`. The description should describe both the domain and the type of question — Claude uses it to decide when to invoke.
- `references/` for data layout, glossary, examples. Keep them readable as standalone Markdown.
- Put query examples in `references/examples.md` rather than inline in `SKILL.md`. The skill loader doesn't always pull example content into context, but the references directory is browsable.
- Cite sources for any data the skill outputs.

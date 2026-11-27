# 25 — For facts that change, check the live source, not blogs or memory

## The lesson
Versions, prices, availability, "latest release", "is it free": these change weekly. Blog posts and your own memory are snapshots. **Check the live source** (official API, registry, release page) before you recommend anything.

## What happened here
- **Free models:** guides from mid-2026 recommended `qwen3-coder:free`, Cohere North Mini Code and DeepSeek V4 Flash. Claude pulled OpenRouter's **live** model list (`/api/v1/models`, 477 models, 15 free) and found that **none of those three were still free**. The recommendation (`nvidia/nemotron-3-ultra-550b-a55b:free`, `recursive/flint-v1.0:free`) came from the live list, with tool support checked.
- **native-dawn:** before suggesting "just upgrade the package", Claude checked the npm registry: **0.1.6 is the latest** (2026-10-16). No upgrade exists, so the plan uses the shader rewrite instead.
- **Dawn fix dates:** the fix landed 2026-09-01. Our pinned Dawn revision is 2026-08-22, confirmed from the package's `upstream.json` and the commit date. A version comparison, not a guess.

## How to apply
- Use machine-readable sources: package registries (`registry.npmjs.org/<pkg>`), vendor APIs, `--version`, release/commit logs.
- Write the date you checked ("checked 2026-11-25").
- When blogs disagree with the live source, trust the live source and say so.
- Don't send private data (project names, emails) in these requests. Use plain public queries.

## One-line rule
**For anything that changes, the only true answer is today's live one.**

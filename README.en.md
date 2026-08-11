[Deutsch](README.md) | **English**

# <img src="docs/pbp.png" alt="PBP logo" width="36" align="absmiddle" /> PBP — Persönliches Bewerbungs-Portal

**PBP is a job application assistant for the German-speaking job market (DACH). It runs entirely on your machine — free, open source, no cloud.**

![PBP dashboard](docs/screenshots/01_dashboard.png)

## Honest scope note

PBP is a German-language product for people applying to jobs in Germany, Austria and Switzerland. The UI, the workflows, the job portal integrations and the documentation are German — and that is deliberate: cover letters, CV conventions and job boards are deeply local. If that is your job market, switch to the [German README](README.md).

If you do not speak German, the interesting part of this repo is the architecture.

## Why this repo might still interest you

PBP is a complete, self-hosted **MCP server** (Model Context Protocol) written in Python (FastMCP), paired with a React 19 dashboard and a single-file SQLite database:

- **202 MCP tools** covering profile management, job search, application tracking, document analysis, calendar, statistics and guided workflows
- **35 configured job sources** with honest health checks — flaky scrapers are visibly flagged instead of failing silently
- **Local-first by design** — one SQLite file holds all data; nothing leaves the machine except what the user deliberately sends to their LLM
- **Claude Desktop as the interface** — no custom chat UI; conversation, voice input and tool calls come for free via MCP
- **Local LLM sidecar** (Ollama) for background classification and scoring, so routine work costs no cloud tokens
- **2199 automated tests**, weekly releases

Version **v1.7.12** · last release 2026-08-11 · MIT license

## Fork it for your job market

The concept — a local MCP server that manages applications, watches job boards and gives honest feedback on CVs — transfers to any country. Scraper adapters, scoring rules and the document pipeline are pluggable. If you would like to build an equivalent for your market, fork the repo or [open an issue](https://github.com/MadGapun/PBP/issues) — questions are answered in English too.

## Quick facts

| | |
|---|---|
| Platforms | Windows, macOS, Linux |
| Interface | Claude Desktop (MCP) + local web dashboard |
| Storage | Single SQLite file (WAL mode) |
| Cost | Free (MIT license); optional Claude Pro for heavy daily use |
| Product language | German — see the [German README](README.md) for the full feature tour |

---

[Deutsch](README.md) | **English**

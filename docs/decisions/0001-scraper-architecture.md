---
adr: "0001"
title: Three-stage pipeline architecture for course scraper
status: Accepted
date: 2025-05-20
deciders: [bo, styx]
type: decision
tags: [adr, architecture]
supersedes: []
superseded-by: []
related: ["0002", "0003"]
---

# ADR-0001: Three-stage pipeline architecture

## Context

Need to scrape SkillFactory Open edX course (848 units, 1193 assets, 208 video recordings) into an offline Obsidian vault. Different content types have different access patterns, sizes, and failure modes:

- Lectures (text/HTML) — requires auth, fast, small (~20 MB total)
- Assets (images/PDF) — CDN without auth, medium (~500 MB)
- Videos (HLS/Kinescope) — requires Referer bypass + ffmpeg, large (~10-50 GB)

Running all in one pass creates poor UX: user waits hours before seeing any result, failures in video don't affect text content.

## Decision

We will split the scraper into **three independent stages** executed sequentially:

1. **Stage 1 (scrape)** — API structure → markdown files with wikilinks and tags
2. **Stage 2 (assets)** — download CDN resources → `_assets/`, rewrite links to local
3. **Stage 3 (videos)** — discover kinescope iframes → download via ffmpeg → link into notes

Each stage is idempotent and can be run independently. Each skips already-completed work.

## Alternatives considered

| Alt | Pros | Cons | Why rejected |
|---|---|---|---|
| Single-pass (download everything inline) | Simpler code | 10+ hour monolith, can't resume, no partial result | UX unacceptable |
| Async pipeline (stream all concurrently) | Fastest | Complex error handling, CDN/API rate limits, hard to debug | Over-engineered for 1-time scrape |
| External tool (yt-dlp + wget + custom glue) | Less code | No Obsidian-native linking, no frontmatter, poor Graph View | Doesn't meet Obsidian requirement |

## Consequences

### Positive
- User gets readable vault after 4 min (Stage 1 only)
- Each stage can fail independently without data loss
- Classmates can skip Stage 3 (videos) to save disk space
- Incremental: re-running skips existing files

### Negative / costs
- Three passes over vault for link rewriting
- Stage ordering matters (1 before 2 before 3)

### Neutral
- CLI wizard guides through stages sequentially

## Reversal triggers

- If Open edX API changes to require different auth per content type
- If Kinescope moves away from HLS to DRM-only delivery

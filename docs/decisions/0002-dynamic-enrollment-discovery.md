---
adr: "0002"
title: Dynamic course discovery via enrollments API
status: Accepted
date: 2025-05-21
deciders: [bo, styx]
type: decision
tags: [adr, architecture]
supersedes: []
superseded-by: []
related: ["0001"]
---

# ADR-0002: Dynamic course discovery via enrollments API

## Context

Initially scraper had hardcoded course IDs (main, pentest, compliance). But users may have different enrollments — free courses (Linux, SQL), session exams, career tracks. Hardcoding forces code changes for each new user.

## Decision

We will fetch `/api/enrollment/v1/enrollment` at runtime to discover all available courses. The wizard presents the full dynamic list. Stage 3 (videos) scans all enrolled courses without assumptions about which ones have recordings.

## Consequences

### Positive
- Works for any user's enrollment set
- New courses auto-discovered without code changes
- No misleading "Scanning: compliance... Found 0" for users without compliance track

### Negative
- Extra API call at startup (~1s)
- Free courses (often empty) pollute the list

### Neutral
- `--track` CLI flag still works for known keys (main/pentest/compliance)

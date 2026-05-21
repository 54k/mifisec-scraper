---
adr: "0003"
title: Obsidian vault structure with semester hierarchy and Graph View
status: Accepted
date: 2025-05-20
deciders: [bo, styx]
type: decision
tags: [adr, structure, obsidian]
supersedes: []
superseded-by: []
related: ["0001"]
---

# ADR-0003: Obsidian vault structure

## Context

Course has 30 chapters across 4 semesters, plus tracks and DPO. Flat structure makes Graph View unreadable (all nodes labeled "_section"). Need hierarchy that maps to both filesystem navigation (sidebar) and graph topology.

## Decision

Hierarchy: `index → semester hubs → discipline MOCs → section aggregates → unit lessons`

```
vault/
├── index.md                    (type/index — red, largest)
├── Семестр N/                  (type/semester-hub — gold)
│   ├── Семестр N.md
│   └── NN. Discipline/
│       ├── Discipline.md       (type/moc — yellow)
│       └── NN. Section/
│           ├── Section.md      (type/module)
│           └── NN. Unit.md     (type/lesson)
├── Трек Пентест/               (type/track-hub — pink)
├── _assets/                    (images, PDF, PPTX)
└── _videos/                    (mp4 recordings)
```

Tags in frontmatter drive Graph View coloring via `.obsidian/graph.json`.

## Alternatives considered

| Alt | Why rejected |
|---|---|
| Flat (all files in root) | Graph unreadable, no hierarchy |
| By chapter number only | No semester grouping, duplicates across runs |
| Obsidian Canvas/MOC only | Requires manual maintenance |

## Consequences

- Graph View shows clear clusters by semester with distinct colors
- Sidebar matches logical structure of the program
- Numbering within semester (not global) prevents duplicate directories
- `graph.json` must be rewritten if Obsidian clears it (`--fix-graph`)

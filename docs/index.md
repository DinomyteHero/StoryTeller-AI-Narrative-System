# Storyteller V3 — Project Guide

**Version:** 3.0
**Date:** April 8, 2026
**Purpose:** Front-door orientation for the entire project. Document
architecture, reading order, authority rules, and navigation.

---

## What This Is

An LLM-powered Star Wars narrative RPG engine using the FFG dice
system. The player reads prose, makes choices, and the story responds
— mechanically real (dice determine outcomes) and narratively generative
(an LLM writes the prose). Two independent systems share one repo:

- **Game Engine** — runtime. Consumes campaign spine JSON and plays it.
- **Campaign Studio** — authoring tool. Produces campaign spine JSON.

The campaign spine JSON is the interface contract between them.

---

## Document Architecture

The project documentation is organized into four tiers plus API
reference and a reference archive. Each tier serves a distinct
audience and purpose.

### Tier 1 — Core Specifications (`docs/specs/`)

The canonical design and implementation specs. If you are building or
reviewing the system, these are the documents you need.

| Document | Authoritative For | When to Read |
|----------|------------------|--------------|
| **[Vision](specs/vision.md)** | Creative intent, player experience goals, design philosophy. What the game should *feel* like. | Read for context and intent. Not for implementation detail. |
| **[Game Mechanics](specs/game-mechanics.md)** | How every mechanical system works. 27 sections (§0-§26). The bridge between creative vision and code. | Reference as needed. §0-§19, §23-§26 cover built systems. §20-§22 cover unbuilt systems. |
| **[Game Engine Implementation](specs/engine-implementation.md)** | Game Engine code: file-by-file specs, V1 build phases 1-6, prompt templates, database schema, orchestration flows. | Read fully before writing Game Engine code. |
| **[Campaign Studio Design](specs/studio-design.md)** | Campaign authoring methodology, three automation modes, spine JSON format, saga layer architecture, validation suite, cross-era import. | Read when working on campaign authoring or the Studio system. |
| **[Campaign Studio Implementation](specs/studio-implementation.md)** | Campaign Studio code: tech stack, Pydantic schema, pipeline stages, build phases CS-1 through CS-6. | Read fully before writing Campaign Studio code. |

### Tier 2 — Planning and Status (`docs/status/`)

Build sequencing and item tracking. These documents govern *when*
things get built and track *whether* they are done.

| Document | Authoritative For | When to Read |
|----------|------------------|--------------|
| **[Build Roadmap](status/roadmap.md)** | Phased build plan. V1 phases 1-6, post-V1 phases 7-22, four milestones, success criteria per phase. | Read to understand build order and phase dependencies. |
| **[Backlog](status/backlog.md)** | Single source of truth for every tracked item — status, design completeness, alignment notes, pending decisions. | Read to check the status of any feature or item. |
| **[Project State Matrix](status/state-matrix.md)** | Compact capability dashboard. One row per capability: promised, designed, built, deferred. | Read for a single-page status overview. |
| **[Changelog](status/changelog.md)** | What changed and when. Standard changelog format. | Read for release history. |

### Tier 3 — Research and Evaluation (`docs/research/`)

Evidence basis and model selection. These documents are consulted when
making LLM or design decisions.

| Document | Authoritative For | When to Read |
|----------|------------------|--------------|
| **[LLM Evaluation](research/llm-evaluation.md)** | Model selection, tier rankings, compliance test protocol, cost estimates, active configuration. | Read when configuring LLM providers or evaluating models. |
| **[Research Catalogue](research/research-catalogue.md)** | Institutional memory: 13 external sources with TAKE/REJECT rationale and design impact tracking. | Read when investigating the research basis for a design decision. |

### Tier 4 — Specialist Specifications (`docs/specialist/`)

Standalone specs for systems that are narrow enough to warrant their
own document. Each is authoritative for its specific scope. Consult
when implementing the relevant phase.

| Document | Scope | Build Phase |
|----------|-------|-------------|
| **[Choice Quality Validation](specialist/choice-quality-validation.md)** | Post-generation choice quality validator: 5-dimension rubric, local model evaluator, retry integration. | Late Phase 3 or Phase 7 |
| **[Prologue System](specialist/prologue-system.md)** | Psychometric prologue: design robustness (contradictions, confidence, anti-gaming) + implementation plan. | Phase 18 |
| **[Import Package Quality](specialist/import-package-quality.md)** | Cross-campaign character import: narrative compression quality standards. | Phase 19 |
| **[Story Architecture](specialist/story-architecture.md)** | Campaign spine dramatic quality: vocabulary, rubrics, Gate 4 evaluation. Extended with dramatic mission types and scene purpose validation in CS-6. | CS-5 + CS-6 (complete) |

### API Reference (`docs/api/`)

HTTP endpoint documentation for both systems.

| Document | Scope |
|----------|-------|
| **[Game Engine API](api/game-engine-api.md)** | 11 endpoints: session management, turn handling, Force mechanics, talents, time skips. |
| **[Campaign Studio API](api/studio-api.md)** | 13 endpoints: spine validation, AI-assisted generation, cross-era import, campaign storage. |

### Reference Archive — `docs/reference/`

Archived material preserved for traceability. **Not authoritative.**
Design content has been applied to canonical documents.

| Document | Original Purpose | Why Archived |
|----------|-----------------|-------------|
| `design-gap-analysis-v2.md` | Design specs for 9 items not covered elsewhere. | All designs complete and applied. Consult when implementing those specific Backlog items. |
| `deferred-design-analysis.md` | 2 deferred designs + full system logic walkthrough. | Designs applied to GM v1.8. Section 4 (logic analysis) remains a useful architecture reference. |
| `claude-code-initial-prompt.md` | Setup prompt for Claude Code sessions. | Superseded by `CLAUDE.md` in the repo root. |
| `prose-quality-review-1.md` | Playtest transcript (Echoes of the Force, Talia Ren). | Historical data artifact, not a specification. |
| `consolidation-report.md` | Record of April 5, 2026 documentation reorganization. | One-time audit artifact. |

---

## Reading Order

### If you are implementing (start here)

1. **Game Engine Implementation** — the primary code spec. Read fully
   before writing any code.
2. **Build Roadmap** — phased plan with success criteria. Determines
   what to build and in what order.
3. **Game Mechanics** — reference as needed. §0-§19, §23-§26 cover
   implemented systems. §20-§22 are not yet built.
4. **Vision** — creative context. Read for intent, not for
   implementation detail.

These four documents are sufficient for most Game Engine work. Add
Campaign Studio Design + Implementation when working on the Studio.

### If you are reviewing the design

1. **This guide** — orientation and authority map.
2. **Vision** — what the game promises.
3. **Game Mechanics** — how those promises become systems.
4. **Game Engine Implementation** — how the systems become code.
5. **Campaign Studio Design** — how campaigns are authored.
6. **Backlog** — current state of every tracked item.

### If you are auditing completeness

1. **Backlog** — the Document Status Summary and Alignment Notes
   sections are the operational state of the project.
2. **Project State Matrix** — compact capability view.
3. **Reference archive** — `reference/design-gap-analysis-v2.md`
   confirms every designable item has been designed.
   `reference/deferred-design-analysis.md` verifies data flows,
   invariants, and integration points.

---

## Authority Resolution Rules

When documents touch overlapping topics, these rules determine which
governs:

**Mechanical design questions** (how a system works, what triggers it,
what data it consumes and produces) -> Game Mechanics is authoritative.
Implementation and Campaign Studio *implement* what Game Mechanics
*defines*.

**Code-level questions** (function signatures, module boundaries, prompt
template text, database schema) -> Implementation (Game Engine) or
Campaign Studio Implementation, depending on which system.

**Creative and experiential questions** (what the player should feel,
what quality the prose should reach, what the choices should
accomplish) -> Vision is authoritative.

**Item status and tracking** (is something designed, is it deferred,
what phase is it in) -> Backlog is authoritative.

**Model selection and compliance testing** -> LLM Evaluation is
authoritative.

**Specialist topics** (choice validation, prologue robustness, import
quality, story architecture) -> the relevant Tier 4 spec is
authoritative for its stated scope.

**API endpoints** -> The API reference docs are authoritative for
request/response schemas. The route source files
(`api/game_routes.py`, `api/studio_routes.py`) are the code-level
authority.

---

## Implementation Status

For current, detailed project status, consult the
**[Backlog](status/backlog.md)** and
**[Changelog](status/changelog.md)**.

---

## What Is Designed vs. Built vs. Deferred

A common review pitfall is mistaking a designed-but-not-built item for
a missing design. The project explicitly distinguishes:

**Built** — Implementation exists and has been verified. Milestones
0-3 and Campaign Studio CS-1 through CS-6 are in this category. See
Project State Matrix for a row-by-row view.

**Designed and ready for implementation** — Full spec exists. Build
when the phase arrives. Examples: psychometric prologue (GM §5,
Phase 18), large-scale NPC management (GM §21, Phase 20), canon
character profiles (GM §22, Phase 21), Force discovery (GM §14.4,
Phase 22).

**Intentionally deferred** — Acknowledged as future work. Not
implementation-ready but not forgotten. Examples: Phase 5 aspirations
(5.1-5.6), multiplayer.

**Open research questions** — Require empirical data from runtime play
before design is possible. Examples: R.1-R.7 in the Backlog.

---

## Key Architectural Invariants

These invariants are non-negotiable across the entire project. Any
change that violates them is a bug.

**Physics-before-imagination.** Code resolves all mechanical outcomes
(dice, state transitions, NPC disposition changes) before the narrative
model receives the context package. The LLM describes outcomes code has
already determined. It never decides them.

**One cloud call per turn.** The turn loop makes exactly one cloud LLM
call for narration. All other LLM calls within the turn loop are local.
Between-act processing may make additional cloud calls, but those are
outside the turn loop.

**The dice are the truth.** Failure is narrated as failure. Triumph is
narrated as triumph. No softening, no reinterpretation.

**The campaign spine is the contract.** The Game Engine and Campaign
Studio communicate exclusively through the campaign spine JSON. The
Engine does not know how the spine was produced. The Studio does not
know how the spine is consumed.

**The character is the primary entity.** Campaigns are chapters in a
character's story, not containers that own characters.

---

## Quick Reference: Where to Find Things

| Question | Go to |
|----------|-------|
| How do FFG dice work in this system? | GM §3 |
| What does the narration prompt look like? | Impl §7.1 |
| What's the turn loop? | Impl §9.1 |
| How does the check decision work? | GM §3, Impl §6 |
| What's in the context package? | Impl §7.2 |
| How are NPCs tracked? | Vision §11, GM §25 |
| How does character advancement work? | GM §14 |
| How do motivation tracks work? | Vision §10, GM §9, §26 |
| What's the character funnel? | Vision §8, GM §5, CS Design §2.5-2.6 |
| How does cross-era import work? | GM §20, CS Impl §6 |
| What's the Writer's Room? | CS Design §3 |
| What models are we using? | LLM Eval §§5-8 |
| What's the compliance test? | LLM Eval §11 |
| What's the build order? | Build Roadmap, then Impl phases 1-6 |
| Is feature X designed? | Backlog (search by item number) |
| What's the spine JSON format? | CS Design §4, CS Impl §4.1 |
| What are the validation rules? | CS Design §5 |
| Prologue edge cases? | Prologue System Spec (Part A) |
| Choice quality validation? | Choice Quality Validation Spec |
| Import quality standards? | Import Package Quality Spec |
| Story architecture rubrics? | Story Architecture Spec |
| Game Engine endpoints? | API: Game Engine API reference |
| Studio endpoints? | API: Campaign Studio API reference |

---

## Superseded Materials

The following earlier documents have been fully absorbed and are no
longer part of the project:

| Document | Superseded By |
|----------|--------------|
| RESEARCH_SCOPING.md | Research Catalogue v1.0 (removed from project) |
| SAGA_RESEARCH_FINDINGS.md | Research Catalogue v1.0 (removed from project) |
| Design Gap Analysis v1.1 | Design Gap Analysis v2.0 (in `reference/`) |
| PROLOGUE_INFERENCE_SPEC.md | Prologue System Spec v1.0 (merged) |
| PHASE_18_IMPLEMENTATION_PLAN.md | Prologue System Spec v1.0 (merged) |

---

## Revision History

**v3.0 — Documentation reorganization (April 8, 2026)**

Major restructure. Moved from flat `docs/` directory to tier-based
subdirectories (`specs/`, `status/`, `research/`, `specialist/`,
`api/`, `reference/`). Renamed all files from SCREAMING_CASE to
lowercase-kebab-case, dropped `STORYTELLER_V3_` prefix. Added API
reference docs (Game Engine + Studio). Added CHANGELOG.md. Added
CONTRIBUTING.md. Updated all cross-references. Added CS-6 awareness.
Replaced inline status summary with pointer to backlog/changelog.

**v2.0 — Documentation consolidation (April 5, 2026)**

Replaced flat document list with four-tier architecture. Created
`docs/reference/` for archived artifacts. Merged prologue specs.

**v1.3 — Documentation audit sync (March 17, 2026)**

Added codebase metrics. Corrected cloud model reference.

**v1.2 — Post-milestone documentation sync (March 8, 2026)**

Updated for Milestones 0-3 completion and CS-1 through CS-4.

**v1.1 — Initial guide (March 6, 2026)**

Initial document.

---

*Storyteller V3 — Project Guide v3.0*
*The front door. Start here.*

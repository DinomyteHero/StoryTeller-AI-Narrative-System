# Storyteller V3 — Project Guide

**Version:** 1.1  
**Date:** March 6, 2026  
**Purpose:** Front-door orientation for the entire project. Reading
order, document authority, current state, and navigation.

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

## Document Authority Map

Each document owns a specific question. When two documents touch the
same topic, the authority column says which one governs.

| Document | Owns | Version | Size |
|----------|------|---------|------|
| **Vision** | What the game should feel like. Creative intent, player experience goals, design philosophy. | v3.1 | 98K |
| **Game Mechanics** | How the game works in practice. 27 sections (§0–§26) covering every mechanical system from dice resolution to cross-era character progression. | v1.8 | 299K |
| **Implementation** | How the Game Engine code is structured. File-by-file specs, V1 build phases 1–6, prompt templates, database schema, orchestration flows. | v2.5 | 149K |
| **Campaign Studio Design** | How campaigns are authored and validated. Writer's Room methodology, three automation modes, spine JSON format, saga layer architecture, validation suite, cross-era import. | v1.3 | 62K |
| **Campaign Studio Implementation** | How Campaign Studio code is structured. Tech stack, repo structure, Pydantic schema, pipeline stages, database additions, import interface. | v1.3 | 45K |
| **Build Roadmap** | Phased build plan. V1 phases 1–6, post-V1 phases 7–22, four milestones, success criteria per phase. | v1.1 | 31K |
| **LLM Evaluation** | Model selection and compliance testing. Model landscape, tier assessments, five-category compliance test protocol, cost estimates, Campaign Studio model roles. | v2.0 | 39K |
| **Backlog** | Single source of truth for every tracked item. Status of every feature, design completeness, alignment notes, pending decisions, document status summary. | v2.9 | 68K |
| **Design Gap Analysis** | Full design specifications for items not covered in Game Mechanics or Implementation. v2.0 supersedes v1.1. Nine post-v1.1 design specs plus all v1.1 items (marked APPLIED). | v2.0 | 72K |
| **Deferred Design and Logic Analysis** | System logic walkthrough. Turn loop verification, data flow analysis, invariant proofs, token budget analysis, post-V1 integration point mapping. | v1.0 | 35K |
| **Research Catalogue** | Evidence basis. 13 external sources across four research domains. TAKE/REJECT decisions with rationale per source per target system. | v1.0 | 39K |
| **Project State Matrix** | Compact view of every capability's status: promised, designed, V1-scoped, deferred. Prevents misclassifying designed-but-not-built items as missing. | v1.1 | — |
| **Choice Quality Validation Spec** | Post-generation choice quality validator. Five-dimension rubric, local model evaluator, retry integration, calibration protocol. | v1.0 | — |
| **Prologue Inference Spec** | Robustness rules for the psychometric prologue. Contradiction handling, confidence scoring, anti-gaming, fallback behavior, scene library diversity. | v1.0 | — |
| **Import Package Quality Spec** | Quality standards for narrative compression in cross-campaign character transfer. Relationship summaries, throughline history, voice notes, memory shards. | v1.0 | — |

---

## Reading Order

### If you are implementing (start here)

1. **Implementation** — the primary code spec. Read fully before
   writing any code.
2. **Build Roadmap** — phased plan with success criteria. Determines
   what to build and in what order.
3. **Game Mechanics** — reference as needed. §0–§13 are V1-relevant.
   §14–§26 are post-V1.
4. **Vision** — creative context. Read for intent, not for
   implementation detail.

These four documents are sufficient for most implementation work.

### If you are reviewing the design

1. **This guide** — orientation and authority map.
2. **Vision** — what the game promises.
3. **Game Mechanics** — how those promises become systems.
4. **Implementation** — how the systems become code.
5. **Campaign Studio Design** — how campaigns are authored.
6. **Backlog** — current state of every tracked item.

### If you are auditing completeness

1. **Backlog** — the Document Status Summary and Alignment Notes
   sections are the operational state of the project.
2. **Design Gap Analysis v2.0** — confirms every designable item has
   been designed.
3. **Deferred Design and Logic Analysis** — verifies data flows,
   invariants, and integration points.

---

## Authority Resolution Rules

When documents touch overlapping topics, these rules determine which
governs:

**Mechanical design questions** (how a system works, what triggers it,
what data it consumes and produces) → Game Mechanics is authoritative.
Implementation and Campaign Studio *implement* what Game Mechanics
*defines*.

**Code-level questions** (function signatures, module boundaries, prompt
template text, database schema) → Implementation (Game Engine) or
Campaign Studio Implementation, depending on which system.

**Creative and experiential questions** (what the player should feel,
what quality the prose should reach, what the choices should
accomplish) → Vision is authoritative.

**Item status and tracking** (is something designed, is it deferred,
what phase is it in) → Backlog is authoritative.

**Design specs for items not fully covered in Game Mechanics** →
Design Gap Analysis v2.0 is authoritative.

**Model selection and compliance testing** → LLM Evaluation is
authoritative.

---

## Current Project State (March 6, 2026)

**Design completeness:** Every item within the current planning horizon
has been fully designed. Zero items with status NEEDS DESIGN,
PARTIALLY DESIGNED, CONCEPT ONLY, CONSIDER, or FILED remain. Only
Phase 5 long-term aspirations (5.1–5.6) and open research questions
(R.1–R.7) are without design, by explicit choice.

**Implementation completeness:** No code has been written. Phase 1
(pure Python dice engine) is the next action.

**Known open items:**

| Item | Status | Tracking |
|------|--------|----------|
| LLM Evaluation needs Category 6 (behavioral envelope compliance) in test protocol | Flagged | Backlog Document Status Summary |
| Active cloud model for V1 pending head-to-head test | Open decision D.2 | Backlog Pending Decisions |
| DeepSeek V4 and Qwen3.5-397B model monitoring | Watching | Backlog 1.40, 1.41 |

---

## What Is Designed vs. Built vs. Deferred

A common review pitfall is mistaking a designed-but-not-built item for
a missing design. The project explicitly distinguishes:

**Designed and ready for implementation** — Full spec exists. Build
when the phase arrives. Examples: conditional choice availability
(Deferred Design §2), reputation echo delivery (Deferred Design §1),
psychometric prologue (GM §5), all Phase 2+ backlog items marked
DESIGNED.

**Architecture reserved in V1** — Schema fields, pipeline stages, or
data structures that exist in V1 but are empty or null. They ensure
post-V1 systems don't require structural changes. Examples:
`prose_diagnostic` on ContextPackage, `sequence` on ContextPackage,
`reputation_log` table, `moral_weight` column on turns.

**Intentionally deferred** — Acknowledged as future work. Not
implementation-ready but not forgotten. Examples: Phase 5 aspirations
(5.1–5.6), multiplayer.

**Open research questions** — Require empirical data from runtime play
before design is possible. Examples: R.1–R.7 in the Backlog.

The Backlog's status definitions and the Design Gap Analysis v2.0
appendix provide the complete picture.

---

## Superseded and Archived Materials

The following documents are superseded and should not be treated as
current:

| Document | Superseded By | Notes |
|----------|--------------|-------|
| RESEARCH_SCOPING.md | Research Catalogue v1.0 | All content absorbed. Removed from project files. |
| SAGA_RESEARCH_FINDINGS.md | Research Catalogue v1.0 | All content absorbed. Removed from project files. |
| Design Gap Analysis v1.1 | Design Gap Analysis v2.0 | v1.1 items retained in v2.0 Section A (marked APPLIED). v2.0 is the only current source. |

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
| What's the turn loop? | Impl §9.1, Deferred Design §4.1 |
| How does the check decision work? | GM §3, Impl §6 |
| What's in the context package? | Impl §7.2 |
| How are NPCs tracked? | Vision §11, GM §25 |
| How does character advancement work? | GM §14 |
| How do motivation tracks work? | Vision §10, GM §9, §26 |
| What's the character funnel? | Vision §8, GM §5, CS Design §2.5–2.6 |
| How does cross-era import work? | GM §20, CS Impl §6 |
| What's the Writer's Room? | CS Design §3 |
| What models are we using? | LLM Eval §§5–8 |
| What's the compliance test? | LLM Eval §11 |
| What's the build order? | Build Roadmap, then Impl phases 1–6 |
| Is feature X designed? | Backlog (search by item number) |
| What's the spine JSON format? | CS Design §4, CS Impl §4.1 |
| What are the validation rules? | CS Design §5 |

---

*Storyteller V3 — Project Guide v1.1*  
*The front door. Start here.*

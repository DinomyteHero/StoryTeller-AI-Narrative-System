# Documentation Consolidation Report

**Date:** April 5, 2026
**Scope:** Full documentation audit, architecture redesign, and
consolidation pass across the Storyteller V3 project.

---

## 1. Summary of Changes

### Structural Changes
- Created `docs/reference/` directory for archived/reference-only material
- Moved 4 documents from `docs/` to `docs/reference/`
- Merged 2 documents into 1 new consolidated spec
- Deleted 2 original files (replaced by merge)
- Created 2 new files (`PROLOGUE_SYSTEM_SPEC.md`, `reference/README.md`)

### Content Changes
- Rewrote `00_PROJECT_GUIDE.md` with four-tier document architecture
- Added status/scope headers to 4 specialist specs
- Added "REFERENCE ONLY" banners to 4 archived docs
- Updated cross-references in 6 documents (`CLAUDE.md`,
  `PROJECT_STATE_MATRIX.md`, `STORYTELLER_V3_BUILD_ROADMAP.md`,
  `STORYTELLER_V3_BACKLOG.md`, plus the 2 new files)
- Removed stale inline status snapshot from Project Guide (replaced
  with pointer to Backlog and State Matrix)

### What Was NOT Changed
- No application code modified
- No runtime behavior changed
- No schemas or gameplay logic altered
- 11 canonical core/planning/research docs left content-unchanged
  (only cross-references and headers updated where needed)
- All important design content preserved

---

## 2. Final Documentation Architecture

### Four-Tier System

**Tier 1 — Core Specifications** (5 documents)

| Document | Authoritative For |
|----------|------------------|
| `STORYTELLER_V3_VISION.md` | Creative intent, player experience |
| `STORYTELLER_V3_GAME_MECHANICS.md` | Mechanical system design (27 sections) |
| `STORYTELLER_V3_IMPLEMENTATION.md` | Game Engine code specification |
| `STORYTELLER_V3_CAMPAIGN_STUDIO.md` | Campaign Studio design |
| `STORYTELLER_V3_CAMPAIGN_STUDIO_IMPLEMENTATION.md` | Campaign Studio code |

**Tier 2 — Planning and Status** (3 documents)

| Document | Authoritative For |
|----------|------------------|
| `STORYTELLER_V3_BUILD_ROADMAP.md` | Build phases, sequencing, success criteria |
| `STORYTELLER_V3_BACKLOG.md` | Item tracking, status (single source of truth) |
| `PROJECT_STATE_MATRIX.md` | Capability dashboard |

**Tier 3 — Research and Evaluation** (2 documents)

| Document | Authoritative For |
|----------|------------------|
| `STORYTELLER_V3_LLM_EVALUATION.md` | Model selection, compliance testing |
| `STORYTELLER_V3_RESEARCH_CATALOGUE.md` | Research evidence, TAKE/REJECT decisions |

**Tier 4 — Specialist Specifications** (4 documents)

| Document | Scope | Phase |
|----------|-------|-------|
| `CHOICE_QUALITY_VALIDATION_SPEC.md` | Choice quality validation | Late Phase 3 / Phase 7 |
| `PROLOGUE_SYSTEM_SPEC.md` | Prologue design + implementation | Phase 18 |
| `IMPORT_PACKAGE_QUALITY_SPEC.md` | Import compression quality | Phase 19 |
| `STORY_ARCHITECTURE_SPEC.md` | Campaign narrative quality | CS-5 (complete) |

**Reference Archive** (`docs/reference/`, 4 documents + README)

| Document | Status |
|----------|--------|
| `STORYTELLER_V3_DESIGN_GAP_ANALYSIS_V2.md` | Designs applied to canonical docs |
| `STORYTELLER_V3_DEFERRED_DESIGN_AND_LOGIC_ANALYSIS.md` | Content applied; logic analysis useful as reference |
| `CLAUDE_CODE_INITIAL_PROMPT.md` | Superseded by CLAUDE.md |
| `prose_quality_review_session_1.md` | Historical playtest data |

**Total: 15 active docs + 1 Project Guide + 4 archived = 20 original
docs reorganized into a navigable, tiered structure.**

---

## 3. Old-to-New Mapping Table

| Old Location | New Location | Change Type |
|-------------|-------------|-------------|
| `docs/00_PROJECT_GUIDE.md` | `docs/00_PROJECT_GUIDE.md` | Rewritten (v1.3 -> v2.0) |
| `docs/STORYTELLER_V3_VISION.md` | `docs/STORYTELLER_V3_VISION.md` | Unchanged |
| `docs/STORYTELLER_V3_GAME_MECHANICS.md` | `docs/STORYTELLER_V3_GAME_MECHANICS.md` | Unchanged |
| `docs/STORYTELLER_V3_IMPLEMENTATION.md` | `docs/STORYTELLER_V3_IMPLEMENTATION.md` | Unchanged |
| `docs/STORYTELLER_V3_CAMPAIGN_STUDIO.md` | `docs/STORYTELLER_V3_CAMPAIGN_STUDIO.md` | Unchanged |
| `docs/STORYTELLER_V3_CAMPAIGN_STUDIO_IMPLEMENTATION.md` | `docs/STORYTELLER_V3_CAMPAIGN_STUDIO_IMPLEMENTATION.md` | Unchanged |
| `docs/STORYTELLER_V3_BUILD_ROADMAP.md` | `docs/STORYTELLER_V3_BUILD_ROADMAP.md` | Cross-ref updated |
| `docs/STORYTELLER_V3_BACKLOG.md` | `docs/STORYTELLER_V3_BACKLOG.md` | Cross-ref updated |
| `docs/PROJECT_STATE_MATRIX.md` | `docs/PROJECT_STATE_MATRIX.md` | Cross-ref updated |
| `docs/STORYTELLER_V3_LLM_EVALUATION.md` | `docs/STORYTELLER_V3_LLM_EVALUATION.md` | Unchanged |
| `docs/STORYTELLER_V3_RESEARCH_CATALOGUE.md` | `docs/STORYTELLER_V3_RESEARCH_CATALOGUE.md` | Unchanged |
| `docs/CHOICE_QUALITY_VALIDATION_SPEC.md` | `docs/CHOICE_QUALITY_VALIDATION_SPEC.md` | Header added |
| `docs/PROLOGUE_INFERENCE_SPEC.md` | `docs/PROLOGUE_SYSTEM_SPEC.md` (Part A) | Merged |
| `docs/PHASE_18_IMPLEMENTATION_PLAN.md` | `docs/PROLOGUE_SYSTEM_SPEC.md` (Part B) | Merged |
| `docs/IMPORT_PACKAGE_QUALITY_SPEC.md` | `docs/IMPORT_PACKAGE_QUALITY_SPEC.md` | Header added |
| `docs/STORY_ARCHITECTURE_SPEC.md` | `docs/STORY_ARCHITECTURE_SPEC.md` | Header added |
| `docs/STORYTELLER_V3_DESIGN_GAP_ANALYSIS_V2.md` | `docs/reference/STORYTELLER_V3_DESIGN_GAP_ANALYSIS_V2.md` | Moved + banner |
| `docs/STORYTELLER_V3_DEFERRED_DESIGN_AND_LOGIC_ANALYSIS.md` | `docs/reference/STORYTELLER_V3_DEFERRED_DESIGN_AND_LOGIC_ANALYSIS.md` | Moved + banner |
| `docs/CLAUDE_CODE_INITIAL_PROMPT.md` | `docs/reference/CLAUDE_CODE_INITIAL_PROMPT.md` | Moved + banner |
| `docs/prose_quality_review_session_1.md` | `docs/reference/prose_quality_review_session_1.md` | Moved + banner |
| — | `docs/reference/README.md` | New |
| — | `docs/PROLOGUE_SYSTEM_SPEC.md` | New (merged) |

---

## 4. Canonical Documents

The following are the active, authoritative documents:

**Always consult these for their stated scope:**
1. `00_PROJECT_GUIDE.md` — front door, authority map
2. `STORYTELLER_V3_VISION.md` — creative vision
3. `STORYTELLER_V3_GAME_MECHANICS.md` — mechanical design
4. `STORYTELLER_V3_IMPLEMENTATION.md` — Game Engine code
5. `STORYTELLER_V3_CAMPAIGN_STUDIO.md` — CS design
6. `STORYTELLER_V3_CAMPAIGN_STUDIO_IMPLEMENTATION.md` — CS code
7. `STORYTELLER_V3_BUILD_ROADMAP.md` — build phases
8. `STORYTELLER_V3_BACKLOG.md` — item tracking
9. `PROJECT_STATE_MATRIX.md` — capability status
10. `STORYTELLER_V3_LLM_EVALUATION.md` — model selection
11. `STORYTELLER_V3_RESEARCH_CATALOGUE.md` — research evidence
12. `CHOICE_QUALITY_VALIDATION_SPEC.md` — choice validation
13. `PROLOGUE_SYSTEM_SPEC.md` — prologue system
14. `IMPORT_PACKAGE_QUALITY_SPEC.md` — import quality
15. `STORY_ARCHITECTURE_SPEC.md` — story architecture

---

## 5. Archived / Reference-Only Documents

| Document | Reason |
|----------|--------|
| `reference/STORYTELLER_V3_DESIGN_GAP_ANALYSIS_V2.md` | One-time audit. All 9 designs complete and applied to canonical docs. Still useful when implementing specific Backlog items. |
| `reference/STORYTELLER_V3_DEFERRED_DESIGN_AND_LOGIC_ANALYSIS.md` | One-time audit. Designs applied to GM v1.8. Section 4 (logic walkthrough) remains a useful architecture reference. |
| `reference/CLAUDE_CODE_INITIAL_PROMPT.md` | Superseded by CLAUDE.md in repo root. |
| `reference/prose_quality_review_session_1.md` | Historical playtest data artifact. Not a specification. |

---

## 6. Duplication Removed

| Topic | Former Duplication | Resolution |
|-------|-------------------|------------|
| Prologue system specification | Split across `PROLOGUE_INFERENCE_SPEC.md` (design robustness) and `PHASE_18_IMPLEMENTATION_PLAN.md` (implementation steps) — two docs for one system | Merged into `PROLOGUE_SYSTEM_SPEC.md` with Part A (design) and Part B (implementation) |
| Claude Code setup guidance | `CLAUDE_CODE_INITIAL_PROMPT.md` duplicated reading order from `00_PROJECT_GUIDE.md` and project overview from `CLAUDE.md` | Archived. CLAUDE.md is the single orientation point. |
| Project status snapshot | `00_PROJECT_GUIDE.md` contained a detailed, date-stamped status snapshot that would drift from Backlog/State Matrix | Replaced with brief milestone summary + pointer to Backlog and State Matrix |
| Audit artifacts competing with canonical docs | Design Gap Analysis and Deferred Design sat alongside canonical docs with no visual distinction | Moved to `reference/` with "REFERENCE ONLY" banners |

---

## 7. Unresolved Tensions and Judgment Calls

### Kept but monitored

**Game Mechanics contains implementation-level detail.** The Game
Mechanics doc (312KB) includes data schemas, function signatures, and
prompt templates that overlap with the Implementation doc. This is by
design — Game Mechanics defines the system, Implementation implements
it — but the boundary is not always clean. The Game Mechanics doc
serves as a "bridge document" between creative vision and code. No
action taken because the overlap is intentional and the authority
resolution rules handle conflicts.

**Campaign Studio has a design/implementation doc pair with heavy
conceptual overlap.** Both docs describe the three automation modes,
saga pipeline, validation, and spine format at different abstraction
levels. This is the same design/implementation split as the Game
Engine side. No consolidation attempted because the separation between
"what and why" vs. "how in code" is architecturally sound.

**Backlog, State Matrix, and Build Roadmap all track status.** The
Backlog is authoritative (per the authority rules), the State Matrix
is a compact dashboard, and the Roadmap tracks phase-level status.
These serve different audiences. The risk is drift between them. No
consolidation attempted because each serves a distinct purpose, but
this should be monitored.

### Judgment calls made

**Specialist specs kept in docs/ root, not in a subdirectory.** These
are active future-phase specs (not archived), and moving them would
add another directory level for only 4 files. The status headers make
their scope clear without physical separation.

**Stale status snapshot removed from Project Guide.** The v1.3 guide
contained a detailed, date-stamped snapshot (codebase metrics, known
limitations, known open items) that was already stale. Replaced with
a brief milestone summary and pointers to the authoritative status
docs. This makes the guide more evergreen but removes some
convenience for first-time readers.

**Design Gap Analysis archived rather than absorbed.** The 9 design
specs in the Gap Analysis could theoretically be absorbed into Game
Mechanics or Implementation. However, they are complete standalone
designs referenced by specific Backlog items. Absorbing them would
significantly grow already-large documents (GM is 312KB, Impl is
155KB) for marginal benefit. Archiving preserves them as a reference
while removing them from the active reading flow.

---

## 8. Recommendations for Ongoing Documentation Hygiene

1. **When implementing a new phase**, check whether the phase touches
   any Tier 4 specialist spec. If so, the spec should be updated or
   graduated into the canonical doc upon completion (e.g., Story
   Architecture Spec content could eventually be absorbed into
   Campaign Studio Design if CS-5 is stable enough).

2. **When the Backlog changes**, verify the State Matrix and Build
   Roadmap phase statuses still agree. The Backlog is authoritative;
   the others should follow.

3. **When adding a new doc**, assign it to a tier and add it to the
   Project Guide's document architecture table. Do not create
   docs that compete with an existing canonical doc's scope.

4. **When a specialist spec's phase is complete**, evaluate whether
   the spec should be absorbed into its parent canonical doc or
   remain standalone. Absorption is preferred when the parent doc
   can accommodate it without becoming unwieldy.

5. **When creating audit or analysis docs**, put them directly in
   `docs/reference/` if they are one-time artifacts. Only promote
   to `docs/` root if they become ongoing references.

6. **Version the Project Guide** when the doc structure changes.
   The Project Guide is the map; when the territory changes, the
   map must be updated.

---

*Documentation Consolidation Report — April 5, 2026*

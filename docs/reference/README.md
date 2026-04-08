# Reference / Archive

This directory contains documents that are **no longer active
specifications** but are preserved for historical reference and
traceability.

**Do not treat these documents as authoritative.** Their design content
has either been applied to canonical documents or they serve as
historical artifacts.

## Contents

| Document | Original Purpose | Status |
|----------|-----------------|--------|
| `design-gap-analysis-v2.md` | Design specs for 9 items not covered in Game Mechanics or Implementation. | All designs complete and referenced by Backlog. Consult canonical docs for current specs. |
| `deferred-design-analysis.md` | Design for 2 deferred items + full system logic walkthrough. | Designs applied to Game Mechanics v1.8. Logic analysis (Section 4) remains a useful architecture reference. |
| `claude-code-initial-prompt.md` | Setup prompt for Claude Code sessions. | Superseded by `CLAUDE.md` in the repository root. |
| `prose-quality-review-1.md` | Playtest transcript (Echoes of the Force, Talia Ren). | Historical data artifact. Useful for prose quality benchmarking. |
| `consolidation-report.md` | Record of the April 2026 documentation consolidation. | One-time artifact documenting the rationale for the four-tier structure. |

## When to Consult These

- **Design Gap Analysis** — when implementing items 2.19, 2.28, 3.26-3.28,
  4.0a, 4.0d, 4.9, 4.10 from the Backlog and you need the original
  detailed design.
- **Deferred Design / Logic Analysis** — when you need to understand
  the V1 turn loop data flow walkthrough (Section 4) or the original
  reputation echo / conditional choice designs.
- **Prose Quality Review** — when evaluating LLM prose quality against
  a real session transcript.

> **SPECIALIST SPEC** — Post-generation choice quality validator.
> **Build phase:** Late Phase 3 or Phase 7 (contingent on playtesting).
> **Design authority for:** choice validation rubric, local evaluator
> integration, retry policy for low-quality choice sets.
> **Depends on:** Vision §7, Implementation §7.1/§7.3, Game Mechanics §24.
>
> **Implementation Status: NOT STARTED**
> The code structures below are the design specification for a future
> validation layer. No implementation code exists yet. Activation is
> contingent on playtesting calibration results.

# Storyteller V3 — Choice Quality Validation Spec

**Version:** 1.0
**Date:** March 6, 2026
**Purpose:** Specification for a post-generation validation layer that
rejects weak, generic, or low-character-expression choice sets before
they reach the player. Addresses the validation gap identified in the
project audit: the narration prompt tells the GM what good choices look
like, but no enforcement layer catches a non-compliant response.

**Relationship to existing documents:**

- **Vision §7** — defines what good choices are (character through
  tactics, no generic action types, risk gradient, specificity)
- **Implementation §7.1** — the narration prompt that instructs the GM
  (worked examples, introspection guidance, risk signaling rules)
- **Implementation §7.3** — the existing retry loop that handles
  structural validation (delimiter, word count, choice count)
- **Game Mechanics §24** — the semantic memory system that annotates
  choices post-selection (different problem — that system runs after
  the player picks; this system runs before the player sees)
- **Deferred Design §2** — conditional choice availability from
  behavioral patterns (different problem — that system controls which
  choices appear; this system controls whether the choices that appear
  are any good)

**What this spec does NOT cover:**

- Prose quality validation (that is the prose diagnostic signal, GM §13)
- Choice availability conditioning (that is Deferred Design §2)
- Choice annotation after selection (that is GM §24)

---

## 1. The Problem

The Vision Document treats choice quality as the skeleton of the game.
The narration prompt (Implementation §7.1) contains extensive
instructions: character through tactics, no generic action types, worked
good/bad examples, risk signaling, introspection guidance. But the
existing `_parse_response()` function only validates structure — is the
delimiter present, is the word count in range, are there 2–4 choices.
If the cloud GM generates structurally valid but experientially flat
choices — "Pick the lock / Force the door / Talk your way in" — the
system accepts and displays them.

This is the gap. Prompt instructions are compliance-dependent. A model
that ignores the character-through-tactics instruction on a given turn
produces a choice set that undermines the core player experience. The
system needs a way to catch this before the player sees it.

---

## 2. Design Constraints

**Latency budget.** The player spends 30–60 seconds reading a passage
before making their choice. The total time from player action to new
passage display is the sum of: check decision (~2–4s local), context
assembly (~instant), cloud narration (~5–15s), and any post-generation
validation. An additional validation step that adds 2–4 seconds to the
local model is acceptable. An additional cloud call is not — it would
double the turn cost and approach the player's reading-time budget.

**Evaluator model.** The local model (Qwen3.5:9B) is the only option
that fits the latency and cost constraints. It is adequate for
structured evaluation tasks (it already handles check decisions and
JSON schema enforcement reliably). It does not need to generate good
choices — it needs to detect bad ones.

**False positive tolerance.** Rejecting a good choice set and forcing
a retry is worse than accepting a mediocre one. A retry adds 5–15
seconds of cloud latency and may produce a worse result. The validator
should be calibrated to catch clearly generic choices, not to enforce
literary perfection. The threshold should prefer precision (few false
positives) over recall (catching every weak choice).

**Retry budget.** The existing structural retry loop allows 2 retries
(3 total attempts). The quality validator shares this budget — it does
not add additional retries. If the structural parse succeeds but the
quality check fails, the system uses one of the remaining retry
attempts. If all retries are exhausted, the system accepts the best
available result rather than failing the turn.

---

## 3. The Rubric

The validator evaluates the choice set (not individual choices) against
five dimensions. Each dimension produces a binary pass/fail signal.
The choice set fails validation only when **two or more** dimensions
fail simultaneously — a single marginal dimension does not trigger
rejection.

### 3.1 Genericity

**Question:** Could these choices appear in any scene with any
character, or are they specific to this moment?

**Fail signal:** The choices are generic action types (attack / defend
/ talk / flee / investigate) with scene-specific wording but no
character-specific content. The test: if you replaced the character
name and location, would the choices still make sense for a different
character in a different scene?

**Pass signal:** At least two choices contain details specific to this
character's situation, relationships, knowledge, or personality —
details that would not make sense for a different character.

### 3.2 Character Expression

**Question:** Do the choices reveal different things about who the
character is, or do they only vary in method?

**Fail signal:** All choices accomplish the same goal through different
skills but reveal nothing about the character's values, priorities, or
personality. They test what the player does, not who they are.

**Pass signal:** At least two choices would reveal different priorities,
values, or aspects of the character's identity if selected. A reviewer
could describe what each choice says about the character beyond its
tactical effect.

### 3.3 Risk Spread

**Question:** Do the choices offer a range of risk levels, or are they
all roughly equivalent in danger?

**Fail signal:** All choices carry the same apparent risk level — all
safe, all dangerous, or all neutral. The player has no meaningful risk
decision to make.

**Pass signal:** At least one choice is lower risk and at least one is
higher risk. The risk difference is apparent from the choice text.

### 3.4 Tactical Differentiation

**Question:** Do the choices lead to genuinely different outcomes, or
are they cosmetic variations on the same action?

**Fail signal:** All choices converge on the same narrative outcome
with different flavor text. The player's selection would not
meaningfully change what happens next.

**Pass signal:** At least two choices would plausibly produce different
narrative outcomes, involve different NPCs, or change the character's
position in the scene.

### 3.5 Contextual Grounding

**Question:** Do the choices reference specific elements of the current
scene — NPCs present, objects available, information known, threats
active — or do they float free of context?

**Fail signal:** The choices could exist independently of the preceding
passage. They do not reference any specific element of the scene as
narrated.

**Pass signal:** At least two choices reference specific scene elements
(named NPCs, specific objects, information revealed in the passage,
established threats or opportunities).

---

## 4. Evaluation Method

### 4.1 Validator Prompt

The local model receives a structured evaluation prompt. The prompt
contains: the current scene description (the `situation` field from
the context package), the character summary (name, career, key
relationships), the generated passage (so the validator can assess
contextual grounding), and the generated choices.

The validator does **not** receive the full narration prompt or the
rubric definitions in natural language. Those would consume too many
tokens for a local model call. Instead, the prompt asks five specific
yes/no questions — one per rubric dimension — designed to be
answerable by a 9B model with high reliability.

```
Evaluate these choices for a Star Wars narrative RPG.

SCENE: {situation}
CHARACTER: {character_name}, {character_career}
PASSAGE ENDING: {last_100_words_of_passage}

CHOICES:
{numbered_choice_list}

Answer each question with YES or NO only.

1. SPECIFIC: Do at least 2 choices contain details that would NOT
   make sense for a different character in a different scene?
2. IDENTITY: Do at least 2 choices reveal different things about
   who the character is (values, priorities, personality), not just
   different methods?
3. RISK: Is there a visible difference in risk level between the
   safest choice and the most dangerous choice?
4. DIFFERENT: Would at least 2 choices plausibly lead to different
   narrative outcomes?
5. GROUNDED: Do at least 2 choices reference specific elements
   from the scene (named NPCs, specific objects, established
   threats)?

Respond as JSON:
{"specific": true/false, "identity": true/false, "risk": true/false,
 "different": true/false, "grounded": true/false}
```

### 4.2 Evaluation Schema

```json
{
  "type": "object",
  "properties": {
    "specific":  {"type": "boolean"},
    "identity":  {"type": "boolean"},
    "risk":      {"type": "boolean"},
    "different": {"type": "boolean"},
    "grounded":  {"type": "boolean"}
  },
  "required": ["specific", "identity", "risk", "different", "grounded"]
}
```

The Ollama `format` parameter enforces this schema, matching the
pattern used by the check decision system (Implementation §6.2).

### 4.3 Failure Threshold

The choice set fails validation when **two or more** of the five
dimensions return `false`. A single `false` is logged but accepted.

**Rationale:** The local model is not a perfect evaluator. A single
failed dimension may be a false negative (the model missed context that
makes the choice specific). Two or more simultaneous failures strongly
correlate with genuinely weak choices — the model would need to
misjudge two independent dimensions to produce a false rejection.

---

## 5. Integration into the Turn Loop

### 5.1 Where It Runs

The validator runs **after** `_parse_response()` succeeds (structural
validation passes) and **before** the result is returned to the turn
handler. It occupies the same position in the retry loop as structural
validation — a quality failure counts as a retry, sharing the existing
retry budget.

### 5.2 Modified Flow

```
narrate_turn():
  for attempt in range(max_retries + 1):
    raw = cloud_call(prompt, correction_messages)
    try:
      result = _parse_response(raw)       # structural validation
    except CloudGMError:
      last_error = structural error
      continue

    quality = _validate_choice_quality(    # quality validation
      situation, character_summary, result
    )

    if quality.passed:
      return result                        # good turn
    elif quality.fail_count == 1:
      log_warning(quality)
      return result                        # marginal — accept
    else:
      last_error = quality.rejection_reason
      continue                             # retry with correction

  return best_available_result             # exhausted — accept best
```

### 5.3 Correction Message

When the quality validator triggers a retry, the correction message
appended to the next attempt is specific to the failed dimensions:

```python
def _build_quality_correction(quality: ChoiceQualityResult) -> str:
    parts = ["Your choices were rejected for quality issues:"]
    if not quality.specific:
        parts.append(
            "- Choices are too generic. Include details specific to "
            "this character and this scene."
        )
    if not quality.identity:
        parts.append(
            "- Choices only vary in method, not in what they reveal "
            "about the character. Each choice should say something "
            "different about who the character is."
        )
    if not quality.risk:
        parts.append(
            "- All choices have similar risk levels. Include at least "
            "one lower-risk and one higher-risk option."
        )
    if not quality.different:
        parts.append(
            "- Choices would all lead to similar outcomes. At least "
            "two should produce meaningfully different results."
        )
    if not quality.grounded:
        parts.append(
            "- Choices don't reference specific scene elements. "
            "Reference named NPCs, objects, or threats from the scene."
        )
    parts.append("Rewrite only the choices. Keep the passage unchanged.")
    return "\n".join(parts)
```

### 5.4 Best-Available Fallback

If all retry attempts are exhausted (structural or quality failures),
the system accepts the best structurally valid result produced across
all attempts, even if it failed quality validation. A failed turn that
shows the player mediocre choices is better than no turn at all. The
quality failure is logged for monitoring.

---

## 6. Latency Analysis

The validator adds one local model call per turn. Based on the existing
check decision performance profile (Qwen3.5:9B on RTX 4070):

| Step | Estimated Time |
|------|---------------|
| Prompt assembly | ~instant |
| Local model inference (short JSON) | 1–2s |
| JSON parsing + threshold check | ~instant |

**Total added latency:** 1–2 seconds per turn when the choices pass.
On rejection, add one cloud retry (5–15s) — but rejections should be
infrequent with a well-performing cloud model.

**Parallelization opportunity:** The quality validation runs on the
local model. The check decision also runs on the local model but
occurs earlier in the turn loop (Step 3 vs Step 6 in Deferred Design
§4.1). They never overlap. If a future optimization parallelizes
quality validation with turn persistence (Step 7), the quality check
becomes zero added latency on the critical path. This is not required
for the initial implementation.

---

## 7. Calibration Protocol

The validator must be calibrated before deployment to ensure the
rejection threshold produces acceptable precision. False rejections
waste cloud credits and add latency. Missed catches degrade player
experience.

### 7.1 Calibration Dataset

Collect 50 choice sets from initial playtesting (or from early
compliance test runs). Manually label each as GOOD, MARGINAL, or BAD.
The target distribution: ~60% GOOD, ~25% MARGINAL, ~15% BAD.

### 7.2 Calibration Criteria

Run the validator against all 50 choice sets. Measure:

- **Precision:** Of choice sets the validator rejected, what
  percentage were actually BAD? Target: ≥80%.
- **Recall on BAD:** Of actually BAD choice sets, what percentage
  did the validator catch? Target: ≥60%.
- **False rejection rate on GOOD:** Of actually GOOD choice sets,
  what percentage did the validator reject? Target: ≤5%.

### 7.3 Threshold Adjustment

If precision is too low (too many false rejections), raise the failure
threshold from 2 to 3 failed dimensions. If recall is too low (too
many BAD sets accepted), lower it to 1 — but only if precision remains
above 80%.

If the local model cannot achieve acceptable precision at any
threshold, the validator should be disabled rather than deployed with
high false rejection rates. In that case, the fallback is the existing
prompt-only approach until a better local evaluator is available
(either through model upgrade or QLoRA fine-tuning from playtesting
data).

---

## 8. Data Collection for Future Improvement

Every quality evaluation is logged alongside the turn data. This
produces training data for two future improvements:

**Prose diagnostic integration.** When the prose diagnostic signal
(GM §13) is implemented, choice quality scores become one of its
input dimensions. A turn that passes prose quality but fails choice
quality (or vice versa) produces a richer diagnostic signal than
either alone.

**Local evaluator fine-tuning.** The logged evaluations, combined
with player feedback (if the campaign rating system captures per-turn
quality signals), can train a more accurate local evaluator via the
same QLoRA pipeline designed for the Campaign Studio evaluator
(Design Gap Analysis v2.0, item 4.9).

### 8.1 Logging Schema

```sql
CREATE TABLE IF NOT EXISTS choice_quality_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    choices_json TEXT NOT NULL,
    evaluation_json TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    fail_count INTEGER NOT NULL,
    triggered_retry BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

---

## 9. Build Phase and Dependencies

**Target phase:** Late Phase 3 or early Phase 7. The validator requires
a working cloud GM producing real choice output. It cannot be built or
calibrated before the cloud narration loop functions.

**Dependencies:**
- Phase 3 complete (cloud GM produces narrated passages with choices)
- Local model operational (Ollama + Qwen3.5:9B serving JSON)

**V1 decision:** Whether the validator ships as part of V1 depends on
the calibration results. If the first 50 choice sets from V1
playtesting show the cloud model consistently producing good choices
(the prompt is sufficient), the validator becomes a Phase 7 addition.
If early playtesting reveals frequent generic choices, the validator
is promoted to a V1 requirement.

**Backlog integration:** Add as item 1.45 (choice quality validation)
in the V1 Build Items — Cross-Cutting section, status DESIGNED, with
a note that activation is contingent on calibration results from
initial playtesting.

---

## 10. Interaction with Existing Systems

**Narration prompt.** The validator does not replace the prompt
instructions — it backstops them. The prompt remains the primary
quality control mechanism. The validator catches the cases where the
prompt fails.

**Retry loop.** The validator shares the existing retry budget. No
additional retries are added. This keeps the worst-case latency
bounded.

**Local fallback narration.** When the system falls back to local
narration (cloud unavailable), the quality validator is **skipped**.
The local model's narration quality is already known to be lower
(LLM Eval §8.1 rates it 2/5 for choice generation). Validating local
output against a quality rubric that the local model cannot meet would
cause every fallback turn to exhaust retries. The fallback path
accepts whatever the local model produces.

**Streaming.** The validator requires the complete response before
evaluation. For the streaming endpoint (`narrate_turn_stream`), the
full response must be buffered before quality validation runs. This
means streaming displays the passage progressively but holds the
choices until validation completes. The player is reading the passage
during this time, so the delay is invisible in practice.

---

*Storyteller V3 — Choice Quality Validation Spec v1.0*  
*The prompt is necessary. It is not sufficient.*

## Context

`docs/phase2_manual_test_scenarios.md` is the single-pass manual QA script for Phase 2 (Menu & Cart). Three inaccuracies have been identified that will cause testers to hit API errors or misread expected behavior. See proposal.md for details.

**Affected modules:** none (documentation-only change).

## Goals / Non-Goals

**Goals:**
- Correct the `item_id` → `menu_item_id` field name in Block 1.3 curl payloads so they match the `SizeOptionCreate` schema.
- Update Block 3.6 expectation to reflect the DELETE-based decrement-to-remove behavior.
- Remove the hedge in Block 3.8 now that the "Clear cart" button is implemented.

**Non-Goals:**
- No source code changes.
- No reformatting or restructuring beyond the three targeted blocks.

## Decisions

1. **Direct text edits, no tooling.** The file is plain Markdown with embedded curl snippets. A simple find-and-replace for `"item_id":` → `"menu_item_id":` covers Fix 1. Fixes 2 and 3 are small rewrites of 2–3 lines each. No scripting or automation needed.

2. **Preserve surrounding whitespace and formatting.** The document uses a consistent style; edits SHALL match it exactly to avoid noisy diffs.

## Risks / Trade-offs

- **Risk:** Other blocks may reference the same wrong field name. → **Mitigation:** grep the entire file for `"item_id"` after editing to confirm no remaining occurrences.
- **Risk:** Minimal — all three fixes are isolated text changes with no downstream dependencies.

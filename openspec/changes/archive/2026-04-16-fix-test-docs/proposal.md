## Why

The Phase 2 manual test scenarios document (`docs/phase2_manual_test_scenarios.md`) contains three inaccuracies that will cause testers to fail or misinterpret results: a wrong field name in API payloads, an outdated cart decrement expectation, and a hedged instruction about a button that now exists. Fixing these keeps the test script reliable as a single-pass walkthrough.

MVP Phase: Phase 2 (Menu & Cart).

## What Changes

- **Block 1.3 size-creation curl payloads**: rename `"item_id"` → `"menu_item_id"` in 3 JSON bodies to match the `SizeOptionCreate` Pydantic schema.
- **Block 3.6 decrement-to-0 expectation**: rewrite to reflect that tapping − at qty=1 triggers a DELETE (remove), not a PATCH with qty=0. Rename section to "Decrement to remove".
- **Block 3.8 Clear cart instruction**: remove the "(if button exists)" hedge — the button is now implemented.

## Non-Goals

- No changes to any backend or frontend source code.
- No changes to test blocks outside 1.3, 3.6, and 3.8.
- No restructuring or reformatting of the document beyond the targeted fixes.

## Capabilities

### New Capabilities

_(none — this is a documentation-only fix)_

### Modified Capabilities

_(none — no spec-level behavior changes, only correcting the test script to match existing specs)_

## Impact

- **Affected file**: `docs/phase2_manual_test_scenarios.md` (3 localized edits).
- No code, API, dependency, or infrastructure changes.

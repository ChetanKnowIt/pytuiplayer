# AI_TASK_STATE.md

## Current Branch
`feature/07-fix-ui-alignment` — branched off `main` (known-good baseline: 102 tests, ruff clean, 53/53 backlog done).

## Completed This Session

### ROADMAP.md cleanup (on `main`, pre-branch)
- Added the missing `feature/06-fix-ui-alignment` entry to ROADMAP.md (it was merged but never recorded; AI_TASK_STATE.md + git history confirmed it).
- Removed the dead `#progress` CSS rule (lines 105–113) for the already-deleted `ProgressBar` widget — leftover from before feature/06.
- Noted in ROADMAP that the `#now-playing` box still clipped its 2nd row, motivating the follow-up branch.

### feature/07-fix-ui-alignment — **IN PROGRESS** (branch `feature/07-fix-ui-alignment`)
Fixes residual UI alignment defects uncovered by a headless layout probe (`NowPlaying.render()`
always returns 2 lines, but the CSS content area was too short to show row 2).

**Evidence (headless probe, `run_test(size=(120,40))`):**
- Before: `#now-playing` region height=5 but content height=1 → `NowPlaying.render()` 2nd row
  (seek bar / stream metadata) was clipped/invisible.
- After:  `#now-playing` content height=2 → both rows render (`'...Nothing playing'`, `'⏱ Duration unknown'`).

**Changes:**
- `src/pytuiplayer/musicplayer_tui.css`
  - `#now-playing`: `height: 5` → `height: 6; min-height: 6` (content = height - 4 = 2 lines). Comment explains the border+padding math.
  - `#controls`: `height: 4` → `height: 5` (content = height - 2 (padding) = 3, fits the round-bordered buttons (3) and `#volume-indicator` (3) without clipping).
- ROADMAP.md + AI_TASK_STATE.md updated to reflect feature/06 + this branch.

**Not yet committed** (user did not ask to commit).

## Tests
- `uv run pytest -q` → **102 passed in ~10s** (no regressions from CSS change)
- `uv run ruff check .` → **All checks passed!**
- Headless layout probe confirmed `#now-playing` now renders 2 lines (row 2 no longer clipped).

## Next Step
Add an acceptance/test guard that the NowPlaying widget reserves height for both rows (so a future
CSS shrink can't silently re-clip row 2), then commit the branch and update the testsuite DB report.
Optionally verify a visual screenshot (no cairosvg/rsvg-convert available in this env to rasterize
the Textual SVG; the 2-line render assertion is the functional gate).

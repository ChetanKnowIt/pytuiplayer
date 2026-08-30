# AI_TASK_STATE.md

## Current Branch
`housekeeping/clean-up-repo` — cleaning up repository clutter before next feature.

## Completed This Session

### Repository Cleanup
- Removed 17+ debug/profile scripts from `scripts/` (debug_*.py, profile_*.py, screenshot_ui.py)
- Removed old manual test scripts (test_main.py, test_mpv.py, test_pyradio.py, test_raw_mpv.py, ast_stub.py)
- Removed screenshots directory and root-level screenshot PNG
- Removed scripts/__pycache__/
- Kept only production scripts: `run_tui_app_demo.py`, `run_radio_demo.py`, `update_testsuite_db.py`, `report_testsuite_db.py`

## Tests
- `uv run pytest -q` → **102 passed**
- `uv run ruff check src/` → All checks passed!

## Next Step
Commit housekeeping, merge to main, then start next feature.

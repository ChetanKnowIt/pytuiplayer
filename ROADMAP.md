# ROADMAP.md — pytuiplayer

## Tech Debt & Drawbacks

### Design Flaws (none open)

All tracked design flaws are closed. See git history (`feature/01` through `feature/04`) for details.

---

## Test Inventory (in `testsuite.db`)
The full test inventory — including the test backlog (missing/integration tests) and their
done/pending status — lives **exclusively** in a structured SQLite database
(`testsuite.db` at the repo root). ROADMAP.md stays light; the DB is the single source of
truth for everything test-related. As features are added, every `uv run pytest` run refreshes
it, so the Test Backlog doubles as the **prerequisite checklist** before starting the next
feature.

- **Schema:** `files`, `tests`, `runs`, `backlog`, `meta` (see
  `src/tests/testsuite_db.py`). Upsert keyed on `(file, name)` — reruns are idempotent.
- **Auto-refresh:** every `uv run pytest` run writes the `tests` + `runs` tables via
  the hook in `src/tests/conftest.py`.
- **Enrichment:** `scripts/update_testsuite_db.py` refreshes `files` (line counts +
  descriptions) and mirrors the Test Backlog into `backlog` (status preserved).
- **Reporting:** `scripts/report_testsuite_db.py` prints the inventory / backlog / runs.

```bash
uv run pytest -q                       # runs tests AND refreshes testsuite.db
uv run python scripts/update_testsuite_db.py   # enrich files + sync backlog
uv run python scripts/report_testsuite_db.py    # print the inventory
```

```sql
-- Quick queries against testsuite.db
SELECT file, COUNT(*) AS n FROM tests GROUP BY file ORDER BY file;
SELECT status, COUNT(*) FROM backlog GROUP BY status;          -- done vs pending
SELECT * FROM runs ORDER BY id DESC LIMIT 5;                   -- last runs
```

> The `network`-marked radio test (`test_radio_integration.py`) passes when a live
> stream is reachable and auto-skips offline.

---

## Feature Plan (branch-organized)

Open work is grouped into feature branches. Each branch is developed and tested on
its own (`feature/NN-slug`), and may merge to `main` only when every test in its plan
passes (`uv run pytest -q` → green) and `uv run ruff check .` is clean. The test names
below are the **acceptance criteria** — add them to `src/tests/` (e.g.
`test_feature_0N_*.py`) and mirror them into `testsuite.db` via
`scripts/update_testsuite_db.py` so the DB tracks each branch's progress.

### feature/04-update-medium-priority — **DONE** (branch `feature/04-update-medium-priority`)
Closes Medium Priority #1 (recursive directory scanning); remaining items below are
unscheduled follow-ups.

**Tests required to mark Done (all pass — 5 tests in `test_feature_04_medium_priority.py`):**
- ✅ `test_load_local_files_recursive` — `load_local_files` walks subdirectories (temp tree
  with nested `.mp3`s); all appear in the local list and respect `max_playlist_items` +
  batched mounting. Supporting: `test_load_local_files_recursive_respects_max_playlist_items`,
  `test_load_local_files_recursive_batched_mounting`, `test_load_local_files_top_level_still_works`.

### feature/05-playlist-search — **DONE** (branch `feature/05-playlist-search`)
Closes Low Priority #1 (playlist search/filter), Winamp-style UI overhaul, and controller architecture
refactor. The thin-orchestrator pattern from feature/01 was restored by extracting 4 controllers
into their own modules.

**New Modules:**
- `volume.py` — `VolumeController` (volume up/down/mute, widget sync)
- `metadata.py` — `MetadataPoller` (stream icy-title + local file tag polling)
- `playlist.py` — `PlaylistLoader` + `PlaylistNavigator` (M3U/local loading + prev/next)
- `tui_app.py` slimmed from ~1072 → ~621 lines as part of the refactor (feature/05); it has since grown as features #08/#09/#10/#11 were added and is currently **749 lines** — the slimming was the key architectural win, not a fixed ceiling.

**Winamp UI Overhaul:**
- `widgets.py` — LED-style NowPlaying (position/time/khz/kbps) with integrated seek bar (● marker)
  rendered as row 2; retro VolumeIndicator (volume bar + MUTE state)
- `screens.py` — Controls bar with prev/next buttons, search input on LocalScreen, loading status
- `musicplayer_tui.css` — Winamp retro theme: LED green (#39ff14), amber (#ffd24a) accents
- Search: `/` to focus, Escape to blur+clear, case-insensitive substring filter on loaded items

**Controller Architecture:**
- `MusicPlayerApp` routes events to controllers instead of containing business logic
- `VolumeController`, `MetadataPoller`, `PlaylistLoader`, `PlaylistNavigator` in separate modules
- Thin delegation methods in `tui_app.py` for backward compatibility with tests

**Tests required to mark Done (all pass — 20 tests in `test_feature_05_playlist_search.py`):**
- ✅ 5 search tests: substring filter, case-insensitive, clear restores, no matches, special chars
- ✅ 6 widget tests: LED display, no position, seek bar, unknown duration, volume bar, muted
- ✅ 4 layout tests: search input, loading status, prev/next buttons, focus search binding
- ✅ 5 additional tests: M3U search, mode-switch state clear, search fallback, local_items storage

**Key Bugs Fixed:**
- ListView timing: `remove_children()` + yield cycles needed before mounting new items
- Filter data vs widgets: `local_items` stores dicts, not widget references
- Mode switch clears `_stream_source` + `currently_playing` to prevent stale metadata
- M3U load cancels pending `$HOME` scan to prevent race condition
- ProgressBar shows metadata for streams (not seek bar) via `stream` reactive flag

### feature/06-fix-ui-alignment — **DONE** (branch `feature/06-fix-ui-alignment`, merged to `main`)
Compacted the layout by merging the separate `ProgressBar` widget into `NowPlaying`, creating a single
2-row Winamp-style display (LED line + seek-bar / stream-metadata line) instead of two stacked rows.

**Changes (merged):**
- `widgets.py` — Removed `ProgressBar` class; added `stream` + `meta` reactives to `NowPlaying`
- `screens.py` — Removed the separate `ProgressBar` yield from `ModeScreen.compose()`
- `tui_app.py` — `action_stop()` / `update_progress()` update `NowPlaying` (not `ProgressBar`)
- `musicplayer_tui.css` — `#now-playing` reduced from `height: 4` to a compact box; tests updated
- All tests retargeted to `NowPlaying` (no `ProgressBar` references remain)

**Status:** 102 tests pass, ruff clean, 53/53 backlog done. `main` is the known-good baseline.

> Follow-up (now RESOLVED): the `#now-playing` box originally clipped its 2nd row at `height: 5`; a later UI-alignment fix raised it to `height: 6` so both rows fit (see Pitfall #19 in the project skill / `docs/AI_TASK_STATE.md`). The `#volume-indicator` is aligned inside `#controls` (`height: 5`).

### feature/08-playback-history — **DONE** (branch `feature/08-playback-history`)
Closes Low Priority #3 (playback history — track recently played items). Adds a `HistoryTracker`
controller that records every played item (radio station or local file) into an in-memory,
most-recent-first list, de-dupes consecutive repeats, and caps at `MAX_HISTORY_ITEMS` (200).

**New module:**
- `history.py` — `HistoryTracker` (`record`, `recent`, `replay`, `clear`) with `@profile` decorators.

**Integration:**
- `tui_app.py` — `self.history_tracker = HistoryTracker(self)` in `__init__`; `record()` called from
  `play_station` (radio) and both branches of `play_local` (URL stream + filesystem). New binding
  `H` (shift+h) → `action_play_history_last()` replays the most recent entry (radio via URL, local via
  `play_local`). `recent_history(n)` thin accessor for tests/UI.
- `constants.py` — `MAX_HISTORY_ITEMS = 200`.

**Tests:** 15 tests in `test_feature_08_playback_history.py` (HistoryTracker unit tests + app
integration: interleaved radio/local ordering, dedup, cap, replay, `H` binding).

**Status:** 117 tests pass (102 + 15), ruff clean, 68/68 backlog done.

### feature/09-shuffle-repeat — **DONE** (branch `feature/09-shuffle-repeat`)
Closes Low Priority #4 (shuffle/repeat modes). Adds app-level `shuffle` (bool) and
`repeat` ("off"|"one"|"all") state; `PlaylistNavigator` honors them in `play_next`/
`play_previous` via a new `_next_index()` helper (deterministic, testable).

**Changes:**
- `playlist.py` — `PlaylistNavigator._next_index(current, count, direction)`:
  - `repeat="one"` → replays current; `repeat="all"` → wraps at both ends;
    `"off"` → stops at first/last.
  - `shuffle=True` → picks a different random item (`random.randrange`, injectable
    via `self._randrange` for deterministic tests). Sequential otherwise.
  - `_play_adjacent_local` / `_play_adjacent_radio` now delegate to `_next_index`
    and no-op when it returns `None`.
- `tui_app.py` — `self.shuffle` / `self.repeat` in `__init__`; new bindings
  `z` → `action_toggle_shuffle`, `r` → `action_cycle_repeat`; actions update the
  `NowPlaying.shuffle` / `NowPlaying.repeat` reactives + post a status message.
- `widgets.py` — `NowPlaying` gains `shuffle` + `repeat` reactives.
- Tests: 20 tests in `test_feature_09_shuffle_repeat.py`.

**Status:** 137 tests pass (117 + 20), ruff clean, 88/88 backlog done.

### feature/10-playlist-export — **DONE** (branch `feature/10-playlist-export`)
Closes Low Priority #6 (playlist export to M3U). Adds a `PlaylistExporter` controller that
serializes the current local playlist (`app.local_items`, an `ItemData` dict) to a standard
EXTINF M3U file. Pure file I/O, fully unit-testable.

**Changes:**
- `src/pytuiplayer/exporter.py` (new) — `PlaylistExporter` with `build_lines(items)` (emits
  `#EXTM3U` + per-item `#EXTINF:<int seconds or -1>,<title>` + `<source>`), `export_m3u(path, items)`,
  and `default_export_path()` (`~/Music/pytuiplayer/playlist.m3u`). `@profile` on each method.
- `tui_app.py` — `self.playlist_exporter = PlaylistExporter(self)` in `__init__`; binding
  `e` → `action_export_playlist()` (exports to the default path, or warns when empty);
  `export_playlist_to(path)` thin accessor for tests/UI.
- Tests: 10 tests in `test_feature_10_playlist_export.py`.

**Status:** 147 tests pass (137 + 10), ruff clean, 98/98 backlog done.

### feature/11-build-pipeline — **DONE** (branch `feature/11-build-pipeline`)
Adds a reproducible build + distribution pipeline so the app can be packaged for
end users (wheel/sdist + one-file binaries) with CI gates and release automation.

**New files:**
- `Makefile` — local build pipeline: `make test`, `make lint`, `make build`
  (wheel+sdist), `make build-exe`, `make dist`, `make clean`.
- `scripts/build_pyinstaller.py` — committed one-file PyInstaller builder. Runs
  `PyInstaller.__main__` with `--onefile --collect-all textual --collect-all mpv`
  and bundles `stations.json` + `musicplayer_tui.css` into the package dir so the
  runtime `Path(__file__).parent` lookup resolves inside the frozen executable.
- `.github/workflows/ci.yml` — merge gate: `ruff check` + `pytest` on push/PR to `main`.
- `.github/workflows/build.yml` — CD: on a `v*` tag (or manual dispatch) builds the
  wheel + sdist and one-file binaries for Linux/macOS/Windows, then drafts a GitHub
  release and attaches every artifact.

**Changed:**
- `pyproject.toml` — version `0.1.0` → `0.2.0`.
- `README.md` — new "Packaging & Distribution" section (source install, wheel,
  one-file binary, CI/CD notes).
- `AGENTS.md` — new build files in Key Files table + a "Packaging & Distribution"
  section documenting the runtime `libmpv` requirement and the local/CI pipelines.

**Verification:**
- `uv run python scripts/build_pyinstaller.py` → built `dist/pytuiplayer` (111M);
  smoke-run rendered the full TUI and exited cleanly (CSS + stations.json resolve inside the bundle).
- `uv build` → wheel + sdist contain `stations.json` and `musicplayer_tui.css`.
- `uv run pytest -q` → **147 passed**; `uv run ruff check .` → All checks passed!.

**Notes / limitations:**
- `python-mpv` loads the *system* `libmpv` at runtime via ctypes — it is NOT bundled,
  so the target machine must have `mpv` installed on PATH for playback to work.
- The legacy `pytuiplayer.spec` is retained only as reference (it is `*.spec`-gitignored
  and does not build cleanly from the repo root); `scripts/build_pyinstaller.py` is canonical.

### feature/12-ui-polish — **DONE** (branch `feature/12-ui-polish`)
Closes several UI polish items identified during the architecture + UI review. All are
small, focused changes with tests following the existing FakeMPV + stub pattern.

**UI improvements (8 items):**
1. Active playback indicator in lists — highlight the current station/local item with
   the orange (#ff9e00) accent via a `.playing` CSS class on the selected ListItem.
2. Current station marker in radio list — show `▶ Station Name` for the active station;
   dim inactive entries (opacity: 0.6). Requires `play_station` to tag the active item.
3. Faster marquee — increase tick rate when title exceeds available width (e.g. 0.2s
   when scrolling vs 0.5s static). Currently 1 char per 0.5s is too slow.
4. Loading / connection state in NowPlaying — show a spinner or "Connecting…" state
   when a stream is launched but ICY metadata hasn't arrived; show "⏳" transport icon.
5. Default local scan to `~/Music` — change `LocalScreen.on_mount` to scan
   `~/Music` (fall back to `$HOME` if the dir doesn't exist) instead of always
   scanning all of `$HOME`.
6. Wider adaptive VolumeIndicator — expand beyond 25 chars when terminal width allows
   (e.g. scale to 40 chars in wide terminals).
7. Button press visual feedback — add `:pressed` pseudo-class styling to control
   buttons (darker background / inset border) so key presses feel responsive.
8. Playlist total time display — show total duration of loaded playlist in the
   loading-status bar (e.g. "✅ Loaded 42 tracks — 2h 15m").

**Tests required:** each change gets a focused unit test. UI changes verified headlessly
via `run_test()` + layout probe (see SKILL references/layout_alignment_probe.md).

**Status:** 156 tests pass (147 original + 9 new in `test_feature_12_ui_polish.py`), ruff clean.

### Low Priority (remaining — unscheduled, in priority order)

**Next up:**

### feature/13-audio-visualizer — **TODO** (branch to be created)
Add real-time audio visualizer — render amplitude/frequency data as ASCII art in the TUI.
Modes: waveform (time-domain), spectrum (frequency-domain via FFT), VU meter.

**Requirements:**
- New `visualizer.py` module — `AudioVisualizer` controller that polls mpv for audio samples
  (via `mpv.player.audio_samples()` or property API) and renders ASCII visualizations.
- NowPlaying widget gains a `visualizer` mode toggle — pressing `v` cycles through:
  - Off (default LED display)
  - Waveform (scrolling amplitude bars)
  - Spectrum (FFT frequency bars)
  - VU meter (stereo level bars)
- Use `numpy` for FFT if available, with a pure-Python fallback (DFT on small windows).
- Render as a compact ASCII grid (e.g. 40x8 chars) in place of the seek bar row.
- Color-coded bars: green (low), amber (mid), red (peak).

**Tests:** ~8 tests — mock audio samples, verify each mode renders correct ASCII output, verify toggle cycling, verify graceful degradation without numpy.

**New dependency:** `numpy` (optional — fallback works without it).

---

**Later:**

7. ~~Add album art / visualizer~~ → folded into `feature/13-audio-visualizer`
5. Add configurable keybindings — user-defined bindings (config file + editor screen)
2. Add station favorites — bookmark frequently played stations (JSON storage + heart icon)

---

## Workflow / Branching Policy

Every feature (and every non-trivial change) is developed on its **own independent branch** and must satisfy the quality gate below before it can be merged to `main`.

- **Branch per feature:** create a dedicated branch for each feature/bugfix (e.g. `feature/NN-short-slug`). Do not pile unrelated work onto one long-lived branch.
- **Tests are the merge gate:** a branch may only move to `main` after `uv run pytest -q` passes — **all tests green, no skips expected on a working machine** (the `network`-marked radio test is allowed to skip only when offline).
- **Lint gate:** `uv run ruff check .` must pass with no errors before merge.
- **One feature = one branch = one reviewable change.** Keep branches focused; split large efforts into smaller, independently-mergeable branches where possible.
- **No merge to `main` with failing tests or lint.** If a test must change, the change and its rationale travel together in the same branch.
- **Document as you go:** update `ROADMAP.md` (mark items Done / add backlog) and `docs/AI_TASK_STATE.md` within the branch so the merge carries its own status.

### Merge / Release Checklist (run before merging a feature branch into `main`)

Run these from the feature branch (and re-run on `main` after the merge) so the next
feature build always starts from a green, known-good state:

1. **Sync:** `git fetch` and ensure `main` has no unmerged commits that conflict
   (`git rev-list --count main..origin/main` → `0`).
2. **Lint gate:** `uv run ruff check .` → `All checks passed!`
3. **Test gate:** `uv run pytest -q` → all passed (the `network` radio test may skip
   only when offline; everything else must be green).
4. **Type/import sanity (optional):** `uv run python -c "import pytuiplayer"` and
   `uv run pytuiplayer` (or `uv run python scripts/run_tui_app_demo.py`) boot cleanly.
5. **Docs in sync:** `ROADMAP.md` and `docs/AI_TASK_STATE.md` reflect the branch's work.
6. **Merge:** `git checkout main && git merge --no-ff feature/<slug>` (the `--no-ff`
   keeps a visible feature boundary in history), then `git push origin main`.
7. **Post-merge verify:** re-run steps 2–3 on `main` to confirm the merge is green.
8. **Next feature:** start the new work on a fresh branch off updated `main`
   (`git checkout main && git pull && git checkout -b feature/<next-slug>`).

> History note: `feature/01-song-duration`, `feature/02-fix-design-flows`, `feature/03-fix-missing-features`,
> and `feature/04-update-medium-priority` have been merged to `main` and pushed. `main` is the
> known-good baseline for the next feature branch.

### Release Cadence Policy (discipline)

Features are rolled into the packaged distribution on a fixed cadence, not ad hoc:

- **Release every 3 merged features.** After the 3rd, 6th, 9th, … feature branch is merged
  to `main`, cut a release: bump `version` in `pyproject.toml`, merge (already done), then
  tag `v<MAJOR>.<MINOR>.0` on `main` to let `.github/workflows/build.yml` build + publish.
- **The build pipeline is the packaging path.** `feature/11-build-pipeline` established
  `Makefile` + `scripts/build_pyinstaller.py` + the CI/release workflows. Releasing = tag a
  `v*` on `main`; do not hand-build artifacts and attach them manually.
- **The 3-feature counter is tracked in `docs/RELEASE_CADENCE.md`** — a one-line log of
  (features-since-last-release → next release number). `scripts/release_cadence.py` prints
  the current count and whether a release is due, derived from merged `feature/*` branches
  in git history (sanity check; the log in the doc is authoritative).
- **Versioning rule:** each cadence release bumps the MINOR version (`0.2.0` → `0.3.0` →
  `0.4.0` …). Patch bumps (`x.y.1`) are reserved for out-of-cadence hotfixes.
- **Scope:** `mpv` stays independent of the package — binaries/wheel rely on `mpv` being
  installed on the target host (python-mpv loads system `libmpv` at runtime). Reaffirmed
  when feature/11 shipped `v0.2.0`.

**Feature → release ledger (running):**
- `v0.1.0` — pre-pipeline baseline (manual; no CI).
- `v0.2.0` — first packaged release (wheel + sdist + per-OS binaries). Shipped after feature/11
  (build pipeline) plus the already-merged feature/08 (playback history), feature/09 (shuffle/repeat),
  and feature/10 (playlist export). It was a 4-branch first cut; the cadence normalizes to 3 merged
  features per release from here. Next release `v0.3.0` is due after 3 more merged feature branches.

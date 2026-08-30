# AI_TASK_STATE.md

## Current Branch
`main` (build pipeline merged + `v0.2.0` published). Working tree contains the new
"release cadence" discipline docs/scripts (uncommitted at time of writing; see Next Step).

## Completed This Session

### feature/11-build-pipeline — Build & Distribution (MERGED + RELEASED)
- Branch `feature/11-build-pipeline` merged to `main` (`--no-ff`), pushed.
- Tagged `v0.2.0` → `.github/workflows/build.yml` built wheel + sdist + per-OS one-file
  binaries and **published** the GitHub release (4 artifacts): `pytuiplayer` (Linux, 113 MB),
  `pytuiplayer.exe` (Windows, 15 MB), `pytuiplayer-0.2.0-py3-none-any.whl` (338 KB),
  `pytuiplayer-0.2.0.tar.gz` (333 KB).
- Release URL: https://github.com/ChetanKnowIt/pytuiplayer/releases/tag/v0.2.0
- `mpv` kept **independent** of the package (user decision): binaries/wheel require `mpv` on
  the target host (python-mpv loads system `libmpv` at runtime). Documented in README/AGENTS.

### Release Cadence discipline (NEW, this turn)
Decision: **cut a release every 3 merged feature branches** (rolling features into the package
on a fixed cadence). Codified in:
- `ROADMAP.md` — new "Release Cadence Policy (discipline)" section (rule, versioning
  `0.x.0` MINOR bumps, scope reaffirmation, feature→release ledger).
- `AGENTS.md` — "Packaging & Distribution" gains the cadence rule + pointer to the ledger/helper.
- `SKILL.md` (project skill) — new "Release Cadence (discipline)" section.
- `docs/RELEASE_CADENCE.md` (new) — authoritative ledger: releases table (v0.1.0 baseline,
  v0.2.0), running counter (features since last release: 0), and a "how to cut a release" recipe.
- `scripts/release_cadence.py` (new) — prints merged `feature/*` branch count (soft hint; branches
  are often deleted post-merge) + the authoritative ledger counter, and whether a release is due.
  Ruff-clean; verified locally: reports last release v0.2.0, 0/3 since, next v0.3.0 after 3 more.

## Verification
- `uv run ruff check .` → **All checks passed!** (incl. `scripts/release_cadence.py`)
- `uv run pytest -q` → **147 passed** (1 radio-integration test skips in CI; 2 benign
  `DirectoryTree.watch_path` coroutine warnings)
- `uv run python scripts/release_cadence.py` → correct output (v0.2.0, 0/3, next v0.3.0)
- CI on main is green; `v0.2.0` release published.

## Architectural decisions
- Packaging path = tag a `v*` on `main` (let `build.yml` build + publish). Never hand-build/attach.
- Release cadence = 3 merged features → MINOR bump + tag. The ledger doc (`docs/RELEASE_CADENCE.md`)
  is authoritative; the script is a git-derived sanity check.
- `mpv` independent of the package (confirmed scope decision).

## Next Step
Commit the release-cadence discipline files on `main` (they are docs/scripts only, no behavior
change) and push. Then resume feature work on fresh branches; when 3 feature branches have merged
since v0.2.0, run the "how to cut a release" recipe (bump to v0.3.0, tag, publish, update ledger).
Remaining ROADMAP Low Priority items (#2 favorites, #5 configurable keys, #7 visualizer) are
unscheduled and untouched.

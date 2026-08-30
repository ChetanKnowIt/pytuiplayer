# AI_TASK_STATE.md

## Current Branch
`feature/11-build-pipeline` — **Build & Distribution pipeline added**, not yet merged
to `main`. 147 tests pass, ruff clean, 98/98 backlog done. (feature/10 playlist-export
remained unmerged on its own branch per prior session; #3/#4 were merged earlier.)

## Completed This Session

### Architecture review (pre-change)
- Repo on `main`, clean working tree; 147 tests, ruff clean (confirmed live).
- Packaging: `uv_build` backend, v0.1.0 at start. `stations.json` + `musicplayer_tui.css`
  load via `Path(__file__).parent` and ARE included in the wheel (verified by building a
  wheel and listing contents). `python -m pytuiplayer` and the `pytuiplayer:main` console
  script both resolve.
- No CI, no `Makefile`, no build automation. A stale `pytuiplayer.spec` existed (gitignored
  `*.spec`, pointed at `pytuiplayer/__main__.py` — only resolves from inside `src/`, so it
  does not build from repo root). Superseded, not deleted.
- Stray bundled data file `src/pytuiplayer/GTA.mp3` (316K) shipped in the wheel but referenced
  nowhere — left as-is (out of scope); flagged for possible removal later.

### feature/11-build-pipeline — Build & Distribution
Adds reproducible packaging for end users.

**New / changed files:**
- `Makefile` (new, ~55 lines) — `make test` / `make lint` / `make build` (wheel+sdist) /
  `make build-exe` / `make dist` / `make clean`. Requires `uv`.
- `scripts/build_pyinstaller.py` (new, ~78 lines) — committed one-file PyInstaller builder:
  runs `PyInstaller.__main__.run` with `--onefile --console --collect-all textual
  --collect-all mpv` and `--add-data` for `stations.json` + `musicplayer_tui.css` into the
  package dir. `@profile` NOT applicable (not a TUI method); kept dependency-free.
- `.github/workflows/ci.yml` (new) — `ruff check` + `pytest -q` gate on push/PR to `main`
  (ubuntu, Python 3.12, `astral-sh/setup-uv@v5` with cache).
- `.github/workflows/build.yml` (new) — on `v*` tag (+ manual dispatch): `python-dist` job
  builds wheel+sdist; `binary` matrix (ubuntu/macos/windows-latest) builds one-file binaries
  via `scripts/build_pyinstaller.py`; `release` job drafts a GitHub release with all artifacts.
- `pyproject.toml` — version `0.1.0` → `0.2.0`.
- `README.md` — new "Packaging & Distribution" section (source install, wheel, one-file
  binary, CI/CD, legacy spec note); test-count wording updated 102 → 147.
- `AGENTS.md` — build files in Key Files table + new "Packaging & Distribution" section
  (build backend, standalone binary, runtime `libmpv` requirement, Makefile, CI/CD, version bump).
- `ROADMAP.md` — new `feature/11-build-pipeline` section documenting file list, verification, limits.

**Verification:**
- `uv run python scripts/build_pyinstaller.py` → built `dist/pytuiplayer` (111M). Smoke run
  with `</dev/null` actually rendered the full TUI and exited cleanly — proving CSS +
  stations.json resolve inside the frozen bundle (no import/data crash).
- `uv build` → produced `pytuiplayer-0.2.0-py3-none-any.whl` + `.tar.gz`; listed contents
  confirm `stations.json` and `musicplayer_tui.css` are packaged. Removed the stale 0.1.0 wheel.
- `uv run ruff check .` → **All checks passed!**
- `uv run pytest -q` → **147 passed** (2 benign `DirectoryTree.watch_path` coroutine warnings).

**Not yet committed/merged** (per repo policy — user did not ask to commit). Branch
`feature/11-build-pipeline` is local; `dist/` + `build/` are gitignored.

## Architectural decisions
- Canonical one-file binary builder is `scripts/build_pyinstaller.py` (committed, repo-root
  relative paths) — NOT the gitignored `pytuiplayer.spec`.
- Data files must ride inside the bundle at the package dir so `Path(__file__).parent` keeps
  resolving; `python-mpv` loads the system `libmpv` at runtime and cannot be frozen, so the
  target host requires `mpv` on PATH (documented in README/AGENTS).
- CI split: `ci.yml` is the merge gate (lint+test only, fast); `build.yml` is release-time only
  (tag-triggered) to avoid burning CI minutes building binaries on every PR.
- No PyPI publish step added (the user asked for packaging + a GitHub Action to package for
  distribution; release assets are attached to a draft GitHub release, which satisfies that).

## Next Step
Merge `feature/11-build-pipeline` to `main` (`--no-ff`) and push, then optionally tag
`v0.2.0` to exercise the build.yml release workflow. If a PyPI publish is desired later, add a
`publish` job to build.yml using `pypa/gh-action-pypi-publish` — out of scope for this task.
Remaining ROADMAP Low Priority items (#2 favorites, #5 configurable keys, #7 visualizer) are
unscheduled and untouched.

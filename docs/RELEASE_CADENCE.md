# Release Cadence Ledger

Discipline (see ROADMAP.md "Release Cadence Policy"): cut a release **every 3 merged
feature branches**, bumping the MINOR version and tagging `v*.*.0` on `main` to let
`.github/workflows/build.yml` build + publish. `mpv` stays independent of the package
(target host must have `mpv` installed). This ledger is the authoritative counter;
`scripts/release_cadence.py` is a git-derived sanity check only.

## Releases

| Version | Date | Features shipped since previous | Notes |
|---------|------|----------------------------------|-------|
| v0.1.0 | (pre-pipeline) | — | Manual baseline, no CI/release workflow. |
| v0.2.0 | 2026-08-30 | #3 history, #4 shuffle/repeat, #6 export, #11 build-pipeline | First packaged release (wheel + sdist + per-OS binaries). 4-feature initial cut; cadence normalizes to 3 from here. |

## Running counter

- Last release: v0.2.0
- Features since last release: 0
- Next release: v0.3.0 — due after 3 more merged feature branches.

## How to cut a release (when 3 features are in)

1. On `main`, bump `version` in `pyproject.toml` to `0.<next-minor>.0`.
2. Commit: `WIP: Bump version to v0.<next-minor>.0 for release <date>` and push `main`.
3. Tag: `git tag -a v0.<next-minor>.0 -m "..." && git push origin v0.<next-minor>.0`.
4. Wait for `.github/workflows/build.yml` to draft the release; publish the draft.
5. Update this ledger: new row + `Features since last release: 0`, and bump the next-release line.

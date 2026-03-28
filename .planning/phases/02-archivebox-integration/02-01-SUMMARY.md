---
phase: 02-archivebox-integration
plan: "01"
subsystem: workflow
tags: [archivebox, act, github-actions, docker, warc, pdf, screenshot]
dependency_graph:
  requires: []
  provides: [archive-job, act-config]
  affects: [.github/workflows/archive-cve.yml, .actrc]
tech_stack:
  added: [archivebox/archivebox Docker image, actions/upload-artifact@v4, nektos/act, catthehacker/ubuntu:act-24.04]
  patterns: [docker one-shot container, GITHUB_ENV for inter-step data, find+sort+tail for dynamic path discovery, chmod 777 for container write permissions]
key_files:
  created: [.actrc]
  modified: [.github/workflows/archive-cve.yml]
decisions:
  - "SAVE_WGET=True kept alongside SAVE_WARC=True due to wget/WARC coupling (issue #1177)"
  - "SAVE_PDF=True explicit — defaults False in ArchiveBox, most common silent failure"
  - "GITHUB_WORKSPACE used (not PWD) for docker volume mount to avoid ACT path resolution bug"
  - "archive job has no needs: prepare — standalone with hardcoded URL, matrix wiring deferred to Phase 3"
  - "chmod 777 on output dir mandatory — ArchiveBox container runs as root"
metrics:
  duration: 99s
  completed: "2026-03-28T22:30:40Z"
  tasks_completed: 2
  files_created: 1
  files_modified: 1
---

# Phase 02 Plan 01: ArchiveBox Archive Job + ACT Config Summary

**One-liner:** ArchiveBox one-shot Docker archive job producing PDF/screenshot/WARC.tgz with ACT `.actrc` for local testing.

## What Was Built

Added a standalone `archive` job to `.github/workflows/archive-cve.yml` that runs ArchiveBox as a Docker one-shot container against a hardcoded test URL (`https://nvd.nist.gov/vuln/detail/CVE-2021-44228`). The job produces three output files (pdf.pdf, screenshot.png, warc.tgz) and uploads them as a GitHub Actions artifact via `upload-artifact@v4`. Created `.actrc` for local ACT execution.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create .actrc for ACT local testing | 18b662c | `.actrc` (created) |
| 2 | Add archive job to archive-cve.yml | f305abe | `.github/workflows/archive-cve.yml` (modified) |

## Key Implementation Details

### .actrc
Three argument lines, no comments (comments not supported in .actrc format):
- Runner image: `ghcr.io/catthehacker/ubuntu:act-24.04`
- Artifact server path: `/tmp/act-artifacts` (required for upload-artifact@v4 under ACT)
- Container architecture: `linux/amd64` (Apple Silicon Docker compatibility)

### archive job
- `continue-on-error: true` — ARCH-04 isolation requirement
- No `needs: prepare` — standalone Phase 2 job; matrix wiring is Phase 3
- `chmod 777` on output dir — container runs as root, needs world-writable mount
- `$GITHUB_WORKSPACE` for volume mount — `$PWD` resolves incorrectly under ACT
- `--depth=0` — archives target URL only, never follows links
- Extractor selection: PDF, screenshot, wget, WARC enabled; all others disabled
- WARC compressed to tgz with `tar -czf` after container exit
- Snapshot dir discovered via `find ... | sort | tail -1` (timestamp-based dir name)
- `ls -la "$SNAPSHOT_DIR"` in step output for empirical filename confirmation on first run
- `if-no-files-found: error` on artifact upload — hard failure if outputs missing

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| SAVE_WGET=True alongside SAVE_WARC=True | ArchiveBox maintainer confirmed WARC is a wget subprocess parameter (issue #1177); disabling wget risks suppressing WARC |
| SAVE_PDF=True explicit | Defaults to False in ArchiveBox — most common silent failure mode |
| No needs: prepare | Phase 2 is standalone validation; Phase 3 adds matrix fan-out |
| GITHUB_WORKSPACE not PWD | PWD resolves to ACT container path, not host workspace path |
| chmod 777 mandatory | ArchiveBox Docker image runs as root; restricted dir permissions cause "Permission denied" |

## Requirements Fulfilled

- ARCH-01: ArchiveBox invoked as Docker one-shot (`docker run --rm`) per URL
- ARCH-02: Produces PDF, screenshot, and compressed WARC (tgz) outputs
- ARCH-03: Only PDF/screenshot/WARC extractors enabled; all others disabled
- ARCH-04: `continue-on-error: true` on archive job
- TEST-01: `.actrc` created with correct runner image, artifact server path, and architecture

## Deviations from Plan

None — plan executed exactly as written. IDE linter warnings for `${{ env.SNAPSHOT_DIR }}` in upload-artifact path are expected false positives (linter cannot statically verify vars set via GITHUB_ENV at runtime).

## Known Stubs

None. The archive job is fully wired for its Phase 2 scope (single hardcoded URL). The hardcoded URL is intentional per plan — Phase 3 replaces it with matrix fan-out from the prepare job.

## Self-Check: PASSED

- `.actrc` exists: FOUND
- `.github/workflows/archive-cve.yml` modified: FOUND
- Commit 18b662c exists: FOUND
- Commit f305abe exists: FOUND
- YAML valid: PASSED (yq)
- All extractor flags present: PASSED
- continue-on-error: true: PASSED

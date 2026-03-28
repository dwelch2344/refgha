---
phase: 01-data-pipeline
verified: 2026-03-28T21:00:00Z
status: human_needed
score: 4/4 must-haves verified
human_verification:
  - test: "Test 2 and 3 from plan 03 checkpoint not confirmed — only Test 1 (CVE-2021-44228) was run during human checkpoint"
    expected: "CVE-1999-0001 exits cleanly with no workflow error and a summary message; lowercase 'cve-2021-44228' fails immediately with error annotation before any curl call"
    why_human: "Plan 03 SUMMARY explicitly deferred Tests 2 and 3. These require live GitHub Actions execution to confirm the guard branch (PIPE-04) and the format-validation early exit work in the actual GHA runner environment."
---

# Phase 01: Data Pipeline Verification Report

**Phase Goal:** The workflow can accept a CVE ID, fetch its reference URLs from CVEProject/cvelistV5 GitHub raw content, and hand a well-formed URL list to downstream jobs
**Verified:** 2026-03-28T21:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can trigger the workflow manually via workflow_dispatch with a CVE ID input | VERIFIED | `workflow_dispatch` trigger at line 4; `cve_id` input declared required at lines 5-9; `inputs.cve_id` used at line 24 (modern syntax, not deprecated `github.event.inputs`) |
| 2 | Given a valid CVE ID, the prepare job fetches GitHub raw content and extracts all reference URLs | VERIFIED | URL construction at lines 38-43 using `1000-block numXXX` arithmetic; curl with `--fail-with-body` at line 48; null-safe jq extraction at lines 52-55 with `(.containers.cna.references // []) \| .[].url` |
| 3 | Given a CVE with zero references, the workflow exits cleanly with a summary (no error, no empty matrix crash) | VERIFIED (code) / HUMAN NEEDED (runtime) | Guard at line 62 (`[ "$REF_COUNT" -eq 0 ]`); emits `has_refs=false`, `matrix=[]`, `ref_count=0`, step summary, then `exit 0`. Runtime confirmation (Test 2) deferred in plan 03 checkpoint. |
| 4 | The prepare job emits a fromJSON-compatible matrix output consumable by downstream jobs | VERIFIED | Job-level outputs block at lines 14-17 wires `steps.extract.outputs.matrix/has_refs/ref_count`; matrix built with `to_entries` + `tojson` at lines 80-83; live run confirmed (GHA run #23694553102, CVE-2021-44228) |

**Score:** 4/4 truths verified (1 has a runtime confirmation gap noted under human verification)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.github/workflows/archive-cve.yml` | Workflow definition with workflow_dispatch trigger and prepare job | VERIFIED | File exists, 93 lines, no placeholder comments remaining, no tabs, structurally well-formed YAML |
| `.github/workflows/archive-cve.yml` | CVE ID format validation | VERIFIED | Regex `^CVE-[0-9]{4}-[0-9]{4,}$` at line 27 with `::error::` annotation; validated before any network call |
| `.github/workflows/archive-cve.yml` | GitHub raw content fetch | VERIFIED | Full URL pattern at line 43: `https://raw.githubusercontent.com/CVEProject/cvelistV5/refs/heads/main/cves/${YEAR}/${NUM_XXX}/CVE-${YEAR}-${NUM}.json` |
| `.github/workflows/archive-cve.yml` | URL extraction, empty guard, matrix output, step summary | VERIFIED | `has_refs` emitted at lines 63 and 85; `containers.cna.references` jq path at line 53; `REF_COUNT` guard at line 62; step summary written in both branches |
| `.github/workflows/archive-cve.yml` | Null-safe jq extraction | VERIFIED | `// []` guard at line 53 prevents jq error on missing references field |
| `.github/workflows/archive-cve.yml` | Empty matrix guard | VERIFIED | `REF_COUNT` variable at line 58; checked with `-eq 0` at line 62 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `workflow_dispatch inputs.cve_id` | `prepare job step id: extract` | bash variable `CVE_ID` | WIRED | `CVE_ID="${{ inputs.cve_id }}"` at line 24; used throughout extraction logic |
| CVE number | GitHub raw URL path segment `{numXXX}` | bash arithmetic `NUM / 1000` + `printf '%dxxx'` | WIRED | Lines 38-40: `NUM_INT` stripped of leading zeros via sed; `BLOCK=$(( NUM_INT / 1000 ))`; `NUM_XXX="${BLOCK}xxx"` |
| `RESPONSE` (curl output) | `URLS` variable | jq null-safe path `(.containers.cna.references // []) \| .[].url` | WIRED | Lines 52-55; `|| true` prevents `set -e` abort on empty output |
| `URLS` variable | `GITHUB_OUTPUT matrix` | jq `-R -s` pipeline with `to_entries` and index embedding | WIRED | Lines 77-83; `printf '%s'` avoids trailing-newline phantom entry; `tojson` produces single-line string |
| `REF_COUNT` check | `has_refs=false` / `GITHUB_STEP_SUMMARY` | bash `if [ $REF_COUNT -eq 0 ]` | WIRED | Lines 62-72; both GITHUB_OUTPUT and GITHUB_STEP_SUMMARY written; `exit 0` for clean success |
| `workflow_dispatch inputs.cve_id` | `prepare job outputs: matrix, has_refs, ref_count` | fetch + extract step | WIRED | Job-level outputs at lines 14-17 reference `steps.extract.outputs.*`; step `id: extract` declared at line 20 |

### Data-Flow Trace (Level 4)

This phase produces a GitHub Actions workflow — no React components or database queries. The data flows are bash variable pipelines within a single step. Verified by tracing from the curl fetch through to the GITHUB_OUTPUT writes.

| Data Variable | Source | Produces Real Data | Status |
|---------------|--------|--------------------|--------|
| `RESPONSE` | `curl --fail-with-body` from GitHub raw content | Yes — live CVE JSON from CVEProject/cvelistV5 | FLOWING |
| `URLS` | `jq -r` extraction from `RESPONSE` | Yes — actual reference URLs extracted from CVE record | FLOWING |
| `REF_COUNT` | `printf '%s' "$URLS" \| grep -c .` | Yes — accurate count of non-empty URL lines | FLOWING |
| `MATRIX` | `printf '%s' "$URLS" \| jq -R -s ... \| tojson` | Yes — real fromJSON-compatible JSON array | FLOWING |
| `matrix` output | `echo "matrix=${MATRIX}" >> "$GITHUB_OUTPUT"` | Yes — wired to job outputs block; confirmed in live run | FLOWING |

### Behavioral Spot-Checks

Step 7b: NOT RUNNABLE in this environment — the artifact is a GitHub Actions workflow that requires the GHA runner environment. No local runnable entry points exist. Live GHA run #23694553102 (CVE-2021-44228) confirmed Test 1 behavior.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| workflow_dispatch trigger present | `grep 'workflow_dispatch' archive-cve.yml` | Found at line 4 | PASS |
| CVE ID validation regex present | `grep 'CVE-\[0-9\]{4}-\[0-9\]{4,}'` | Found at line 27 | PASS |
| GitHub raw content URL constructed | `grep 'raw.githubusercontent.com/CVEProject'` | Found at line 43 | PASS |
| null-safe jq extraction present | `grep 'containers.cna.references'` | Found at line 53 | PASS |
| empty reference guard present | `grep 'REF_COUNT.*-eq 0'` | Found at line 62 | PASS |
| matrix construction with to_entries + tojson | `grep 'to_entries\|tojson'` | Found at lines 80, 82 | PASS |
| No placeholder comments remain | `grep 'extraction pending\|plan 02'` | Not found | PASS |
| No deprecated ::set-output:: syntax | `grep '::set-output::'` | Not found | PASS |
| YAML has no tab characters | tab check | No tabs | PASS |
| Commits e905ae2 and c519764 exist | `git log --oneline` | Both confirmed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PIPE-01 | 01-01-PLAN.md, 01-03-PLAN.md | User can trigger workflow with a single CVE ID via workflow_dispatch | SATISFIED | `workflow_dispatch` trigger; `cve_id` required string input; `inputs.cve_id` at line 24 |
| PIPE-02 | 01-01-PLAN.md, 01-03-PLAN.md | Action fetches CVE JSON from CVEProject/cvelistV5 GitHub raw content | SATISFIED | Full URL at line 43 matches required pattern including `{year}/{numXXX}/CVE-{id}.json`; curl with `--fail-with-body` |
| PIPE-03 | 01-02-PLAN.md, 01-03-PLAN.md | Action extracts all reference URLs from the API JSON response | SATISFIED | null-safe jq at lines 52-55; matrix array with `{index, url}` objects built at lines 77-83; confirmed in live run |
| PIPE-04 | 01-02-PLAN.md, 01-03-PLAN.md | Action handles CVEs with zero references gracefully (no-op, clear summary) | SATISFIED (code) / NEEDS RUNTIME CONFIRMATION | Guard at lines 62-72; `exit 0`; step summary writes "No References Found"; Test 2 deferred in plan 03 checkpoint |

All four requirement IDs (PIPE-01 through PIPE-04) appear in the plans for this phase. No orphaned requirements found — REQUIREMENTS.md traceability table maps exactly PIPE-01 through PIPE-04 to Phase 1.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | — | — | — |

No TODOs, FIXMEs, placeholders, hardcoded empty returns, or deprecated GHA syntax found. The plan 01 placeholder block (`Extraction, empty guard, and matrix output will be added in plan 02`) was confirmed absent — it was fully replaced by commit c519764.

### Human Verification Required

#### 1. PIPE-04 Zero-Reference Guard (Test 2)

**Test:** Trigger the "Archive CVE References" workflow from the GitHub Actions UI with input `CVE-1999-0001`
**Expected:** Prepare job completes with a green checkmark (no workflow-level error). Job summary shows "No References Found" or a small reference count. If `has_refs=false`: the log shows `matrix=[]`, `ref_count=0`, and the step exits cleanly. No matrix-related GHA error.
**Why human:** Plan 03 SUMMARY explicitly deferred this test. The empty-reference guard (`exit 0` inside the `REF_COUNT -eq 0` branch) must be confirmed in the actual GHA runner environment — particularly that `fromJSON([])` does not trigger a workflow-level failure when `has_refs=false` is set. Static code analysis confirms the guard is implemented correctly, but the GHA empty-matrix edge case requires live confirmation.

#### 2. Format Validation Early Exit (Test 3)

**Test:** Trigger the workflow with input `cve-2021-44228` (lowercase)
**Expected:** Prepare job fails immediately (red) with a visible error annotation "Invalid CVE ID format: 'cve-2021-44228'". No curl fetch is attempted — the log should not show "Fetching: https://raw.githubusercontent.com/...".
**Why human:** Plan 03 SUMMARY deferred this test. The format validation at line 27 uses a bash `=~` regex match and a `::error::` annotation before `exit 1`. While the code path is clearly correct, confirming the annotation surfaces correctly in the GHA UI requires a live run.

### Gaps Summary

No gaps blocking goal achievement. All four phase truths are verified at the code level:
- PIPE-01 and PIPE-02 confirmed both statically and via live GHA run (CVE-2021-44228, run #23694553102).
- PIPE-03 confirmed statically and via the same live run.
- PIPE-04 is verified at code level (guard logic, `exit 0`, step summary output) but the live run confirmation for the zero-reference branch (Test 2) and the format-validation branch (Test 3) was explicitly deferred in the plan 03 checkpoint.

The two human verification items are runtime confirmations of already-correct code paths, not missing implementations. The phase goal is achievable with the current codebase; the human tests provide final confidence on GHA-specific edge cases.

---

_Verified: 2026-03-28T21:00:00Z_
_Verifier: Claude (gsd-verifier)_

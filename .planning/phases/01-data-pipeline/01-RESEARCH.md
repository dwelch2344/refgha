# Phase 1: Data Pipeline - Research

**Researched:** 2026-03-28
**Domain:** GitHub Actions workflow — workflow_dispatch, MITRE CVE API, jq/bash data pipeline, fromJSON matrix output
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PIPE-01 | User can trigger workflow with a single CVE ID via workflow_dispatch | workflow_dispatch input syntax verified; string type with required:true and description is the correct pattern |
| PIPE-02 | Action fetches CVE data from MITRE public API (`https://cveawg.mitre.org/api/cve/{CVE-ID}`) | API endpoint verified live; returns CVE JSON 5.x; no auth required; curl --fail-with-body is the right error-catching flag |
| PIPE-03 | Action extracts all reference URLs from the API JSON response | Verified field path `.containers.cna.references[].url` against live CVE-2021-44228 (60+ refs) and CVE-1999-0001 (2 refs); jq null-safe extraction pattern documented |
| PIPE-04 | Action handles CVEs with zero references gracefully (no-op, clear summary) | Empty matrix is a GHA workflow-level error; must check ref count before matrix construction and emit $GITHUB_STEP_SUMMARY instead |
</phase_requirements>

---

## Summary

Phase 1 builds the prepare job: a self-contained GitHub Actions job that accepts a CVE ID via `workflow_dispatch`, fetches the MITRE public API, extracts reference URLs, handles edge cases (invalid IDs, API errors, zero references), and emits a `fromJSON`-compatible matrix output for downstream jobs.

All four requirements (PIPE-01 through PIPE-04) are implementable with native GHA runner tools: Bash, `curl`, and `jq`. No additional installs are needed. The MITRE API is public, returns a stable CVE JSON v5 schema, and requires no authentication. The field path `.containers.cna.references[].url` was verified against live API responses for multiple CVEs.

The single highest-risk item in this phase is the empty-matrix edge case (PIPE-04). GitHub Actions treats an empty `fromJSON` matrix as a workflow-level error — this cannot be handled downstream. The prepare job must check the reference count before setting the matrix output and exit cleanly with a job summary if zero references are found. Everything else in this phase is a well-documented GHA pattern with HIGH confidence.

**Primary recommendation:** Implement the prepare job as a single-job workflow with one `run` step using bash + jq + curl. Keep the matrix output as a JSON array of objects (`[{"url":"...","index":0}, ...]`) embedding an explicit index. Gate on empty references before setting matrix output.

---

## Standard Stack

### Core

| Library/Tool | Version | Purpose | Why Standard |
|-------------|---------|---------|--------------|
| GitHub Actions | N/A | Workflow runtime | Project requirement; no infrastructure needed |
| `ubuntu-latest` runner | Current (24.04) | Job execution environment | Pre-installs curl, jq, bash; no setup overhead |
| `curl` | pre-installed | MITRE API fetch | Native to runner; `--fail-with-body` gives clean error handling |
| `jq` | pre-installed (1.6+) | JSON extraction and matrix construction | Native to runner; null-safe paths handle reserved CVEs cleanly |
| `workflow_dispatch` | N/A | Manual trigger with CVE ID input | The only trigger type that accepts user input without a PR/push event |

### Supporting

| Library/Tool | Version | Purpose | When to Use |
|-------------|---------|---------|-------------|
| `$GITHUB_OUTPUT` | N/A | Pass matrix JSON to downstream jobs | Only correct mechanism for inter-job data in GHA |
| `$GITHUB_STEP_SUMMARY` | N/A | Write Markdown summary to job summary | Use for zero-reference no-op message and success summary |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Bash + jq + curl | Python script | Python adds install step on some runners; overkill for fetch+parse |
| Bash + jq + curl | Node.js script | Same — over-engineering for this task |
| `workflow_dispatch` | `repository_dispatch` | `repository_dispatch` requires a PAT and API call to trigger; `workflow_dispatch` is directly user-triggerable from GitHub UI and CLI |

**Installation:** No installs required. All tools are pre-installed on `ubuntu-latest`.

---

## Architecture Patterns

### Recommended Workflow Structure

```
.github/
└── workflows/
    └── archive-cve.yml   # single workflow file for all phases
```

Phase 1 defines the `prepare` job. Downstream jobs (`archive`, `collect`) are added in later phases.

### Pattern 1: workflow_dispatch with CVE ID Input

**What:** Defines a manual trigger that accepts a single CVE ID string from the GitHub UI or `gh workflow run`.
**When to use:** This is the PIPE-01 pattern — the workflow entry point.

```yaml
# Source: https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#workflow_dispatch
on:
  workflow_dispatch:
    inputs:
      cve_id:
        description: 'CVE ID to archive (e.g. CVE-2021-44228)'
        required: true
        type: string
```

**Note:** Use `inputs.cve_id` (not `github.event.inputs.cve_id`) in expressions — the `inputs` context preserves types correctly. For string inputs this doesn't matter, but the pattern is correct.

### Pattern 2: MITRE API Fetch with Error Handling

**What:** Fetches the CVE record from the MITRE public API. `--fail-with-body` makes curl exit non-zero on HTTP 4xx/5xx and includes the body in stderr for debugging.
**When to use:** PIPE-02 pattern — the API client.

```yaml
# Source: verified against https://cveawg.mitre.org/api/cve/CVE-2021-44228
- name: Fetch CVE data
  id: fetch
  run: |
    CVE_ID="${{ inputs.cve_id }}"
    RESPONSE=$(curl --fail-with-body --silent --show-error \
      "https://cveawg.mitre.org/api/cve/${CVE_ID}")
    echo "response<<EOF" >> "$GITHUB_OUTPUT"
    echo "$RESPONSE" >> "$GITHUB_OUTPUT"
    echo "EOF" >> "$GITHUB_OUTPUT"
```

**Caution:** Storing full API response in `$GITHUB_OUTPUT` works for typical CVEs, but the 1 MB per-job output limit could theoretically be hit for CVEs with very large records. For Phase 1, parse the response in the same step rather than storing the full body.

### Pattern 3: URL Extraction with Null-Safe jq

**What:** Extracts `references[].url` values from the CVE v5 JSON. The null-safe `//empty` guard handles CVEs where `.containers.cna.references` is absent (reserved or structurally atypical CVEs).
**When to use:** PIPE-03 pattern — the extraction logic.

```bash
# Source: verified field path against live MITRE API responses (CVE-2021-44228, CVE-1999-0001, CVE-2024-0001)
URLS=$(echo "$RESPONSE" | jq -r '
  (.containers.cna.references // [])
  | .[].url
  // empty
')
```

### Pattern 4: Matrix JSON Construction with Embedded Index

**What:** Builds the `fromJSON`-compatible matrix as an array of objects with both `url` and `index` fields. Embedding the index at construction time avoids the "matrix job index not a built-in variable" pitfall — `strategy.job-index` is not accessible inside matrix job steps in all GHA versions.
**When to use:** The output format for downstream jobs.

```bash
# Build matrix JSON
MATRIX=$(echo "$URLS" | jq -R -s '
  split("\n")
  | map(select(length > 0))
  | to_entries
  | map({"index": .key, "url": .value})
')
echo "matrix=$(echo "$MATRIX" | jq -c '.')" >> "$GITHUB_OUTPUT"
```

### Pattern 5: Empty Reference Guard (PIPE-04)

**What:** Checks reference count before emitting matrix output. An empty `fromJSON` matrix causes a GHA workflow-level error — it cannot be caught downstream. The check must happen in the prepare job.
**When to use:** Mandatory guard around every matrix output.

```bash
REF_COUNT=$(echo "$URLS" | grep -c . || true)

if [ "$REF_COUNT" -eq 0 ]; then
  echo "### CVE ${CVE_ID}: No references found" >> "$GITHUB_STEP_SUMMARY"
  echo "This CVE has no reference URLs. Nothing to archive." >> "$GITHUB_STEP_SUMMARY"
  # Set empty-safe sentinel output
  echo "matrix=[]" >> "$GITHUB_OUTPUT"
  echo "has_refs=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

echo "has_refs=true" >> "$GITHUB_OUTPUT"
echo "ref_count=${REF_COUNT}" >> "$GITHUB_OUTPUT"
```

Downstream jobs guard on `has_refs`:
```yaml
archive:
  needs: prepare
  if: needs.prepare.outputs.has_refs == 'true'
  strategy:
    matrix:
      ref: ${{ fromJSON(needs.prepare.outputs.matrix) }}
```

### Pattern 6: Job Output Declaration

**What:** Job-level `outputs` block declaring which step outputs to expose to downstream jobs. Must be declared at the job level, not just written to `$GITHUB_OUTPUT`.
**When to use:** Any job that passes data to a `needs:` dependent job.

```yaml
jobs:
  prepare:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.extract.outputs.matrix }}
      has_refs: ${{ steps.extract.outputs.has_refs }}
      ref_count: ${{ steps.extract.outputs.ref_count }}
    steps:
      - name: Fetch and extract references
        id: extract
        run: |
          # ... script body ...
```

### Anti-Patterns to Avoid

- **Storing full API response as job output:** The 1 MB job output limit can be exceeded for large CVEs. Parse within the same step instead of storing the raw response.
- **Using `github.event.inputs.cve_id` for string comparisons:** Prefer `inputs.cve_id`. While equivalent for strings today, `inputs` is the modern context.
- **Setting matrix output to `[]` and letting downstream `fromJSON` handle it:** GHA treats empty matrix as an error regardless. The `if: has_refs == 'true'` guard on downstream jobs is the only safe pattern.
- **Constructing artifact names from URL strings:** URLs with query params produce collisions. The index embedded in matrix JSON must be used as the artifact name suffix.
- **Not declaring job-level `outputs`:** Writing to `$GITHUB_OUTPUT` in a step does not automatically expose it to downstream jobs — the job `outputs:` block is required.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON parsing | Custom regex/awk JSON parser | `jq` (pre-installed) | jq handles null values, nested paths, and array operations without escaping nightmares |
| HTTP error detection | Manual HTTP status code checking | `curl --fail-with-body` | Cleanly exits non-zero on 4xx/5xx; includes body in stderr |
| Matrix construction | String concatenation to build JSON | `jq -R -s` pipeline | jq guarantees valid JSON; string concatenation breaks on URLs with special characters |
| CVE ID validation | Complex bash string parsing | regex in `if` condition or simple pattern check | `[[ "$CVE_ID" =~ ^CVE-[0-9]{4}-[0-9]{4,}$ ]]` is sufficient; no library needed |
| Job summary formatting | Custom HTML/markdown builder | Heredoc with `>> "$GITHUB_STEP_SUMMARY"` | Native GHA feature; renders in GitHub UI |

**Key insight:** Every operation in this phase (API fetch, JSON parse, string manipulation) has a pre-installed native tool. Adding scripts in Python or Node would require install steps and add complexity with no benefit.

---

## Common Pitfalls

### Pitfall 1: Empty Matrix Causes Workflow-Level Error

**What goes wrong:** A CVE with zero references causes `fromJSON(needs.prepare.outputs.matrix)` to evaluate to an empty matrix. GitHub Actions treats this as a workflow configuration error, not a skipped job. The run fails with an error, not a clean no-op.
**Why it happens:** GHA validates matrix values at runtime; an empty array is not a valid strategy configuration.
**How to avoid:** Check reference count in the prepare step before setting matrix output. Set `has_refs=false` and skip matrix jobs with `if: needs.prepare.outputs.has_refs == 'true'`. Write a summary to `$GITHUB_STEP_SUMMARY` explaining zero refs were found.
**Warning signs:** Workflow fails on valid CVE IDs that happen to have no references (reserved CVEs, CVEs with no external advisories).

### Pitfall 2: MITRE API Returns 404 for Non-Existent CVE IDs

**What goes wrong:** An invalid or non-existent CVE ID returns HTTP 404. Without `--fail-with-body`, `curl` exits 0, `jq` receives an HTML error page, and the extraction silently produces garbage or empty output.
**Why it happens:** `curl` by default exits 0 for all HTTP responses including error codes.
**How to avoid:** Always use `curl --fail-with-body --silent --show-error`. The step will fail with a non-zero exit code and the response body will appear in the runner log.
**Warning signs:** Workflow appears to succeed but emits zero URLs for a valid CVE.

### Pitfall 3: Reserved/Rejected CVEs Lack `containers.cna.references`

**What goes wrong:** Reserved CVEs (state: `RESERVED`) and some rejected CVEs may not have the `.containers.cna` path or `.references` array. A bare `jq '.containers.cna.references[].url'` will exit non-zero on null input.
**Why it happens:** CVE JSON v5 schema does not require `containers.cna.references` to be present.
**How to avoid:** Use null-safe jq: `(.containers.cna.references // []) | .[].url // empty`. This produces zero lines of output (not an error) when references are absent.
**Warning signs:** Step fails with `jq: error (at <stdin>:0): null (null) has no keys` for reserved CVEs.

### Pitfall 4: Job Output Size Limit (1 MB)

**What goes wrong:** Very large CVEs with many long URLs could approach the 1 MB per-job output limit. The output is silently truncated, producing an incomplete matrix.
**Why it happens:** GHA enforces a hard 1 MB limit per job output, approximated using UTF-16 encoding.
**How to avoid:** Parse and build matrix JSON in the same step as the API fetch — do not store the full API response as an output. The matrix JSON itself (URLs only) is far smaller than the full CVE record.
**Warning signs:** Matrix fan-out processes fewer URLs than expected for CVEs with large reference sets.

### Pitfall 5: Missing Job-Level `outputs:` Declaration

**What goes wrong:** Steps write to `$GITHUB_OUTPUT` but downstream jobs cannot read the values via `needs.prepare.outputs.*`.
**Why it happens:** Step outputs are scoped to the step. To expose them to other jobs, they must be explicitly re-declared in the job's `outputs:` block.
**How to avoid:** For every value that must be accessible downstream, add it to the job's `outputs:` block: `matrix: ${{ steps.extract.outputs.matrix }}`.
**Warning signs:** Downstream job sees empty string for `needs.prepare.outputs.matrix`; `fromJSON('')` raises an error.

### Pitfall 6: CVE ID Input Not Validated Before API Call

**What goes wrong:** User passes a malformed string (e.g., `cve-2021-44228` lowercase, or arbitrary text). The API returns a 404 or unexpected response.
**Why it happens:** `workflow_dispatch` string inputs are not validated by GHA.
**How to avoid:** Add a simple format check at the top of the prepare step: `[[ "$CVE_ID" =~ ^CVE-[0-9]{4}-[0-9]{4,}$ ]]`. Exit 1 with a clear message if it fails.
**Warning signs:** API returns 404 for inputs that look like CVE IDs but are malformed.

---

## Code Examples

### Complete Prepare Step (consolidated)

```bash
# Source: Verified against MITRE API live responses (2026-03-28)
# Field path .containers.cna.references[].url confirmed for CVE-2021-44228, CVE-1999-0001, CVE-2024-0001, CVE-2024-12345

set -euo pipefail

CVE_ID="${{ inputs.cve_id }}"

# Validate CVE ID format
if [[ ! "$CVE_ID" =~ ^CVE-[0-9]{4}-[0-9]{4,}$ ]]; then
  echo "Error: Invalid CVE ID format: $CVE_ID" >&2
  echo "Expected format: CVE-YYYY-NNNNN" >&2
  exit 1
fi

# Fetch from MITRE API
RESPONSE=$(curl --fail-with-body --silent --show-error \
  "https://cveawg.mitre.org/api/cve/${CVE_ID}")

# Extract reference URLs (null-safe — handles reserved/rejected CVEs)
URLS=$(echo "$RESPONSE" | jq -r '
  (.containers.cna.references // [])
  | .[].url
' 2>/dev/null || true)

# Count references
REF_COUNT=$(echo "$URLS" | grep -c . 2>/dev/null || echo "0")

if [ "$REF_COUNT" -eq 0 ]; then
  echo "has_refs=false" >> "$GITHUB_OUTPUT"
  echo "matrix=[]" >> "$GITHUB_OUTPUT"
  {
    echo "### ${CVE_ID}: No References"
    echo ""
    echo "This CVE has no reference URLs. Nothing to archive."
  } >> "$GITHUB_STEP_SUMMARY"
  exit 0
fi

# Build matrix JSON with embedded index
MATRIX=$(echo "$URLS" | jq -R -s '
  split("\n")
  | map(select(length > 0))
  | to_entries
  | map({"index": .key, "url": .value})
  | tojson
')

echo "has_refs=true" >> "$GITHUB_OUTPUT"
echo "ref_count=${REF_COUNT}" >> "$GITHUB_OUTPUT"
echo "matrix=${MATRIX}" >> "$GITHUB_OUTPUT"

{
  echo "### ${CVE_ID}: ${REF_COUNT} references found"
  echo ""
  echo "Matrix prepared for archiving."
} >> "$GITHUB_STEP_SUMMARY"
```

### Workflow Skeleton for Phase 1

```yaml
# Source: GHA workflow_dispatch documentation + verified patterns
name: Archive CVE References

on:
  workflow_dispatch:
    inputs:
      cve_id:
        description: 'CVE ID to archive (e.g. CVE-2021-44228)'
        required: true
        type: string

jobs:
  prepare:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.extract.outputs.matrix }}
      has_refs: ${{ steps.extract.outputs.has_refs }}
      ref_count: ${{ steps.extract.outputs.ref_count }}
    steps:
      - name: Fetch and extract CVE references
        id: extract
        run: |
          # ... (complete step body above) ...
```

---

## MITRE API Reference

**Endpoint:** `https://cveawg.mitre.org/api/cve/{CVE-ID}`
**Auth:** None required
**Schema:** CVE JSON 5.x

**Verified response structure** (live calls against CVE-2021-44228, CVE-1999-0001, CVE-2024-0001, CVE-2024-12345 on 2026-03-28):

```
Root keys:
  dataType      string
  dataVersion   string
  cveMetadata   object
    .cveId      string   (e.g. "CVE-2021-44228")
    .state      string   ("PUBLISHED" | "REJECTED" | "RESERVED")
  containers    object
    .cna        object
      .references  array (MAY BE ABSENT for reserved/rejected CVEs)
        .[].url     string  ← extraction target
        .[].name    string  (optional)
        .[].tags    array   (optional)
  adp           array
```

**Error behavior:**
- Non-existent CVE ID: HTTP 404 (verified: `CVE-2025-99999` returns 404)
- Malformed ID: HTTP 404 or 400 depending on format
- `curl --fail-with-body` exits non-zero on any 4xx/5xx

**Field path confidence:** HIGH — verified against 4 live CVE records including a 1999 CVE (old schema), a 2021 high-profile CVE (60+ references), and two 2024 CVEs. The `.containers.cna.references` path is consistent across CVE v5 records.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `set-output` workflow command | `$GITHUB_OUTPUT` env file | GHA deprecation (2022) | Old `::set-output::` syntax is deprecated; must use `echo "key=value" >> "$GITHUB_OUTPUT"` |
| `actions/upload-artifact@v3` | `actions/upload-artifact@v4` | v3 deprecated 2024 | v4 required for `merge-multiple`; v3 should not be used in new workflows |
| `github.event.inputs` context | `inputs` context | GHA enhancement | `inputs` context preserves boolean types; prefer `inputs` over `github.event.inputs` |

**Deprecated/outdated:**
- `::set-output name=X::VALUE` syntax: deprecated, replaced by `$GITHUB_OUTPUT` env file. Use `echo "X=VALUE" >> "$GITHUB_OUTPUT"`.
- `actions/upload-artifact@v3`: deprecated. All new workflows must use v4.

---

## Open Questions

1. **MITRE API behavior for RESERVED CVEs**
   - What we know: The `.containers.cna` object or `.references` array may be absent for RESERVED CVEs; null-safe jq handles this
   - What's unclear: Whether RESERVED CVEs return HTTP 200 with a reduced JSON body, or whether the API returns a different status code
   - Recommendation: The null-safe jq pattern plus `--fail-with-body` handles both cases safely. If needed, check `cveMetadata.state` in the response and emit a specific summary message for reserved CVEs.

2. **CVE ID format validation strictness**
   - What we know: Standard format is `CVE-YYYY-NNNNN` where NNNNN is 4+ digits
   - What's unclear: Whether MITRE accepts lowercase or alternate formats and returns data vs. 404
   - Recommendation: Enforce uppercase `^CVE-[0-9]{4}-[0-9]{4,}$` in the validation step. Fail fast with a clear error rather than letting the API return a 404 with a confusing message.

---

## Environment Availability

All tools required for Phase 1 are pre-installed on `ubuntu-latest` GHA runners. No external services require setup beyond network access.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `curl` | MITRE API fetch (PIPE-02) | Yes (pre-installed) | 7.x+ | None needed |
| `jq` | JSON extraction (PIPE-03) | Yes (pre-installed) | 1.6+ | None needed |
| `bash` | Scripting | Yes (pre-installed) | 5.x | None needed |
| MITRE CVE API | PIPE-02, PIPE-03 | Yes (public endpoint) | v5 schema | None — required |

**Missing dependencies with no fallback:** None.

**Note:** This phase has no Docker dependency, no ArchiveBox, and no ACT requirement. All execution is pure GHA + shell.

---

## Sources

### Primary (HIGH confidence)
- Live MITRE API calls (2026-03-28) — verified field path `.containers.cna.references[].url` against CVE-2021-44228 (60+ refs), CVE-1999-0001 (2 refs), CVE-2024-0001 (1 ref), CVE-2024-12345 (multiple refs)
- Live MITRE API 404 — verified non-existent CVE `CVE-2025-99999` returns HTTP 404
- GitHub Actions `workflow_dispatch` docs — https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#workflow_dispatch
- GitHub Actions job outputs — https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/defining-outputs-for-jobs

### Secondary (MEDIUM confidence)
- GitHub Actions limits documentation (job output 1 MB limit) — https://docs.github.com/en/actions/reference/limits — reported by search results; not directly fetched
- PITFALLS.md project research (2026-03-28) — empty matrix pitfall, artifact naming, matrix index
- STACK.md project research (2026-03-28) — curl/jq/bash stack, fromJSON pattern

### Tertiary (LOW confidence — training knowledge, not freshly verified)
- `jq` null-safe path syntax (`// empty`, `// []`) — standard jq behavior, LOW risk of change
- GHA `$GITHUB_STEP_SUMMARY` and `$GITHUB_OUTPUT` env file syntax — introduced 2022, stable

---

## Metadata

**Confidence breakdown:**
- MITRE API field path: HIGH — verified against 4 live API responses on 2026-03-28
- workflow_dispatch input syntax: HIGH — verified against current official docs
- Empty matrix guard requirement: HIGH — established GHA behavior, cross-referenced with PITFALLS.md
- jq extraction patterns: HIGH — standard jq, verified field paths
- Job output 1 MB limit: MEDIUM — referenced in search results pointing to official docs; not fetched directly

**Research date:** 2026-03-28
**Valid until:** 2026-09-28 (MITRE API schema is stable; GHA workflow syntax changes slowly)

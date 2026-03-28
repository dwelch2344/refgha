# Feature Landscape

**Domain:** CVE reference archiving via GitHub Actions + ArchiveBox
**Researched:** 2026-03-28
**Overall confidence:** MEDIUM — web tools unavailable; based on training knowledge of GitHub Actions, ArchiveBox, MITRE CVE API, and web archiving patterns (training cutoff August 2025). Core GHA and ArchiveBox behaviors are stable; specifics should be verified against current docs.

---

## Table Stakes

Features users expect. Missing = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Accept CVE ID as `workflow_dispatch` input | Entry point for any manual use; without it the action is useless | Low | Input validation (format CVE-YYYY-NNNNN) is table stakes alongside acceptance |
| Fetch CVE metadata from MITRE public API | Core data source; without it there's nothing to archive | Low | `https://cveawg.mitre.org/api/cve/{CVE-ID}` — public, no auth |
| Extract all reference URLs from API response | The whole point is archiving references; partial extraction = silent data loss | Low-Med | API response shape is `cveMetadata.references[].url`; must handle absent/empty references gracefully |
| Archive each URL with ArchiveBox (PDF + screenshot + WARC) | Three output formats are the stated deliverable; missing any one is a regression | Med | ArchiveBox Docker container (`archivebox/archivebox`) run as one-off per URL |
| Per-reference artifact upload | Users need access to individual archives, not just the bundle | Med | Uses `actions/upload-artifact`; naming must be deterministic and collision-safe |
| Bundled per-CVE artifact | One download for all references is basic usability | Med | Requires a collect/bundle job that depends on all matrix jobs |
| Matrix fan-out (one job per reference URL) | Parallelism is the only practical way to handle 2–80+ URLs in a reasonable time | Med | GHA matrix limit is 256 jobs — fine for almost all CVEs |
| Graceful no-op for CVEs with zero references | Silent failure is worse than a clear "nothing to archive" outcome | Low | Empty matrix is invalid in GHA; requires explicit check before matrix step |
| Input validation on CVE ID format | Nonsense input should fail fast with a clear error, not silently archive nothing | Low | Regex: `^CVE-\d{4}-\d{4,}$` |
| Works on `ubuntu-latest` with Docker support | GHA hosted runners are the baseline; Docker must be available | Low | Standard ubuntu-latest runners have Docker; no special setup needed |
| Local testability via ACT | Without local testing, iteration cycle is 5–10 minutes per change | Med | ACT has quirks around matrix jobs and Docker-in-Docker; requires care |

---

## Differentiators

Features that set this tool apart from a naive "curl + wget" approach. Not expected by default, but high value when present.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Compressed WARC output (tgz/zip) | Raw WARC directories are large and awkward; a single compressed archive is portable and storage-efficient | Low-Med | ArchiveBox produces a WARC directory; compression step added in job |
| Batch/scheduled mode (multiple CVEs) | Enables ongoing monitoring workflows — e.g., archive all CVEs published this week | Med | Requires a wrapper job that invokes the single-CVE action in a loop or calls a matrix over CVE IDs |
| Artifact retention policy control | Artifacts expire; tunable retention prevents surprise data loss | Low | `actions/upload-artifact` `retention-days` parameter; default is 90 days |
| Per-URL archive failure isolation | One broken URL should not fail the entire CVE archive run | Med | `continue-on-error: true` on matrix jobs, with status reporting in the summary |
| Workflow summary / job summary output | Post-run visibility — how many URLs archived, which failed, total artifact size | Med | GHA Job Summaries API (`$GITHUB_STEP_SUMMARY`) |
| Idempotency / skip-if-already-archived | Re-running for the same CVE wastes compute and produces duplicate artifacts | Med-High | Requires artifact existence check before running — complex in GHA without external state |
| CVE API response caching | The MITRE API can be slow or rate-limited under batch load | Low-Med | Cache the API response as an artifact or use GHA cache; minimal payoff for single runs |
| Timeout per-URL archive job | Long-running ArchiveBox jobs (paywalled sites, heavy pages) should not block the workflow indefinitely | Low | GHA `timeout-minutes` on the matrix job step |

---

## Anti-Features

Features to explicitly NOT build. Tempting but harmful to scope.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Persistent ArchiveBox instance / database | Running a stateful ArchiveBox service in GHA is fragile — runners are ephemeral, there is no persistent storage | One-off Docker container per URL; no ArchiveBox state between runs |
| Native ArchiveBox install (non-Docker) | Native install has complex system dependencies (Chromium, Node, wget, etc.) that vary by runner image and break unpredictably | Always use `archivebox/archivebox` Docker image |
| Custom ArchiveBox extractors beyond PDF/screenshot/WARC | More output formats = more compute time, larger artifacts, more surface area for breakage | Explicitly disable unused extractors via ArchiveBox config to keep jobs fast |
| Deduplication / content diffing across runs | Comparing archive content over time is a legitimate feature but is downstream of archiving, not part of it | Out of scope for this project per PROJECT.md; belongs in a future storage/indexing layer |
| MITRE API authentication / private CVE data | Private CVEs are outside the stated use case; adding auth would complicate the action significantly | Public API endpoint is sufficient |
| Self-hosted runner targeting | Pinning to self-hosted runners eliminates portability; the action should work anywhere | Default to `ubuntu-latest`; document self-hosted requirements separately if needed |
| Automatic PR or issue creation from results | Notifications and integrations belong in the calling workflow, not the action itself | Keep the action focused; emit artifacts and a job summary, nothing more |
| Storage/indexing of archived content | This is an explicitly deferred third step per PROJECT.md | Future milestone; do not conflate archiving with indexing |
| Rate limiting / politeness delays between URL archives | GHA matrix jobs run concurrently by design; artificially serializing them defeats the purpose | Let GHA control concurrency; if a site blocks the runner IP, that's a user problem |

---

## Feature Dependencies

```
CVE ID input
  → Input validation
    → MITRE API fetch
      → URL extraction
        → [Empty reference check] → no-op if empty
        → Matrix fan-out (one job per URL)
          → ArchiveBox Docker run (PDF + screenshot + WARC)
            → WARC compression (tgz)
              → Per-reference artifact upload
                → Bundle/collect job
                  → Per-CVE artifact upload
                  → Job summary output

Batch/scheduled mode
  → Multiple CVE IDs
    → Loop over single-CVE workflow (above)
```

Key ordering constraints:
- Matrix fan-out cannot happen until URL extraction is complete (dynamic matrix requires a preceding job to emit the list)
- Bundle/collect job has `needs:` dependency on all matrix jobs completing (success or `continue-on-error`)
- Per-reference artifact upload must complete before the bundle job can download and re-pack them
- Compressed WARC is a post-processing step inside each matrix job, before artifact upload

---

## MVP Recommendation

Prioritize (in order):

1. CVE ID input + MITRE API fetch + URL extraction (the data pipeline)
2. ArchiveBox Docker one-off per URL (PDF + screenshot + WARC + compression)
3. Matrix fan-out with per-reference artifact upload
4. Bundle/collect job with per-CVE artifact
5. Graceful empty-reference no-op
6. ACT local test coverage for all of the above

Defer:
- **Batch/scheduled mode**: Get single CVE solid first — PROJECT.md explicitly states this ordering
- **Idempotency/skip-if-archived**: Requires external state; high complexity, low immediate value
- **Job summary output**: Nice to have, low complexity, can be added in a later phase
- **Artifact retention tuning**: One-line addition, add once the happy path is proven

---

## Confidence Notes

| Area | Confidence | Notes |
|------|------------|-------|
| GHA matrix behavior and limits | MEDIUM | Training knowledge; 256-job limit is well-established but should be verified against current GHA docs |
| ArchiveBox Docker one-off pattern | MEDIUM | Pattern is documented in ArchiveBox GitHub and confirmed viable; specific flags for disabling extractors should be verified against current `archivebox/archivebox` image |
| MITRE CVE API response shape | MEDIUM | Public API; response schema is stable but exact field paths (`cveMetadata.references[].url`) should be confirmed against a live API call or current MITRE docs |
| ACT local testing behavior | LOW | ACT has known limitations with Docker-in-Docker and dynamic matrices; must be tested empirically |
| GHA artifact upload limits | MEDIUM | Default 90-day retention and per-artifact size limits (~2GB) are well-established but current limits should be verified |

---

## Sources

- Training knowledge: GitHub Actions documentation (matrix jobs, artifacts, job summaries) — August 2025 cutoff
- Training knowledge: ArchiveBox documentation and Docker usage patterns — August 2025 cutoff
- Training knowledge: MITRE CVE API public endpoint behavior — August 2025 cutoff
- Training knowledge: ACT (nektos/act) capabilities and limitations — August 2025 cutoff
- Web tools unavailable during this research session; all claims should be verified against current official documentation before implementation

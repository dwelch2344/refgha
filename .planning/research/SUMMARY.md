# Project Research Summary

**Project:** CVE Reference Archiver
**Domain:** GitHub Actions workflow — automated web archiving via ArchiveBox
**Researched:** 2026-03-28
**Confidence:** MEDIUM

## Executive Summary

The CVE Reference Archiver is a GitHub Actions workflow that accepts a CVE ID, fetches its reference URLs from the MITRE public API, and archives each URL using ArchiveBox (PDF, screenshot, WARC). The established pattern for this kind of tool is a three-job GHA workflow: a prepare job that produces a dynamic matrix, a fan-out archive job (one job per URL) running ArchiveBox as a Docker one-shot container, and a collect job that bundles all per-reference artifacts into a single per-CVE artifact. No external services or infrastructure are required — the MITRE API is public, ArchiveBox runs in a disposable Docker container, and GHA artifacts handle storage.

The recommended implementation uses only Bash, `jq`, and `curl` — no Python or Node required. The `fromJSON` dynamic matrix pattern is a first-class GHA feature and handles the fan-out without third-party actions. ArchiveBox must be invoked as a Docker one-shot (not installed natively) with non-PDF/screenshot/WARC extractors explicitly disabled to keep jobs fast. Artifacts must use `actions/upload-artifact@v4` (v3 is deprecated and lacks `merge-multiple` support needed in the collect step).

The primary risk area is ACT (local testing), which has known limitations with Docker-in-Docker and dynamic matrices. This must be validated empirically early — local iteration speed depends on it. A secondary risk cluster surrounds ArchiveBox behavior: extractors are on by default, WARC output is a directory not a file, and container permissions require explicit setup. Both risks are manageable with known mitigations but cannot be fully resolved without hands-on testing.

## Key Findings

### Recommended Stack

The entire workflow is implementable with native GHA runner tools — Bash, `jq`, and `curl` are pre-installed on `ubuntu-latest`. ArchiveBox runs as a Docker one-shot container (`archivebox/archivebox`), mounted to the runner workspace, eliminating native install complexity. Artifacts are managed with `actions/upload-artifact@v4` and `actions/download-artifact@v4` (v4 is current stable; v3 is deprecated). Local testing uses `nektos/act` with the `catthehacker/ubuntu:act-24.04` runner image.

**Core technologies:**
- GitHub Actions (`ubuntu-latest`): workflow runtime — zero infrastructure, free for public repos
- Bash + `jq` + `curl`: data pipeline scripting — native to runner, no install overhead
- `archivebox/archivebox` (Docker): archiving engine — isolates dependencies, disposable per-URL
- `actions/upload-artifact@v4` / `download-artifact@v4`: artifact management — v4 required for `merge-multiple`
- `nektos/act` + `catthehacker/ubuntu:act-24.04`: local testing — fast iteration without push-to-test cycle
- MITRE CVE API (`https://cveawg.mitre.org/api/cve/{CVE-ID}`): data source — public, no auth, CVE v5 schema

### Expected Features

**Must have (table stakes):**
- `workflow_dispatch` input with CVE ID validation (`^CVE-\d{4}-\d{4,}$`) — entry point; bad input must fail fast
- MITRE API fetch + URL extraction — core data pipeline; null-safe `jq` paths required for reserved/rejected CVEs
- ArchiveBox Docker one-shot per URL (PDF + screenshot + WARC + compression) — stated deliverable
- Matrix fan-out (one job per reference URL) — only practical way to handle 2–80+ URLs at scale
- Per-reference artifact upload with collision-safe naming (use job index or URL hash, not stripped URL string)
- Bundle/collect job with single per-CVE artifact — basic usability
- Graceful no-op for CVEs with zero references — empty matrix is invalid in GHA; must be checked explicitly
- Local testability via ACT — without this, iteration cycle is 5–10 minutes per change

**Should have (differentiators):**
- Per-URL failure isolation (`continue-on-error: true`) — one broken URL should not abort the run
- Job summary output (`$GITHUB_STEP_SUMMARY`) — post-run visibility on archive count, failures, artifact size
- Artifact retention policy control (`retention-days`) — prevents surprise data loss from default 90-day expiry
- Timeout per matrix job (`timeout-minutes`) — paywalled/heavy pages can block a run indefinitely

**Defer (v2+):**
- Batch/scheduled mode (multiple CVEs) — get single CVE solid first; PROJECT.md explicitly orders this
- Idempotency/skip-if-already-archived — requires external state; high complexity, low immediate value
- CVE API response caching — minimal payoff for single-run use case

### Architecture Approach

The workflow is a linear three-job pipeline with a fan-out in the middle. The prepare job owns API interaction and matrix construction. The archive job matrix owns all ArchiveBox invocations and per-reference artifact uploads. The collect job owns bundling, running with `if: always()` so it completes even when individual archive jobs fail. All inter-job communication flows through GHA artifacts — matrix jobs cannot aggregate outputs across instances, so artifact prefix-pattern downloads in the collect job are the only correct pattern.

**Major components:**
1. **Prepare job** — fetches MITRE API, extracts reference URLs, emits `fromJSON`-compatible matrix via job output; also handles input validation and empty-reference no-op
2. **Archive job (matrix)** — one instance per URL; runs ArchiveBox Docker one-shot with extractors restricted to PDF/screenshot/WARC; compresses WARC directory to tgz; uploads `ref-{index}` artifact
3. **Collect job** — `needs: [archive]` with `if: always()`; downloads all `ref-*` artifacts using `merge-multiple`; bundles into `cve-{ID}-archives.zip`; writes job summary

### Critical Pitfalls

1. **Empty matrix crashes the workflow** — GHA treats an empty matrix as an error. The prepare job must explicitly check reference count and skip the matrix step entirely for CVEs with zero references, emitting a clear summary instead.
2. **ArchiveBox enables all extractors by default** — without explicit env var overrides, jobs run 5+ minutes per URL and produce massive output. Disable all extractors except `SAVE_PDF`, `SAVE_SCREENSHOT`, and `SAVE_WARC` before any testing.
3. **WARC output is a directory, not a file** — ArchiveBox produces a WARC directory; artifact upload will grab the entire tree. An explicit `tar -czf` step must run after the ArchiveBox container exits and before artifact upload.
4. **Artifact name collisions** — using a sanitized URL string as the artifact name causes silent overwrites when URLs differ only by query params. Use the matrix job index (embedded in the matrix JSON during prepare) as the artifact name suffix.
5. **ACT Docker volume mounts resolve incorrectly** — `$PWD` inside Docker-in-Docker under ACT resolves to the wrong path. Use absolute paths derived from `$GITHUB_WORKSPACE` and test ACT compatibility before building on top of it.
6. **Matrix job outputs cannot be aggregated** — collecting results across matrix instances via job outputs does not work in GHA. Use artifact prefix-pattern downloads in the collect job exclusively.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Data Pipeline (Prepare Job)
**Rationale:** All downstream work depends on a working API client and URL extractor. The prepare job has no external dependencies and can be developed and tested in isolation. Building this first validates the MITRE API response shape before investing in ArchiveBox work.
**Delivers:** A working prepare job that accepts a CVE ID, validates the format, fetches the MITRE API, extracts reference URLs, handles empty/reserved CVEs gracefully, and emits a `fromJSON`-compatible matrix.
**Addresses:** CVE ID input validation, MITRE API fetch, URL extraction, empty-reference no-op
**Avoids:** MITRE API schema variation for reserved CVEs (null-safe `jq` paths); `workflow_dispatch` string-vs-boolean input pitfall

### Phase 2: ArchiveBox Integration (Single URL, No Matrix)
**Rationale:** ArchiveBox Docker invocation is the highest-risk component. Validating it end-to-end for a single hardcoded URL before wiring it into the matrix eliminates risk early and provides a working artifact-upload proof-of-concept. ACT Docker-in-Docker issues surface here and must be resolved before fan-out.
**Delivers:** A working ArchiveBox Docker one-shot that produces PDF, screenshot, and compressed WARC for one URL, uploaded as a single artifact.
**Uses:** `archivebox/archivebox` Docker image, `actions/upload-artifact@v4`, `nektos/act`
**Avoids:** All-extractors-on-by-default, WARC-is-a-directory, container permissions, ACT volume mount issues

### Phase 3: Matrix Fan-Out and Full Single-CVE Pipeline
**Rationale:** With both the prepare job and single-URL archiving proven, wiring them together via dynamic matrix is the natural next step. This phase produces the complete end-to-end happy path for a single CVE.
**Delivers:** Full single-CVE workflow: dynamic matrix fan-out, parallel archive jobs with per-URL failure isolation, per-reference artifact uploads, collect/bundle job producing `cve-{ID}-archives.zip`.
**Addresses:** Matrix fan-out, per-reference artifacts, bundle artifact, `fail-fast: false`, collect job with `if: always()`
**Avoids:** Artifact name collisions (job index naming), matrix output aggregation pitfall, `merge-multiple` requirement, bundle size limits

### Phase 4: Polish and Local Testing Hardening
**Rationale:** The happy path is working; this phase makes it production-ready and locally testable. ACT compatibility is a first-class concern — without it, the development workflow for anyone contributing is slow and fragile.
**Delivers:** ACT test coverage for all jobs, job summary output, artifact retention tuning, per-URL timeout, documented edge cases (reserved CVEs, zero references, >256 references).
**Addresses:** Job summary, retention policy, timeouts, ACT artifact v4 issues, `GITHUB_TOKEN` mock for local testing
**Avoids:** ACT artifact v4 incomplete support, silent ACT token failure

### Phase 5: Batch/Scheduled Mode
**Rationale:** PROJECT.md explicitly defers batch mode until the single-CVE workflow is solid. This phase adds a wrapper that loops over multiple CVE IDs, either via a scheduled trigger or an extended `workflow_dispatch` input accepting a list.
**Delivers:** Batch workflow that invokes the single-CVE pipeline for a list of CVE IDs, either on schedule or on demand.
**Addresses:** Batch/scheduled mode, CVE API response caching (low priority, can be added here)

### Phase Ordering Rationale

- The prepare-first order is forced by the dynamic matrix dependency: the matrix cannot exist until URL extraction is proven.
- ArchiveBox-before-matrix isolates the highest-risk component from the fan-out complexity — a failure in Phase 2 is easy to debug; a failure inside a 20-job matrix is not.
- Batch mode last is explicitly required by PROJECT.md and also architecturally correct — batch mode is a wrapper over a working single-CVE workflow.
- Phase 4 polish comes before batch mode because ACT compatibility must be validated for the core workflow before extending it.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (ArchiveBox Integration):** ArchiveBox CLI flags for disabling extractors and exact Docker invocation syntax need verification against the current `archivebox/archivebox` image — training knowledge may be stale.
- **Phase 4 (ACT Hardening):** ACT's support for `upload-artifact@v4` and dynamic matrices is rated LOW confidence; empirical testing will reveal the actual state. Planning should flag this as "spike first."

Phases with standard patterns (skip research-phase):
- **Phase 1 (Data Pipeline):** MITRE API is public and stable; `jq` and `curl` patterns are trivial; GHA `workflow_dispatch` inputs are well-documented.
- **Phase 3 (Matrix Fan-Out):** `fromJSON` dynamic matrix and `actions/download-artifact@v4` with `merge-multiple` are standard, well-documented GHA patterns.
- **Phase 5 (Batch Mode):** Straightforward wrapper over proven Phase 1–3 work; no novel patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Core choices (Bash/jq/curl, artifact v4, Docker one-shot) are high-confidence standard GHA practice; ArchiveBox-specific CLI flags and ACT Docker behavior need empirical validation |
| Features | MEDIUM | GHA matrix limits and artifact size limits are well-established; ArchiveBox extractor config and MITRE API exact field paths should be verified against current docs before implementation |
| Architecture | MEDIUM | Three-job pipeline and `fromJSON` dynamic matrix are standard patterns; ACT compatibility is LOW confidence and must be tested early |
| Pitfalls | MEDIUM | Pitfalls derived from known GHA, Docker, and ACT behavior; ArchiveBox-specific pitfalls (extractor defaults, WARC structure) need empirical confirmation |

**Overall confidence:** MEDIUM

### Gaps to Address

- **ArchiveBox extractor env vars:** Exact environment variable names to disable non-PDF/screenshot/WARC extractors must be confirmed against the current `archivebox/archivebox` Docker image before Phase 2 implementation. Do a quick `docker run archivebox/archivebox help` or check current ArchiveBox docs.
- **MITRE API response field path:** `containers.cna.references[].url` is the expected path for CVE v5 format, but reserved/rejected CVEs have different structures. Confirm with a live API call against a known-good and a known-reserved CVE ID before finalizing the `jq` extraction logic.
- **ACT v4 artifact support:** Must be spiked before Phase 4 planning. If `upload-artifact@v4` is not functional under ACT, a workaround or version pin is needed. This gates local testability for the entire project.
- **GHA matrix job count limit:** 256 is the documented limit but should be verified; CVEs with large reference sets (rare but possible) need a chunking strategy if the limit is lower.

## Sources

### Primary (MEDIUM confidence)
- Training knowledge: GitHub Actions documentation (matrix jobs, dynamic matrix via `fromJSON`, artifacts, job summaries, `workflow_dispatch`) — August 2025 cutoff
- Training knowledge: `archivebox/archivebox` Docker image and ArchiveBox CLI documentation — August 2025 cutoff
- Training knowledge: MITRE CVE API v5 schema and public endpoint behavior — August 2025 cutoff

### Secondary (MEDIUM confidence)
- Training knowledge: `nektos/act` capabilities, limitations, and Docker-in-Docker behavior — August 2025 cutoff
- Training knowledge: `actions/upload-artifact@v4` and `actions/download-artifact@v4` including `merge-multiple` flag — August 2025 cutoff

### Tertiary (LOW confidence — needs empirical validation)
- ACT support for `upload-artifact@v4` and dynamic matrix jobs — behavior may have changed; must test
- ArchiveBox extractor disable env vars — specific flag names need verification against current image

---
*Research completed: 2026-03-28*
*Ready for roadmap: yes*

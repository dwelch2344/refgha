# Requirements — refgha (CVE Reference Archiver)

## v1 Requirements

### Data Pipeline
- [x] **PIPE-01**: User can trigger workflow with a single CVE ID via workflow_dispatch
- [x] **PIPE-02**: Action fetches CVE JSON from CVEProject/cvelistV5 GitHub raw content (`https://raw.githubusercontent.com/CVEProject/cvelistV5/refs/heads/main/cves/{year}/{numXXX}/CVE-{id}.json`)
- [x] **PIPE-03**: Action extracts all reference URLs from the API JSON response
- [x] **PIPE-04**: Action handles CVEs with zero references gracefully (no-op, clear summary)

### Archiving
- [x] **ARCH-01**: Each reference URL is archived by ArchiveBox running as a Docker one-shot container
- [x] **ARCH-02**: Each archive produces PDF, screenshot, and compressed WARC (tgz) outputs
- [x] **ARCH-03**: Only PDF, screenshot, and WARC extractors are enabled (all others disabled)
- [x] **ARCH-04**: Individual URL failures don't kill the entire workflow (continue-on-error)

### Artifact Management
- [x] **ART-01**: Each matrix job uploads its 3 output files as a per-reference GitHub Actions artifact
- [x] **ART-02**: A collect step bundles all per-reference artifacts into a single per-CVE artifact
- [x] **ART-03**: The bundle step runs even if some archive jobs fail (`if: always()`)
- [x] **ART-04**: Workflow summary shows success/failure counts per URL

### Local Testing
- [x] **TEST-01**: Project includes ACT configuration (.actrc) for local workflow execution
- [ ] **TEST-02**: End-to-end test validates the full pipeline with a known CVE ID

### Batch Mode
- [ ] **BATCH-01**: Action accepts a list of CVE IDs (file or multi-line input)

## v2 Requirements (Deferred)

- Cron/scheduled trigger for batch processing
- Mock API responses for offline testing
- CVE ID format validation before API call
- Artifact retention policy configuration
- Progress reporting across multiple CVEs
- Deduplication of already-archived CVEs

## Out of Scope

- Storage/indexing of archived content — future third step
- MITRE API (using GitHub raw content instead)
- Custom ArchiveBox configuration beyond PDF/screenshot/WARC — defaults fine
- Persistent ArchiveBox instance — one-shot containers only

## Traceability

| REQ ID | Phase | Status |
|--------|-------|--------|
| PIPE-01 | Phase 1 | Complete |
| PIPE-02 | Phase 1 | Complete |
| PIPE-03 | Phase 1 | Complete |
| PIPE-04 | Phase 1 | Complete |
| ARCH-01 | Phase 2 | Complete |
| ARCH-02 | Phase 2 | Complete |
| ARCH-03 | Phase 2 | Complete |
| ARCH-04 | Phase 2 | Complete |
| TEST-01 | Phase 2 | Complete |
| ART-01 | Phase 3 | Complete |
| ART-02 | Phase 3 | Complete |
| ART-03 | Phase 3 | Complete |
| ART-04 | Phase 3 | Complete |
| TEST-02 | Phase 3 | Pending |
| BATCH-01 | Phase 4 | Pending |

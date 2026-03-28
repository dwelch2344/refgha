# Requirements — refgha (CVE Reference Archiver)

## v1 Requirements

### Data Pipeline
- [ ] **PIPE-01**: User can trigger workflow with a single CVE ID via workflow_dispatch
- [ ] **PIPE-02**: Action fetches CVE JSON from CVEProject/cvelistV5 GitHub raw content (`https://raw.githubusercontent.com/CVEProject/cvelistV5/refs/heads/main/cves/{year}/{numXXX}/CVE-{id}.json`)
- [ ] **PIPE-03**: Action extracts all reference URLs from the API JSON response
- [ ] **PIPE-04**: Action handles CVEs with zero references gracefully (no-op, clear summary)

### Archiving
- [ ] **ARCH-01**: Each reference URL is archived by ArchiveBox running as a Docker one-shot container
- [ ] **ARCH-02**: Each archive produces PDF, screenshot, and compressed WARC (tgz) outputs
- [ ] **ARCH-03**: Only PDF, screenshot, and WARC extractors are enabled (all others disabled)
- [ ] **ARCH-04**: Individual URL failures don't kill the entire workflow (continue-on-error)

### Artifact Management
- [ ] **ART-01**: Each matrix job uploads its 3 output files as a per-reference GitHub Actions artifact
- [ ] **ART-02**: A collect step bundles all per-reference artifacts into a single per-CVE artifact
- [ ] **ART-03**: The bundle step runs even if some archive jobs fail (`if: always()`)
- [ ] **ART-04**: Workflow summary shows success/failure counts per URL

### Local Testing
- [ ] **TEST-01**: Project includes ACT configuration (.actrc) for local workflow execution
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
| PIPE-01 | Phase 1 | Pending |
| PIPE-02 | Phase 1 | Pending |
| PIPE-03 | Phase 1 | Pending |
| PIPE-04 | Phase 1 | Pending |
| ARCH-01 | Phase 2 | Pending |
| ARCH-02 | Phase 2 | Pending |
| ARCH-03 | Phase 2 | Pending |
| ARCH-04 | Phase 2 | Pending |
| TEST-01 | Phase 2 | Pending |
| ART-01 | Phase 3 | Pending |
| ART-02 | Phase 3 | Pending |
| ART-03 | Phase 3 | Pending |
| ART-04 | Phase 3 | Pending |
| TEST-02 | Phase 3 | Pending |
| BATCH-01 | Phase 4 | Pending |

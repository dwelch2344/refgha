# Roadmap: refgha (CVE Reference Archiver)

## Overview

Four phases deliver a GitHub Action that archives CVE reference URLs into durable formats. The pipeline is built inside-out: the data layer first, then the archiving engine in isolation, then the full fan-out workflow wired together, then batch mode on top of a proven single-CVE foundation.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Data Pipeline** - Prepare job accepts a CVE ID, fetches GitHub raw content, extracts reference URLs, handles edge cases
- [ ] **Phase 2: ArchiveBox Integration** - Single-URL archiving via Docker one-shot produces PDF, screenshot, and compressed WARC
- [ ] **Phase 3: Full Single-CVE Workflow** - Dynamic matrix fan-out, per-reference artifact uploads, and bundle collection wired end-to-end
- [ ] **Phase 4: Batch Mode** - Workflow accepts multiple CVE IDs and invokes the single-CVE pipeline for each

## Phase Details

### Phase 1: Data Pipeline
**Goal**: The workflow can accept a CVE ID, fetch its reference URLs from CVEProject/cvelistV5 GitHub raw content, and hand a well-formed URL list to downstream jobs
**Depends on**: Nothing (first phase)
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04
**Success Criteria** (what must be TRUE):
  1. User can trigger the workflow manually via workflow_dispatch with a CVE ID input
  2. Given a valid CVE ID, the prepare job fetches GitHub raw content and extracts all reference URLs
  3. Given a CVE with zero references, the workflow exits cleanly with a summary (no error, no empty matrix crash)
  4. The prepare job emits a fromJSON-compatible matrix output consumable by downstream jobs
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Workflow scaffold: workflow_dispatch trigger, CVE ID validation, GitHub raw content fetch
- [ ] 01-02-PLAN.md — Extraction and output: null-safe jq URL extraction, empty-reference guard, matrix JSON construction
- [ ] 01-03-PLAN.md — Human verification: end-to-end test against CVE-2021-44228, CVE-1999-0001, and invalid input

### Phase 2: ArchiveBox Integration
**Goal**: A single reference URL can be archived by ArchiveBox running as a Docker one-shot container, producing PDF, screenshot, and compressed WARC outputs, with local ACT testability confirmed
**Depends on**: Phase 1
**Requirements**: ARCH-01, ARCH-02, ARCH-03, ARCH-04, TEST-01
**Success Criteria** (what must be TRUE):
  1. Given a hardcoded reference URL, the archive job produces a PDF file, a screenshot file, and a tgz-compressed WARC archive
  2. Only the PDF, screenshot, and WARC extractors are active — no other ArchiveBox extractors run
  3. If the target URL is unreachable or archiving fails, the job fails gracefully without aborting sibling jobs (continue-on-error)
  4. ACT is configured (.actrc) and the archive job can be executed locally via act
**Plans**: TBD
**UI hint**: no

### Phase 3: Full Single-CVE Workflow
**Goal**: A single CVE ID can be processed end-to-end — prepare, parallel archive fan-out, and artifact collection — producing a single bundled artifact containing all reference archives
**Depends on**: Phase 2
**Requirements**: ART-01, ART-02, ART-03, ART-04, TEST-02
**Success Criteria** (what must be TRUE):
  1. Given a CVE ID with multiple references, the workflow launches one archive job per URL in parallel via dynamic matrix
  2. Each archive job uploads its 3 output files as a uniquely named per-reference artifact (no collisions)
  3. The collect job produces a single per-CVE artifact bundle even when some archive jobs have failed
  4. The workflow summary shows a count of successful and failed archive jobs per URL
  5. An end-to-end test with a known CVE ID passes, confirming the full pipeline works
**Plans**: TBD

### Phase 4: Batch Mode
**Goal**: The workflow can accept a list of CVE IDs and archive references for all of them in a single run
**Depends on**: Phase 3
**Requirements**: BATCH-01
**Success Criteria** (what must be TRUE):
  1. User can trigger the workflow with a multi-line list of CVE IDs (or a file reference) via workflow_dispatch
  2. Each CVE in the list is processed through the full single-CVE pipeline independently
  3. The run produces one bundled artifact per CVE in the input list
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Pipeline | 0/3 | Planned | - |
| 2. ArchiveBox Integration | 0/? | Not started | - |
| 3. Full Single-CVE Workflow | 0/? | Not started | - |
| 4. Batch Mode | 0/? | Not started | - |

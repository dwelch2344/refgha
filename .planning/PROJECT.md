# refgha — CVE Reference Archiver

## What This Is

A GitHub Action that takes a CVE identifier, fetches its references from the CVEProject/cvelistV5 GitHub repo (raw JSON), and archives each reference URL using ArchiveBox — producing PDF, screenshot, and WARC outputs. Designed for local development with ACT and deployment as a standard GitHub Action.

## Core Value

Every reference URL for a given CVE is reliably archived into durable formats (PDF, screenshot, WARC) before the content disappears.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Project configured with ACT for local GitHub Actions testing
- [ ] GitHub Action accepts a CVE ID as input (e.g., CVE-2025-24070)
- [ ] Action fetches CVE data from CVEProject/cvelistV5 GitHub raw content (https://raw.githubusercontent.com/CVEProject/cvelistV5/refs/heads/main/cves/{year}/{numXXX}/CVE-{id}.json)
- [ ] Action extracts all reference URLs from the API response
- [ ] Action fans out into a matrix of jobs — one per reference URL
- [ ] Each matrix job runs ArchiveBox in a Docker container as a one-off
- [ ] Each matrix job produces three outputs: PDF, screenshot (PNG/JPEG), and WARC archive (tgz/zip)
- [ ] Each matrix job uploads its 3 files as a per-reference GitHub Actions artifact
- [ ] A final collection step bundles all per-reference artifacts into one per-CVE artifact
- [ ] Action can be triggered manually via workflow_dispatch with a CVE ID
- [ ] Action supports batch/scheduled mode for processing multiple CVEs
- [ ] Tests exist to prevent regressions across all components
- [ ] ACT tests validate the action works locally before deployment

### Out of Scope

- Storage/indexing of archived content — deferred to a future third step
- MITRE API (using GitHub raw content instead — simpler, no rate limits)
- Processing CVEs without references — no-op is acceptable
- Custom ArchiveBox configuration beyond PDF/screenshot/WARC — defaults are fine

## Context

- Data source: CVEProject/cvelistV5 GitHub repo raw JSON files
- URL pattern: `https://raw.githubusercontent.com/CVEProject/cvelistV5/refs/heads/main/cves/{year}/{numXXX}/CVE-{id}.json`
  - Example: CVE-2025-29002 → `.../cves/2025/29xxx/CVE-2025-29002.json`
  - The `{numXXX}` segment groups CVE numbers into 1000-blocks (e.g., 29002 → 29xxx)
- JSON schema: CVE Record v5.1, references at `.containers.cna.references[].url`
- ArchiveBox runs as a Docker container (`archivebox/archivebox`) for one-off archive jobs
- ArchiveBox outputs: PDF, screenshot (format TBD — PNG or JPEG), WARC directory with resources + tgz
- User wants only the compressed WARC archive (tgz/zip), not the raw WARC directory
- ACT (https://github.com/nektos/act) enables local GHA testing for fast iteration and reproducibility
- Scale varies per CVE — could be 2 references or 80+; matrix must handle both
- Future third step will add storage/indexing of the archived outputs

## Constraints

- **Runtime**: GitHub Actions runners (ubuntu-latest) with Docker support
- **ArchiveBox**: Must run as Docker container, not native install
- **Artifacts**: GitHub Actions artifact size limits apply
- **Matrix**: GitHub Actions matrix job limit (256 jobs) may constrain very large CVEs
- **Local testing**: Must work with ACT for local development

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| ACT for local testing | Fast iteration + reproducibility ("works on my box" that scales to deploy) | — Pending |
| ArchiveBox via Docker | One-off container runs are cleaner than native install in GHA | — Pending |
| Per-reference + bundled artifacts | Granular access to individual archives + convenient per-CVE download | — Pending |
| Manual dispatch first, batch later | Get single CVE working before scaling to batch processing | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-28 after initialization*

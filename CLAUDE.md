# refgha

## Project Overview
<!-- Describe your project here -->

## Development

### Setup
<!-- Add setup instructions -->

### Testing
<!-- Add test commands -->

### Building
<!-- Add build commands -->

<!-- GSD:project-start source:PROJECT.md -->
## Project

**refgha — CVE Reference Archiver**

A GitHub Action that takes a CVE identifier, fetches its references from the MITRE CVE API, and archives each reference URL using ArchiveBox — producing PDF, screenshot, and WARC outputs. Designed for local development with ACT and deployment as a standard GitHub Action.

**Core Value:** Every reference URL for a given CVE is reliably archived into durable formats (PDF, screenshot, WARC) before the content disappears.

### Constraints

- **Runtime**: GitHub Actions runners (ubuntu-latest) with Docker support
- **ArchiveBox**: Must run as Docker container, not native install
- **Artifacts**: GitHub Actions artifact size limits apply
- **Matrix**: GitHub Actions matrix job limit (256 jobs) may constrain very large CVEs
- **Local testing**: Must work with ACT for local development
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Workflow Runtime
- **GitHub Actions** on `ubuntu-latest`
- **Scripting:** Bash + `jq` + `curl` — no Python/Node needed
- **Rationale:** All operations are API fetch + JSON parse + Docker run + file manipulation. Shell tools are native to GHA runners, zero install overhead.
### Dynamic Matrix
- **Pattern:** `fromJSON(needs.setup.outputs.matrix)` for fan-out from a prior job
- **Rationale:** Standard GHA pattern for variable-length matrix; no third-party action needed
### Archiving
- **Image:** `archivebox/archivebox` Docker image (latest)
- **Mode:** One-off container per URL — no persistent ArchiveBox instance
- **Config:** Extractor env vars to disable unused outputs (only PDF, screenshot, WARC)
- **Rationale:** Docker one-shot is cleaner than native install, isolated per-URL, disposable
### Artifacts
- **Upload:** `actions/upload-artifact@v4`
- **Download:** `actions/download-artifact@v4`
- **Note:** v3 is deprecated — must use v4
- **Rationale:** v4 supports `merge-multiple` for the bundle step
### Local Testing
- **Tool:** `nektos/act`
- **Runner image:** `catthehacker/ubuntu:act-24.04` (or similar ACT-compatible image)
- **Config:** `.actrc` in project root for default flags
- **Rationale:** Fast iteration, reproducibility, catches workflow syntax errors before push
### MITRE CVE API
- **Endpoint:** `https://cveawg.mitre.org/api/cve/{CVE-ID}`
- **Schema:** CVE v5 format
- **Extraction:** `jq` to pull `.containers.cna.references[].url` (or similar path)
- **Error handling:** `curl --fail-with-body` to catch API errors cleanly
- **Auth:** None required (public endpoint)
## What NOT to Use
| Rejected | Why |
|----------|-----|
| Python/Node scripts | Over-engineering for curl+jq tasks; adds install step |
| Native ArchiveBox install | Slow setup, pollutes runner, version conflicts |
| actions/upload-artifact@v3 | Deprecated, lacks merge-multiple |
| Composite action | Premature abstraction — start with workflow, extract later if needed |
| Persistent ArchiveBox DB | GHA runners are ephemeral, no storage benefit |
| Third-party matrix actions | `fromJSON` is built-in, no dependency needed |
## Versions to Verify
| Component | Expected Version | Verify Against |
|-----------|-----------------|----------------|
| `actions/upload-artifact` | v4 | GitHub Marketplace |
| `actions/download-artifact` | v4 | GitHub Marketplace |
| `archivebox/archivebox` | latest | Docker Hub |
| `nektos/act` | latest | GitHub releases |
| `catthehacker/ubuntu` | act-24.04 | Docker Hub |
| `jq` | pre-installed on ubuntu-latest | GHA runner docs |
## Confidence Levels
| Decision | Confidence | Notes |
|----------|-----------|-------|
| Bash + jq + curl | HIGH | Standard GHA practice, zero overhead |
| ArchiveBox Docker one-shot | MEDIUM | Correct pattern, but exact CLI flags need testing |
| ACT + catthehacker image | MEDIUM | Well-established, but Docker-in-Docker edge cases |
| Dynamic matrix fromJSON | HIGH | Standard GHA pattern, well-documented |
| Artifact v4 | HIGH | Current stable version |
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

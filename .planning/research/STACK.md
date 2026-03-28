# Stack Research — CVE Reference Archiver

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

---
*Confidence: MEDIUM overall — stack choices are standard; ArchiveBox CLI specifics and ACT Docker behavior need empirical validation*

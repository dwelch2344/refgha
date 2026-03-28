# Architecture Research — CVE Reference Archiver

## Components

Three jobs in strict sequence:

### 1. Prepare Job
- Fetches `https://cveawg.mitre.org/api/cve/{CVE-ID}`
- Extracts reference URLs from JSON response
- Emits `fromJSON`-compatible matrix via job `outputs`

### 2. Archive Job (Matrix)
- One job per reference URL
- Runs `docker run --rm archivebox/archivebox add --depth=0 "$URL"` with workspace mounted
- Uploads 3-file artifact (PDF, PNG, WARC tgz) named `ref-{index}`
- `fail-fast: false` — one failure must not kill the whole run

### 3. Collect Job
- `needs: [archive]` with `if: always()` — runs even if some archives fail
- Downloads all `ref-*` artifacts
- Bundles into `cve-{ID}-archives.zip`
- Uploads final per-CVE artifact

## Data Flow

```
CVE ID
  → MITRE API fetch (prepare job)
  → JSON parse → extract references[]
  → Job output: matrix JSON

Matrix JSON
  → fromJSON → N parallel archive jobs
  → Each: docker run archivebox → PDF + PNG + WARC
  → Each: compress WARC → tgz
  → Each: upload-artifact (ref-{index})

All ref-* artifacts
  → download-artifact (pattern: ref-*)
  → Bundle into single zip
  → upload-artifact (cve-{ID}-archives)
```

## Key Patterns

### Dynamic Matrix via Job Output
```yaml
prepare:
  outputs:
    matrix: ${{ steps.extract.outputs.matrix }}
archive:
  needs: prepare
  strategy:
    fail-fast: false
    matrix:
      ref: ${{ fromJSON(needs.prepare.outputs.matrix) }}
```

### ArchiveBox One-Shot
```yaml
- run: |
    docker run --rm \
      -v ${{ github.workspace }}/output:/data \
      archivebox/archivebox \
      add --depth=0 "${{ matrix.ref.url }}"
```

### Bundle with merge
```yaml
collect:
  needs: archive
  if: always()
  steps:
    - uses: actions/download-artifact@v4
      with:
        pattern: ref-*
        merge-multiple: true
    - uses: actions/upload-artifact@v4
      with:
        name: cve-${{ inputs.cve_id }}-archives
        path: .
```

## Constraints

| Factor | Limit | Mitigation |
|--------|-------|------------|
| Matrix jobs | 256 max | Chunk large CVEs into batches |
| Artifact size | 10 GB per artifact | Compress aggressively |
| ACT artifacts | Known gaps | `--artifact-server-path` flag, needs testing |
| ACT dynamic matrix | Edge cases | Empirical validation required |

## Build Order

1. MITRE API client (no deps)
2. ArchiveBox Docker invocation (highest risk — validate early)
3. Single-job wiring (fetch → archive for one URL)
4. Dynamic matrix fan-out
5. Artifact upload + bundle (end-to-end single CVE)
6. Batch mode (multiple CVEs)

---
*Confidence: MEDIUM — established GHA patterns; ACT compatibility LOW, needs empirical testing*

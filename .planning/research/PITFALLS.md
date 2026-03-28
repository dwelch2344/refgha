# Pitfalls Research — CVE Reference Archiver

## Critical (cause rewrites or silent data loss)

### 1. Dynamic matrix output exceeds 1 MB limit
- **Warning signs:** Matrix JSON silently truncated, archive jobs run on partial URL set
- **Prevention:** Check output size before setting; for huge CVEs, chunk into multiple outputs or use artifact file
- **Phase:** Matrix fan-out implementation

### 2. Empty matrix causes workflow failure
- **Warning signs:** CVE with zero references → workflow-level error instead of graceful no-op
- **Prevention:** Check reference count before fan-out; skip matrix if empty, output summary
- **Phase:** Prepare job / error handling

### 3. Matrix job outputs can't be aggregated across instances
- **Warning signs:** Trying to collect outputs from matrix jobs via job outputs — doesn't work
- **Prevention:** Use artifact prefix-pattern downloads in collect job, not job outputs
- **Phase:** Collect/bundle step

### 4. Artifact name collisions from URL sanitization
- **Warning signs:** Artifacts overwrite each other when URLs differ only by query params
- **Prevention:** Use SHA hash of URL or job index, not stripped URL string, for artifact names
- **Phase:** Archive job artifact upload

### 5. Docker volume mounts break under ACT
- **Warning signs:** `$PWD` mounts resolve to wrong path in Docker-in-Docker
- **Prevention:** Use absolute paths; test with ACT early; may need ACT-specific mount workaround
- **Phase:** ACT setup / ArchiveBox integration

### 6. ArchiveBox enables all extractors by default
- **Warning signs:** Jobs take 5+ minutes per URL, produce massive output directories
- **Prevention:** Explicitly disable non-PDF/screenshot/WARC extractors via env vars
- **Phase:** ArchiveBox Docker invocation

### 7. WARC output is a directory, not a file
- **Warning signs:** Artifact upload grabs entire directory tree, huge artifacts
- **Prevention:** Explicit `tar -czf` step after ArchiveBox run, before artifact upload
- **Phase:** Archive job post-processing

## Moderate

### 8. ACT artifact v4 support incomplete
- **Warning signs:** `upload-artifact@v4` fails or no-ops under ACT
- **Prevention:** Test with `--artifact-server-path` flag; may need ACT version pinning
- **Phase:** ACT local testing setup

### 9. Concurrent matrix jobs hammer same domain
- **Warning signs:** Rate limiting, 429s, blocked IPs from reference hosts
- **Prevention:** Document as known limitation; optionally add `max-parallel` to matrix strategy
- **Phase:** Matrix fan-out configuration

### 10. Bundle artifact size limits
- **Warning signs:** 80 refs at ~50 MB each exceeds 2 GB per-artifact cap
- **Prevention:** Compress aggressively; for very large CVEs, split bundle or skip bundle
- **Phase:** Collect/bundle step

### 11. workflow_dispatch boolean inputs arrive as strings
- **Warning signs:** `if: inputs.batch == true` never matches — it's `'true'` (string)
- **Prevention:** Always compare with `'true'` not `true` in conditionals
- **Phase:** Input handling / dispatch trigger

## Minor

### 12. ArchiveBox container user/permissions
- **Warning signs:** Permission denied errors inside container
- **Prevention:** `mkdir -p && chmod 777` output dir before `docker run`
- **Phase:** ArchiveBox Docker invocation

### 13. MITRE API schema varies for reserved/rejected CVEs
- **Warning signs:** `jq` path fails on CVEs without `.containers.cna.references`
- **Prevention:** Use null-safe jq paths (`// empty` or `try-catch`)
- **Phase:** Prepare job / API fetch

### 14. ACT requires explicit flags for GITHUB_TOKEN
- **Warning signs:** Steps using `GITHUB_TOKEN` fail silently under ACT
- **Prevention:** Use `--secret-file` or mock token for local testing
- **Phase:** ACT setup

### 15. Matrix job index not a built-in variable
- **Warning signs:** Can't reference `strategy.job-index` for artifact naming
- **Prevention:** Embed index in matrix JSON explicitly during prepare step
- **Phase:** Prepare job / matrix construction

---
*Confidence: MEDIUM — pitfalls based on known GHA/Docker/ACT patterns; ArchiveBox-specific issues need empirical validation*

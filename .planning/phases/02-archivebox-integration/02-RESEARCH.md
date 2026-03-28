# Phase 2: ArchiveBox Integration - Research

**Researched:** 2026-03-28
**Domain:** ArchiveBox Docker one-shot, GitHub Actions archive job, ACT local testing
**Confidence:** MEDIUM

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ARCH-01 | Each reference URL is archived by ArchiveBox running as a Docker one-shot container | Docker one-shot invocation pattern confirmed; `archivebox/archivebox add --depth=0` is the correct command |
| ARCH-02 | Each archive produces PDF, screenshot, and compressed WARC (tgz) outputs | SAVE_PDF, SAVE_SCREENSHOT, SAVE_WARC are valid env vars; WARC is a directory requiring explicit tar compression |
| ARCH-03 | Only PDF, screenshot, and WARC extractors are enabled (all others disabled) | Full extractor list confirmed with SAVE_* env var names and defaults; exact disable set documented below |
| ARCH-04 | Individual URL failures don't kill the entire workflow (continue-on-error) | Standard GHA `continue-on-error: true` on the job; no ArchiveBox-specific handling needed |
| TEST-01 | Project includes ACT configuration (.actrc) for local workflow execution | ACT .actrc format confirmed; `--artifact-server-path` required for upload-artifact@v4; `catthehacker/ubuntu:act-24.04` image confirmed available |
</phase_requirements>

---

## Summary

Phase 2 adds a single-URL archive job to the existing workflow. ArchiveBox is invoked as a Docker one-shot container (`docker run --rm`) with the workspace mounted as `/data`. The container accepts all extractor configuration via `-e` environment variable flags. The key discipline is **explicit extractor disabling**: most extractors are on by default, and failing to disable them results in jobs that take 5+ minutes and produce gigabytes of output.

The WARC output is not a single file — it is a subdirectory at `archive/{timestamp}/warc/` inside the mounted data directory. An explicit `tar -czf` step must run after the container exits to produce a tgz file suitable for artifact upload. The PDF and screenshot are single files (`pdf.pdf` and `screenshot.png`) in the same snapshot directory.

ACT local testing requires `.actrc` in the project root with the runner image, artifact server path, and a `--secret-file` or `--env-file` for any secrets. `upload-artifact@v4` is confirmed to work under ACT when `--artifact-server-path` is set. Docker socket is mounted automatically by ACT for Docker-in-Docker; `--privileged` may be needed for some operations.

**Primary recommendation:** Build the archive job as a standalone step with a hardcoded test URL before wiring it into the matrix. Validate ArchiveBox extractor behavior and output file locations empirically before Phase 3.

---

## Project Constraints (from CLAUDE.md)

CLAUDE.md is present but contains no actionable directives beyond the GSD workflow enforcement section. The relevant project constraints are:

- ArchiveBox must run as Docker container, not native install
- Runtime is GitHub Actions (ubuntu-latest) with Docker support
- Local testing must work with ACT
- No Python or Node — Bash + jq + curl only
- Use `actions/upload-artifact@v4` (v3 deprecated)
- No persistent ArchiveBox instance — one-shot containers only

---

## Standard Stack

### Core

| Library / Tool | Version | Purpose | Why Standard |
|---------------|---------|---------|--------------|
| `archivebox/archivebox` | `latest` (Docker Hub) | Archiving engine — PDF, screenshot, WARC per URL | Only practical option; official image; no native install needed |
| `actions/upload-artifact` | `v4` | Upload 3 output files as per-reference artifact | v4 is current stable; v3 deprecated and lacks merge-multiple |
| `nektos/act` | latest | Run the archive job locally without pushing | Fast iteration; catches workflow errors before CI |
| `catthehacker/ubuntu` | `act-24.04` (ghcr.io) | ACT runner image matching ubuntu-latest | Confirmed available tag; matches GHA ubuntu-latest environment |
| Bash + `tar` | pre-installed | Compress WARC directory to tgz after container exits | Native to ubuntu-latest runner; no install needed |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|---------------|---------|---------|-------------|
| `docker` CLI | pre-installed on ubuntu-latest | Invoke ArchiveBox one-shot container | All archive steps |
| `GITHUB_WORKSPACE` | GHA env var | Absolute path for volume mount (avoids ACT $PWD bug) | All `docker run -v` invocations |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `archivebox/archivebox` Docker | Native pip install | Docker is required per project constraints; native install would pollute runner and take longer |
| `tar -czf` on runner | Compress inside container | Runner-side compression keeps the container command simple and avoids root permission issues on compressed output |
| `--depth=0` flag | `--depth=1` | depth=0 archives only the target URL; depth=1 follows links and explodes job time/size |

**Installation:**
```bash
# No npm/pip install required.
# ACT install (macOS):
brew install act
# ACT install (Linux):
curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

---

## Architecture Patterns

### Recommended Project Structure

```
.github/
└── workflows/
    └── archive-cve.yml     # Single workflow file — add archive job here
.actrc                      # ACT local config (new file, Phase 2)
output/                     # gitignored — local ACT archive output
```

### Pattern 1: ArchiveBox Docker One-Shot

**What:** Run ArchiveBox as a disposable container per URL with explicit extractor selection.
**When to use:** Every archive step — never run a persistent ArchiveBox instance on GHA runners.

```yaml
# Source: https://github.com/ArchiveBox/ArchiveBox/wiki/Docker
- name: Prepare output directory
  run: |
    mkdir -p "${{ github.workspace }}/output"
    chmod 777 "${{ github.workspace }}/output"

- name: Archive URL with ArchiveBox
  run: |
    docker run --rm \
      -v "${{ github.workspace }}/output:/data" \
      -e SAVE_TITLE=False \
      -e SAVE_FAVICON=False \
      -e SAVE_WGET=False \
      -e SAVE_WARC=True \
      -e SAVE_PDF=True \
      -e SAVE_SCREENSHOT=True \
      -e SAVE_DOM=False \
      -e SAVE_SINGLEFILE=False \
      -e SAVE_READABILITY=False \
      -e SAVE_GIT=False \
      -e SAVE_YTDLP=False \
      -e SAVE_ARCHIVE_DOT_ORG=False \
      archivebox/archivebox \
      add --depth=0 "https://example.com/target"
```

**Critical note:** `SAVE_PDF` defaults to `False` in ArchiveBox — it must be explicitly set to `True`. `SAVE_WARC` is tied to the wget extractor internally but responds to `SAVE_WARC=True/False` as a standalone control.

### Pattern 2: WARC Compression and File Discovery

**What:** After the container exits, find the snapshot directory and compress the WARC subdirectory.
**When to use:** After every ArchiveBox run, before artifact upload.

```bash
# Source: ArchiveBox output structure documentation
# Each snapshot is stored under archive/{timestamp}/
# Files: screenshot.png, pdf.pdf, warc/ (directory)

SNAPSHOT_DIR=$(find "${{ github.workspace }}/output/archive" -mindepth 1 -maxdepth 1 -type d | head -1)

# Compress the WARC directory
tar -czf "${SNAPSHOT_DIR}/warc.tgz" -C "${SNAPSHOT_DIR}" warc/

# Locate individual output files for artifact upload
PDF_FILE="${SNAPSHOT_DIR}/pdf.pdf"
SCREENSHOT_FILE="${SNAPSHOT_DIR}/screenshot.png"
WARC_FILE="${SNAPSHOT_DIR}/warc.tgz"
```

### Pattern 3: ACT .actrc Configuration

**What:** Project-level `.actrc` file that sets persistent ACT defaults.
**When to use:** Any project using ACT for local GHA testing.

```
# .actrc — one argument per line, no comments supported
-P ubuntu-latest=ghcr.io/catthehacker/ubuntu:act-24.04
--artifact-server-path=/tmp/act-artifacts
--container-architecture=linux/amd64
```

**Notes on ACT artifact support:** `upload-artifact@v4` and `download-artifact@v4` both work under ACT when `--artifact-server-path` is set. Without this flag the artifact server does not start and upload/download steps no-op silently.

### Pattern 4: GHA Job with continue-on-error (ARCH-04)

**What:** Isolate per-URL failures so one broken URL does not abort the run.
**When to use:** The archive job (Phase 2) and every matrix instance (Phase 3).

```yaml
# Source: GitHub Actions documentation
archive:
  needs: prepare
  runs-on: ubuntu-latest
  continue-on-error: true   # ARCH-04: one failure must not kill sibling jobs
  steps:
    - name: Archive URL
      # ... ArchiveBox steps ...
```

### Anti-Patterns to Avoid

- **Running without explicit extractor flags:** ArchiveBox enables wget, singlefile, readability, git, dom, and archive.org by default. Omitting disable flags causes 5–10 minute jobs and multi-GB output directories.
- **Using `$PWD` in Docker volume mounts under ACT:** `$PWD` resolves incorrectly inside the ACT container. Always use `$GITHUB_WORKSPACE` for absolute paths.
- **Uploading the raw WARC directory:** `tar -czf` must run before `upload-artifact`. Uploading the `warc/` directory directly produces a large artifact and loses the tgz requirement from ARCH-02.
- **Omitting `chmod 777` on the output directory:** ArchiveBox runs as root inside the container. Without permissive output dir permissions, writes will fail with permission denied.
- **Using `--depth=1`:** Follows links and archives referenced pages recursively. Always use `--depth=0` for single-URL archiving.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Web archiving (PDF, screenshot, WARC) | Custom Chromium/wget scripts | `archivebox/archivebox` Docker image | Handles headless Chrome, warc-warc, readability, auth negotiation — years of edge case handling |
| WARC generation | Custom wget with WARC flags | `SAVE_WARC=True` in ArchiveBox config | WARC spec compliance, timestamp naming, content-type handling |
| Artifact upload/download | Custom S3 or cache step | `actions/upload-artifact@v4` | GHA native, free for public repos, handled retention and size limits |
| Local GHA execution | Custom Docker Compose wrapper | `nektos/act` | Reads the actual .github/workflows/ files, provides GITHUB_* env vars, handles secrets |

**Key insight:** ArchiveBox exists precisely to handle the enormous edge-case surface of archiving arbitrary URLs. The value is in the existing extractor implementations — hand-rolling any part of this loses years of battle-testing.

---

## ArchiveBox Extractor Reference

This is the complete list of `SAVE_*` environment variables confirmed for the current ArchiveBox releases (0.6.x through current). These are the canonical names — not `*_ENABLED` flags, which appear in newer plugin-based docs but the `SAVE_*` names remain the authoritative runtime env vars per multiple cross-referenced sources.

| SAVE_* Variable | Default | Keep for Phase 2? | Notes |
|----------------|---------|-------------------|-------|
| `SAVE_TITLE` | True | False — disable | HTTP fetch of title; not needed |
| `SAVE_FAVICON` | True | False — disable | Small but unnecessary |
| `SAVE_WGET` | True | False — disable | wget HTML archive; WARC is separate |
| `SAVE_WARC` | True | **True — keep** | WARC is generated via wget subprocess; SAVE_WARC=True is the toggle |
| `SAVE_PDF` | **False** | **True — enable** | Must be explicitly enabled — it is OFF by default |
| `SAVE_SCREENSHOT` | True | **True — keep** | Default on; keep |
| `SAVE_DOM` | True | False — disable | DOM capture via Chrome |
| `SAVE_SINGLEFILE` | True | False — disable | SingleFile HTML archiver |
| `SAVE_READABILITY` | True | False — disable | Readability/Mercury text extraction |
| `SAVE_GIT` | True | False — disable | git clone for code repos |
| `SAVE_YTDLP` | False | False — already off | yt-dlp media download |
| `SAVE_ARCHIVE_DOT_ORG` | True | False — disable | Submits URL to Wayback Machine |

**Important:** `SAVE_PDF` defaults to `False`. This is a common source of confusion — the job appears to complete but no PDF file is produced. Always verify `SAVE_PDF=True` is in the env var list.

**WARC note:** ArchiveBox maintainers confirmed (GitHub issue #1177) that "WARC is sort of a lie as it's not really its own extractor, it's just a parameter added when the wget extractor runs." This means `SAVE_WARC=True` but `SAVE_WGET=False` is an untested combination. The safe approach: set `SAVE_WGET=False` only after empirically confirming WARC output is produced. If WARC requires wget enabled, the wget HTML output can be excluded post-hoc from the artifact upload.

---

## Output File Structure

After `docker run ... archivebox/archivebox add --depth=0 $URL`, the mounted data directory contains:

```
output/                             # mounted as /data inside container
├── ArchiveBox.conf
├── index.sqlite3
├── index.html
└── archive/
    └── {timestamp}/                # e.g. 1711234567/
        ├── index.json
        ├── index.html
        ├── screenshot.png          # ARCH-02: screenshot output
        ├── pdf.pdf                 # ARCH-02: PDF output (only if SAVE_PDF=True)
        └── warc/                   # ARCH-02: WARC directory — must compress to tgz
            └── {timestamp}.warc.gz
```

**File discovery pattern:** Because the timestamp is not predictable, use `find` to locate the snapshot directory:
```bash
SNAPSHOT_DIR=$(find output/archive -mindepth 1 -maxdepth 1 -type d | sort | tail -1)
```

---

## Common Pitfalls

### Pitfall 1: SAVE_PDF Defaults Off
**What goes wrong:** Archive job completes successfully but no `pdf.pdf` is produced. Artifact upload proceeds with only screenshot and WARC. Phase success criteria ARCH-02 silently fails.
**Why it happens:** `SAVE_PDF` defaults to `False` in ArchiveBox — PDF generation requires an explicit `SAVE_PDF=True` env var.
**How to avoid:** Always include `-e SAVE_PDF=True` in the docker run command. Verify `pdf.pdf` exists before artifact upload with `test -f "$SNAPSHOT_DIR/pdf.pdf"`.
**Warning signs:** Archive job exits 0, artifact contains only 2 files instead of 3.

### Pitfall 2: WARC Requires wget (Possible)
**What goes wrong:** Setting `SAVE_WGET=False` to suppress wget HTML output also disables WARC generation, because WARC is a wget subprocess parameter internally.
**Why it happens:** ArchiveBox maintainer confirmed in issue #1177: "WARC is not really its own extractor, it's just a parameter added when the wget extractor runs."
**How to avoid:** Option A — leave `SAVE_WGET=True` and `SAVE_WARC=True`; wget HTML output will appear in the snapshot dir but is not uploaded in the artifact. Option B — set `SAVE_WGET=True, SAVE_WARC=True` and exclude the wget HTML from artifact path selection.
**Warning signs:** No `warc/` directory inside the snapshot folder after running with `SAVE_WGET=False`.

### Pitfall 3: Permission Denied Inside Container
**What goes wrong:** `docker run` exits with permission errors writing to mounted `/data` directory.
**Why it happens:** ArchiveBox container runs as root; if the host mount directory is owned by the runner user with restrictive permissions, root writes still fail in some container runtimes.
**How to avoid:** Always `mkdir -p output && chmod 777 output` before the `docker run` step.
**Warning signs:** Container exits non-zero; docker logs contain "Permission denied" writing to `/data/`.

### Pitfall 4: $PWD Wrong Path Under ACT
**What goes wrong:** Volume mount `-v $PWD:/data` resolves to the ACT container's working directory rather than the host workspace, causing ArchiveBox to write to the wrong path or fail to find output.
**Why it happens:** Under ACT's Docker-in-Docker, `$PWD` is the path inside the outer ACT container, not the host path that the inner ArchiveBox container can access.
**How to avoid:** Use `$GITHUB_WORKSPACE` for all volume mount paths. ACT sets `GITHUB_WORKSPACE` to the correct absolute path that inner containers can resolve.
**Warning signs:** ArchiveBox exits successfully but no files appear in `output/archive/`.

### Pitfall 5: ACT Artifact Server Not Started
**What goes wrong:** `upload-artifact@v4` step silently succeeds but artifact is not stored. Subsequent download steps fail to find it.
**Why it happens:** Without `--artifact-server-path`, ACT does not start the artifact server. `ACTIONS_RUNTIME_URL` is not set, and the upload action falls back silently.
**How to avoid:** Include `--artifact-server-path=/tmp/act-artifacts` in `.actrc`. Verify by checking that the specified directory contains files after a test run.
**Warning signs:** Upload step reports success but local artifact directory is empty.

### Pitfall 6: Snapshot Directory Timestamp Not Predictable
**What goes wrong:** Step uses a hardcoded or guessed timestamp path like `output/archive/1711234567/` which doesn't exist, causing `pdf.pdf` and `screenshot.png` path resolution to fail.
**Why it happens:** ArchiveBox names snapshot directories after the Unix timestamp at archive time, which varies per run.
**How to avoid:** Use `find output/archive -mindepth 1 -maxdepth 1 -type d | sort | tail -1` to discover the latest snapshot directory dynamically.
**Warning signs:** `test -f` checks fail even though ArchiveBox reported success.

---

## Code Examples

### Complete Archive Job Step Sequence (Phase 2 scaffold)

```yaml
# Source: GitHub Actions docs + ArchiveBox wiki + ACT docs (synthesized)
archive:
  runs-on: ubuntu-latest
  continue-on-error: true   # ARCH-04

  steps:
    - name: Prepare output directory
      run: |
        mkdir -p "$GITHUB_WORKSPACE/output"
        chmod 777 "$GITHUB_WORKSPACE/output"

    - name: Archive URL with ArchiveBox
      run: |
        docker run --rm \
          -v "$GITHUB_WORKSPACE/output:/data" \
          -e SAVE_TITLE=False \
          -e SAVE_FAVICON=False \
          -e SAVE_WGET=True \
          -e SAVE_WARC=True \
          -e SAVE_PDF=True \
          -e SAVE_SCREENSHOT=True \
          -e SAVE_DOM=False \
          -e SAVE_SINGLEFILE=False \
          -e SAVE_READABILITY=False \
          -e SAVE_GIT=False \
          -e SAVE_YTDLP=False \
          -e SAVE_ARCHIVE_DOT_ORG=False \
          archivebox/archivebox \
          add --depth=0 "https://nvd.nist.gov/vuln/detail/CVE-2021-44228"

    - name: Locate snapshot and compress WARC
      run: |
        set -euo pipefail
        SNAPSHOT_DIR=$(find "$GITHUB_WORKSPACE/output/archive" \
          -mindepth 1 -maxdepth 1 -type d | sort | tail -1)

        if [ -z "$SNAPSHOT_DIR" ]; then
          echo "::error::No snapshot directory found after ArchiveBox run" >&2
          exit 1
        fi

        echo "Snapshot dir: $SNAPSHOT_DIR"

        # Compress WARC directory to tgz (ARCH-02)
        if [ -d "${SNAPSHOT_DIR}/warc" ]; then
          tar -czf "${SNAPSHOT_DIR}/warc.tgz" -C "${SNAPSHOT_DIR}" warc/
          echo "WARC compressed: ${SNAPSHOT_DIR}/warc.tgz"
        else
          echo "::warning::No warc/ directory found — check SAVE_WGET/SAVE_WARC settings"
        fi

        # Verify PDF and screenshot
        test -f "${SNAPSHOT_DIR}/pdf.pdf"   || echo "::warning::pdf.pdf not found"
        test -f "${SNAPSHOT_DIR}/screenshot.png" || echo "::warning::screenshot.png not found"

        # Export paths for upload step
        echo "SNAPSHOT_DIR=${SNAPSHOT_DIR}" >> "$GITHUB_ENV"

    - name: Upload archive artifact
      uses: actions/upload-artifact@v4
      with:
        name: ref-test
        path: |
          ${{ env.SNAPSHOT_DIR }}/pdf.pdf
          ${{ env.SNAPSHOT_DIR }}/screenshot.png
          ${{ env.SNAPSHOT_DIR }}/warc.tgz
        if-no-files-found: error
```

### .actrc (Project Root)

```
# Source: https://nektosact.com/usage/index.html
# One argument per line, no comments supported — remove these comment lines in the actual file
-P ubuntu-latest=ghcr.io/catthehacker/ubuntu:act-24.04
--artifact-server-path=/tmp/act-artifacts
--container-architecture=linux/amd64
```

### ACT Run Command for Archive Job

```bash
# Run just the archive job with a local secret file
act workflow_dispatch \
  -j archive \
  --secret-file .secrets \
  -W .github/workflows/archive-cve.yml
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `FETCH_SCREENSHOT=False` env var | `SAVE_SCREENSHOT=True/False` | ArchiveBox 0.5.x | Old naming still seen in some Docker wiki examples; use `SAVE_*` |
| `actions/upload-artifact@v3` | `actions/upload-artifact@v4` | Nov 2023 | v3 deprecated; v4 required for `merge-multiple` in Phase 3 |
| `catthehacker/ubuntu:act-latest` | `catthehacker/ubuntu:act-24.04` | 2024 | Explicit version pinning preferred over floating `latest` tag |
| `$PWD` in docker volume mounts | `$GITHUB_WORKSPACE` | Known ACT issue | `$PWD` breaks under ACT Docker-in-Docker |

**Deprecated/outdated:**
- `FETCH_SCREENSHOT=False`: Old env var style seen in early Docker wiki; replaced by `SAVE_SCREENSHOT`.
- `actions/upload-artifact@v3`: Deprecated; no longer receiving updates; missing `merge-multiple`.
- `--depth=1` for single-URL archiving: Correct for RSS feeds, wrong for reference URL archiving.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | ArchiveBox one-shot | Yes (ubuntu-latest) | 28.1.1 (local) | None — required by project constraints |
| `act` (nektos/act) | TEST-01 local testing | No (not installed locally) | — | Install: `brew install act` |
| `tar` | WARC compression | Yes (pre-installed) | — | None needed |
| `find` | Snapshot dir discovery | Yes (pre-installed) | — | None needed |
| `ghcr.io/catthehacker/ubuntu:act-24.04` | ACT runner image | Needs pull | — | `act-22.04` as fallback |

**Missing dependencies with no fallback:**
- `act` is not installed locally. Must be installed before TEST-01 can be executed. `brew install act` or script install.

**Missing dependencies with fallback:**
- `catthehacker/ubuntu:act-24.04`: If unavailable, use `catthehacker/ubuntu:act-22.04`. First `act` run will pull the image automatically.

---

## Open Questions

1. **Does `SAVE_WARC=True` work with `SAVE_WGET=False`?**
   - What we know: ArchiveBox maintainer comment (issue #1177) says WARC is "a parameter added when the wget extractor runs," implying wget must be active.
   - What's unclear: Whether a recent version decoupled WARC from wget, or whether `SAVE_WGET=False` always suppresses WARC.
   - Recommendation: Set `SAVE_WGET=True` and `SAVE_WARC=True` in the initial implementation. Verify WARC output exists before attempting to disable wget. If `SAVE_WGET=False` breaks WARC, leave wget enabled and exclude the wget HTML output from the artifact upload step.

2. **Exact PDF filename: `pdf.pdf` or variable?**
   - What we know: Multiple sources reference `pdf.pdf` as the output filename. ArchiveBox documentation and community posts confirm this naming.
   - What's unclear: Whether newer ArchiveBox versions changed the filename.
   - Recommendation: Add a verification step (`ls -la "$SNAPSHOT_DIR"`) that prints the actual filenames on first run, then confirm the find pattern.

3. **ACT Docker socket access on macOS Docker Desktop**
   - What we know: ACT mounts `/var/run/docker.sock` automatically; `--privileged` is available as a flag.
   - What's unclear: Whether Docker Desktop's socket path differs (`/var/run/docker.sock` vs socket in user home) and whether this causes issues with nested Docker in ACT.
   - Recommendation: If `docker run` inside ACT fails to connect to the daemon, add `--privileged` to `.actrc` and verify `/var/run/docker.sock` exists on the host.

---

## Sources

### Primary (HIGH confidence)
- [ArchiveBox/ArchiveBox Wiki — Configuration](https://github.com/ArchiveBox/ArchiveBox/wiki/Configuration) — SAVE_* env var names, extractor defaults
- [ArchiveBox/ArchiveBox Wiki — Docker](https://github.com/ArchiveBox/ArchiveBox/wiki/Docker) — one-shot container invocation pattern, `-e` flag usage
- [nektosact.com — Usage Guide](https://nektosact.com/usage/index.html) — .actrc format, --artifact-server-path, upload-artifact@v4 support
- [mintlify.com/archivebox — Dependencies config](https://www.mintlify.com/archivebox/archivebox/config/dependencies) — complete SAVE_* list with defaults

### Secondary (MEDIUM confidence)
- [ArchiveBox issue #1177](https://github.com/ArchiveBox/ArchiveBox/issues/1177) — WARC/wget coupling clarification from maintainer
- [nektos/act Runners page](https://nektosact.com/usage/runners.html) — catthehacker image list and tier descriptions
- [catthehacker/docker_images](https://github.com/catthehacker/docker_images) — act-24.04 tag availability confirmation
- WebSearch cross-verification of SAVE_* defaults and ArchiveBox output structure

### Tertiary (LOW confidence — needs empirical validation)
- WARC output structure (`archive/{timestamp}/warc/`) — confirmed via multiple sources but exact filename within warc/ needs empirical testing
- `SAVE_WGET=False` + `SAVE_WARC=True` combination — contradicted by maintainer comment; behavior unverified
- ACT Docker socket behavior on macOS Docker Desktop — no official documentation found for edge cases

---

## Metadata

**Confidence breakdown:**
- ArchiveBox SAVE_* env vars: MEDIUM — confirmed names and defaults from official wiki + cross-referenced; empirical validation needed for edge cases
- Docker one-shot invocation: HIGH — standard pattern, well-documented across multiple sources
- WARC/wget coupling: LOW — one maintainer comment is the only source; must test before building on this assumption
- ACT .actrc format and artifact server: HIGH — official nektosact.com docs confirm format and `--artifact-server-path` requirement
- Output file structure: MEDIUM — confirmed directory structure; specific filenames (pdf.pdf, screenshot.png) consistent across sources but need empirical confirmation

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (ArchiveBox is in active development; extractor config may shift in new releases)

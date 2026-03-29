#!/usr/bin/env python3
"""Generate static site data files from S3 bucket listing and CVE index files."""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path


def parse_s3_listing(lines):
    """Parse `aws s3 ls --recursive` output into structured snapshots."""
    snapshots = defaultdict(set)  # s3_prefix -> set of filenames

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Format: 2026-03-28 18:15:20    1077799 v2/domain/path/timestamp/file.ext
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        key = parts[3]

        # Only care about our 3 asset types
        if not key.endswith(('output.pdf', 'screenshot.png', 'warc.tgz')):
            continue

        # Split key into prefix and filename
        key_parts = key.rsplit('/', 1)
        if len(key_parts) == 2:
            prefix, filename = key_parts
            snapshots[prefix].add(filename)

    return snapshots


def prefix_to_url_info(prefix):
    """Parse S3 prefix into domain, path, query, timestamp, original_url."""
    parts = prefix.split('/')
    # v2/<domain>/<path...>[__q__<query>]/<timestamp>
    if len(parts) < 3:
        return None

    timestamp = parts[-1]
    url_parts = parts[1:-1]  # skip 'v2' and timestamp
    domain = url_parts[0]
    uri_path = '/'.join(url_parts[1:]) if len(url_parts) > 1 else ''

    query = ''
    path = uri_path
    if '__q__' in uri_path:
        path, query = uri_path.rsplit('__q__', 1)

    if query:
        original_url = f"https://{domain}/{path}?{query}"
    elif path:
        original_url = f"https://{domain}/{path}"
    else:
        original_url = f"https://{domain}"

    return {
        'domain': domain,
        'path': f"/{path}" if path else '/',
        'query': query,
        'timestamp': timestamp,
        'original_url': original_url,
        's3_prefix': prefix,
    }


def build_domain_data(snapshots):
    """Group snapshots by domain -> URL -> timestamps."""
    domains = defaultdict(lambda: defaultdict(list))

    for prefix, files in snapshots.items():
        info = prefix_to_url_info(prefix)
        if not info:
            continue

        domains[info['domain']][info['original_url']].append({
            'timestamp': info['timestamp'],
            's3_prefix': info['s3_prefix'],
            'files': sorted(files),
        })

    # Build per-domain JSON files
    result = {}
    for domain, urls in sorted(domains.items()):
        url_list = []
        for original_url, snaps in sorted(urls.items()):
            info = prefix_to_url_info(snaps[0]['s3_prefix'])
            snaps.sort(key=lambda s: s['timestamp'], reverse=True)
            url_list.append({
                'original_url': original_url,
                'path': info['path'] if info else '',
                'query': info['query'] if info else '',
                'snapshots': snaps,
            })
        result[domain] = {
            'domain': domain,
            'url_count': len(url_list),
            'urls': url_list,
        }

    return result


def build_cve_data(cve_index_files):
    """Read per-CVE index files from S3."""
    cves = {}
    for path in cve_index_files:
        try:
            with open(path) as f:
                data = json.load(f)
            cve_id = data.get('cve_id', os.path.basename(path).replace('.json', ''))
            cves[cve_id] = data
        except (json.JSONDecodeError, KeyError):
            continue
    return cves


def main():
    docs_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('docs')
    cve_index_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('/tmp/cve-indexes')
    s3_listing = Path(sys.argv[3]) if len(sys.argv) > 3 else Path('/tmp/s3-listing.txt')

    data_dir = docs_dir / 'data'
    domains_dir = data_dir / 'domains'
    cves_dir = data_dir / 'cves'

    domains_dir.mkdir(parents=True, exist_ok=True)
    cves_dir.mkdir(parents=True, exist_ok=True)

    # Parse S3 listing
    with open(s3_listing) as f:
        snapshots = parse_s3_listing(f.readlines())

    print(f"Parsed {len(snapshots)} snapshots from S3 listing")

    # Build domain data
    domain_data = build_domain_data(snapshots)
    for domain, data in domain_data.items():
        out = domains_dir / f"{domain}.json"
        with open(out, 'w') as f:
            json.dump(data, f, separators=(',', ':'))
    print(f"Wrote {len(domain_data)} domain files")

    # Build CVE data
    cve_files = sorted(cve_index_dir.glob('*.json'))
    cve_data = build_cve_data(cve_files)
    for cve_id, data in cve_data.items():
        out = cves_dir / f"{cve_id}.json"
        with open(out, 'w') as f:
            json.dump(data, f, separators=(',', ':'))
    print(f"Wrote {len(cve_data)} CVE files")

    # Build manifest
    total_urls = sum(d['url_count'] for d in domain_data.values())
    total_snapshots = sum(
        sum(len(u['snapshots']) for u in d['urls'])
        for d in domain_data.values()
    )

    manifest = {
        'generated': os.popen('date -u +"%Y%m%d-%H%M%S"').read().strip(),
        'total_domains': len(domain_data),
        'total_urls': total_urls,
        'total_snapshots': total_snapshots,
        'total_cves': len(cve_data),
        'domains': sorted([
            {'domain': d, 'url_count': data['url_count']}
            for d, data in domain_data.items()
        ], key=lambda x: x['url_count'], reverse=True),
        'cves': sorted([
            {'cve_id': cve_id, 'snapshot_count': len(data.get('snapshots', []))}
            for cve_id, data in cve_data.items()
        ], key=lambda x: x['cve_id']),
    }

    with open(data_dir / 'manifest.json', 'w') as f:
        json.dump(manifest, f, separators=(',', ':'))
    print(f"Manifest: {total_urls} URLs, {total_snapshots} snapshots, {len(cve_data)} CVEs")


if __name__ == '__main__':
    main()

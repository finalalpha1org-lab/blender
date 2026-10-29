#!/usr/bin/env python3
# Reports how far this fork is from upstream Blender and checks that the branding
# branch only touches paths listed in tools/rebrand/branding-paths.txt.
#
# Usage: python3 tools/rebrand/check_divergence.py [branch]
# Requires: env GITHUB_TOKEN (read access to the fork) and GITHUB_REPOSITORY.

import json
import os
import sys
import urllib.request

UPSTREAM = 'blender/blender'
FORBIDDEN = [
    'source/blender/blenloader/',
    'source/blender/blenkernel/BKE_blender_version.h',
]

def api(path):
    req = urllib.request.Request(
        'https://api.github.com' + path,
        headers={
            'Authorization': 'Bearer ' + os.environ.get('GITHUB_TOKEN', ''),
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'final-effect-3d-fork-sync',
        },
    )
    with urllib.request.urlopen(req) as response:
        return json.load(response)

def load_patterns():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, 'branding-paths.txt')
    patterns = []
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
    return patterns

def allowed(changed, patterns):
    return any(changed.startswith(pattern) for pattern in patterns)

def main():
    repo = os.environ.get('GITHUB_REPOSITORY', 'finalalpha1org-lab/blender')
    branch = sys.argv[1] if len(sys.argv) > 1 else 'final-effect-3d'
    patterns = load_patterns()
    summary = []
    failures = []

    mirror = api('/repos/' + UPSTREAM + '/compare/main...' + repo + ':main')
    line = 'mirror main vs upstream main: %s (ahead %d, behind %d)' % (
        mirror['status'], mirror['ahead_by'], mirror['behind_by'])
    print(line)
    summary.append(line)
    if mirror['ahead_by'] or mirror['behind_by']:
        print('::warning::fork main is not identical to upstream main - run the sync in docs/SYNC.md')

    comparison = api('/repos/' + UPSTREAM + '/compare/main...' + repo + ':' + branch)
    line = 'branding branch %s vs upstream main: ahead %d, behind %d' % (
        branch, comparison['ahead_by'], comparison['behind_by'])
    print(line)
    summary.append(line)
    if comparison['behind_by'] > 50:
        print('::warning::branding branch is %d commits behind upstream - schedule a rebase' % comparison['behind_by'])

    changed = sorted(item['filename'] for item in comparison.get('files', []))
    print('diverging files: %d' % len(changed))

    unexpected = []
    forbidden = []
    for name in changed:
        if any(name.startswith(prefix) for prefix in FORBIDDEN):
            forbidden.append(name)
        elif not allowed(name, patterns):
            unexpected.append(name)

    if forbidden:
        message = 'files under no-touch paths were modified: ' + ', '.join(forbidden)
        print('::error::' + message)
        failures.append(message)
    if unexpected:
        print('::warning::changes outside the branding allow-list: ' + ', '.join(unexpected[:25]))
        summary.append('WARNING: %d path(s) outside the branding allow-list' % len(unexpected))
    else:
        summary.append('all changed paths are inside the branding allow-list')

    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_path:
        with open(summary_path, 'a', encoding='utf-8') as handle:
            handle.write('### fork-sync report\n\n')
            for item in summary:
                handle.write('- ' + item + '\n')

    return 1 if failures else 0

if __name__ == '__main__':
    sys.exit(main())
#!/usr/bin/env python3
'''Apply Final Effect 3D branding to a checkout of this fork.

Run this after every upstream sync (see docs/SYNC.md). Dry-run by default:

    python3 tools/rebrand/apply_branding.py            # report only
    python3 tools/rebrand/apply_branding.py --apply    # write changes

Guarantees:
  * only paths listed in tools/rebrand/branding-paths.txt are modified
  * no-touch paths (blenloader, file-format constants, licence texts, AUTHORS)
    are never modified
  * attribution lines (SPDX, copyright, licence wording) are never rewritten
  * the pass is idempotent: a second run reports zero replacements
'''

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

NO_TOUCH = (
    'source/blender/blenloader/',
    'source/blender/blenkernel/BKE_blender_version.h',
    'COPYING',
    'AUTHORS',
    'doc/license/',
    'release/license/',
    'locale/',
)

ATTRIBUTION_MARKERS = (
    'spdx-filecopyrighttext',
    'spdx-license-identifier',
    'copyright',
    'license',
    'licence',
    'gpl',
    '@blender.org',
    'blender authors',
)

TEXT_EXTENSIONS = (
    '.py', '.cc', '.hh', '.h', '.c', '.cpp', '.hpp', '.m', '.mm', '.inl',
    '.cmake', '.txt', '.md', '.rst', '.xml', '.json', '.toml', '.yml', '.yaml',
    '.desktop', '.wxs', '.template', '.rc', '.bat', '.sh', '.iss', '.plist',
    '.manifest', '.ts', '.glsl', '.pyi', '.cfg', '.def', '.inc', '.appdata',
)


def load_config():
    values = {}
    with open(os.path.join(HERE, 'brand.conf'), encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            values[key.strip()] = value.strip()
    return values


def load_allow_list():
    patterns = []
    with open(os.path.join(HERE, 'branding-paths.txt'), encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
    return patterns


def allowed(path, patterns):
    if any(path.startswith(blocked) for blocked in NO_TOUCH):
        return False
    return any(path.startswith(pattern) for pattern in patterns)


def tracked_files():
    try:
        out = subprocess.run(['git', 'ls-files'], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout
        return [name for name in out.split('\n') if name]
    except Exception:
        names = []
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d != '.git']
            for name in files:
                names.append(os.path.relpath(os.path.join(base, name), ROOT))
        return names


def is_text(path):
    return path.lower().endswith(TEXT_EXTENSIONS)


def read(path):
    with open(os.path.join(ROOT, path), encoding='utf-8') as handle:
        return handle.read()


def is_attribution(line):
    low = line.lower()
    return any(marker in low for marker in ATTRIBUTION_MARKERS)


def replace_word(text, word, replacement):
    '''Replace standalone occurrences of word without regular expressions.'''
    out = []
    index = 0
    count = 0
    while True:
        hit = text.find(word, index)
        if hit < 0:
            out.append(text[index:])
            break
        before = text[hit - 1] if hit > 0 else ''
        after = text[hit + len(word)] if hit + len(word) < len(text) else ''
        boundary = not (before.isalnum() or before == '_') and not (after.isalnum() or after == '_')
        out.append(text[index:hit])
        if boundary:
            out.append(replacement)
            count += 1
        else:
            out.append(text[hit:hit + len(word)])
        index = hit + len(word)
    return ''.join(out), count


def rewrite(text, tokens):
    '''Apply tokens to a whole file, skipping attribution lines.'''
    lines = text.split('\n')
    total = 0
    result = []
    for line in lines:
        if is_attribution(line):
            result.append(line)
            continue
        new = line
        for token, replacement in tokens:
            new, hits = replace_word(new, token, replacement)
            total += hits
        result.append(new)
    return '\n'.join(result), total


def cmake_identity(text, config, report):
    '''Product identity inside the build system (substring edits, no regex).'''
    edits = [
        ('project(Blender)', 'project(' + config['PRODUCT_SLUG'] + ')'),
        ('BLENDER_WIN_APPID="blender.', 'BLENDER_WIN_APPID="' + config['APP_ID'] + '.'),
        ('BLENDER_WIN_APPID_FRIENDLY_NAME="Blender ', 'BLENDER_WIN_APPID_FRIENDLY_NAME="' + config['PRODUCT_NAME'] + ' '),
    ]
    count = 0
    for old, new in edits:
        if old in text:
            text = text.replace(old, new)
            count += 1
            report.append('identity: ' + old[:48] + ' -> ' + new[:48])
    return text, count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='write changes (default is dry-run)')
    args = parser.parse_args()

    config = load_config()
    patterns = load_allow_list()
    missing = [key for key in ('PRODUCT_NAME', 'PRODUCT_SLUG', 'APP_ID') if not config.get(key)]
    if missing:
        print('brand.conf is missing: ' + ', '.join(missing))
        return 2

    tokens = []
    if config.get('REPLACE_WORD_BLENDER') == '1':
        tokens.append(('Blender', config['PRODUCT_NAME']))
    if config.get('REPLACE_BLENDER_FOUNDATION') == '1':
        tokens.append(('Blender Foundation', config['COMPANY']))
    if config.get('REPLACE_URLS') == '1':
        tokens.append(('blender.org', config.get('URL_REPLACEMENT', '')))
    if config.get('REPLACE_LOWER_BLENDER') == '1':
        tokens.append(('blender', config['PRODUCT_SLUG']))

    report = []
    changed = []
    replacements = 0
    skipped_binary = 0

    for path in tracked_files():
        if not allowed(path, patterns):
            continue
        if not is_text(path):
            skipped_binary += 1
            continue
        try:
            text = read(path)
        except (UnicodeDecodeError, OSError):
            skipped_binary += 1
            continue
        new_text, hits = rewrite(text, tokens)
        if path in ('CMakeLists.txt', 'source/creator/CMakeLists.txt'):
            new_text, identity_hits = cmake_identity(new_text, config, report)
            hits += identity_hits
        if hits and new_text != text:
            replacements += hits
            changed.append((path, hits))
            if args.apply:
                with open(os.path.join(ROOT, path), 'w', encoding='utf-8') as handle:
                    handle.write(new_text)

    print('brand target: ' + config['PRODUCT_NAME'] + '  (app id ' + config['APP_ID'] + ')')
    print('mode: ' + ('APPLY' if args.apply else 'dry-run'))
    print('files with replacements: %d, replacements: %d, non-text files skipped: %d'
          % (len(changed), replacements, skipped_binary))
    for path, hits in changed[:60]:
        print('  %5d  %s' % (hits, path))
    if len(changed) > 60:
        print('  ... and %d more files' % (len(changed) - 60))
    for line in report:
        print('  ' + line)

    print('')
    print('next steps:')
    print('  * artwork that cannot be scripted (splash.png, icons, .blend defaults)')
    print('    still needs manual replacement - see docs/REBRANDING.md section 3.2')
    print('  * build, then walk the verification checklist in docs/REBRANDING.md section 5')
    print('  * review the diff: git diff --name-only -- .  (must stay inside branding-paths.txt)')
    if not args.apply:
        print('  * nothing was written (dry-run)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
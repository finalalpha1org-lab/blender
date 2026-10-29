#!/usr/bin/env python3
'''Apply Final Effect 3D branding to a checkout of this fork.

Run this after every upstream sync (see docs/SYNC.md). Dry-run by default:

    python3 tools/rebrand/apply_branding.py            # report only
    python3 tools/rebrand/apply_branding.py --apply    # write changes

Guarantees:
  * only paths listed in tools/rebrand/branding-paths.txt are modified
  * no-touch paths (blenloader, file-format constants, licence texts, AUTHORS,
    localisation) are never modified
  * our own tooling and documentation are never rewritten by themselves
  * attribution lines (SPDX, copyright, licence wording) are never rewritten
  * build identity is applied before the word pass, so the pass is idempotent:
    a second run reports zero replacements
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

# Our own files: they describe the brand, they are not part of the product.
PROTECTED = (
    'tools/rebrand/',
    '.github/workflows/fork-sync.yml',
    'docs/',
    'tests/',
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

IDENTITY_FILES = ('CMakeLists.txt', 'source/creator/CMakeLists.txt')


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


def skip_reason(path, patterns):
    if any(path.startswith(prefix) for prefix in NO_TOUCH):
        return 'no-touch'
    if any(path.startswith(prefix) for prefix in PROTECTED):
        return 'protected'
    if not any(path.startswith(pattern) for pattern in patterns):
        return 'not allow-listed'
    return None


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


def write(path, text):
    with open(os.path.join(ROOT, path), 'w', encoding='utf-8') as handle:
        handle.write(text)


def is_attribution(line):
    low = line.lower()
    return any(marker in low for marker in ATTRIBUTION_MARKERS)


def replace_word(text, word, replacement):
    '''Replace standalone occurrences of word, without regular expressions.'''
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


def rewrite_lines(text, tokens):
    '''Apply word tokens line by line, skipping attribution lines.'''
    total = 0
    result = []
    for line in text.split('\n'):
        if is_attribution(line):
            result.append(line)
            continue
        new = line
        for token, replacement in tokens:
            new, hits = replace_word(new, token, replacement)
            total += hits
        result.append(new)
    return '\n'.join(result), total


def identity_edits(config):
    app_id = config['APP_ID']
    return (
        ('project(Blender)', 'project(' + config['PRODUCT_SLUG'] + ')'),
        ('BLENDER_WIN_APPID="blender.', 'BLENDER_WIN_APPID="' + app_id + '.'),
        ('BLENDER_WIN_APPID_FRIENDLY_NAME="Blender ', 'BLENDER_WIN_APPID_FRIENDLY_NAME="' + config['PRODUCT_NAME'] + ' '),
    )


def apply_identity(text, edits, report, path):
    '''Build identity first, so the word pass never sees these strings.'''
    count = 0
    for old, new in edits:
        if old in text:
            text = text.replace(old, new)
            count += 1
            report.append('%s: %s -> %s' % (path, old[:46], new[:46]))
    return text, count


def build_tokens(config):
    tokens = []
    if config.get('REPLACE_WORD_BLENDER') == '1':
        tokens.append(('Blender', config['PRODUCT_NAME']))
    if config.get('REPLACE_BLENDER_FOUNDATION') == '1':
        tokens.append(('Blender Foundation', config['COMPANY']))
    if config.get('REPLACE_URLS') == '1':
        tokens.append(('blender.org', config.get('URL_REPLACEMENT', '')))
    if config.get('REPLACE_LOWER_BLENDER') == '1':
        tokens.append(('blender', config['PRODUCT_SLUG']))
    return tokens


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='write changes (default is dry-run)')
    parser.add_argument('--verbose', action='store_true', help='list skipped paths')
    args = parser.parse_args()

    config = load_config()
    patterns = load_allow_list()
    missing = [key for key in ('PRODUCT_NAME', 'PRODUCT_SLUG', 'APP_ID') if not config.get(key)]
    if missing:
        print('brand.conf is missing: ' + ', '.join(missing))
        return 2

    tokens = build_tokens(config)
    edits = identity_edits(config)

    report = []
    changed = []
    skip_counts = {}
    replacements = 0

    for path in tracked_files():
        reason = skip_reason(path, patterns)
        if reason is not None:
            skip_counts[reason] = skip_counts.get(reason, 0) + 1
            if args.verbose and reason == 'protected':
                print('protected, not modified: ' + path)
            continue
        if not is_text(path):
            skip_counts['non-text'] = skip_counts.get('non-text', 0) + 1
            continue
        try:
            text = read(path)
        except (UnicodeDecodeError, OSError):
            skip_counts['non-text'] = skip_counts.get('non-text', 0) + 1
            continue
        new_text = text
        hits = 0
        if path in IDENTITY_FILES:
            new_text, identity_hits = apply_identity(new_text, edits, report, path)
            hits += identity_hits
        new_text, word_hits = rewrite_lines(new_text, tokens)
        hits += word_hits
        if hits and new_text != text:
            replacements += hits
            changed.append((path, hits))
            if args.apply:
                write(path, new_text)

    print('brand target: ' + config['PRODUCT_NAME'] + '  (app id ' + config['APP_ID'] + ')')
    print('mode: ' + ('APPLY' if args.apply else 'dry-run'))
    print('files with replacements: %d, replacements: %d' % (len(changed), replacements))
    for path, hits in changed[:60]:
        print('  %5d  %s' % (hits, path))
    if len(changed) > 60:
        print('  ... and %d more files' % (len(changed) - 60))
    for line in report:
        print('  ' + line)
    print('skipped: ' + ', '.join('%s %d' % (k, v) for k, v in sorted(skip_counts.items())))

    print('')
    print('next steps:')
    print('  * artwork that cannot be scripted (splash.png, icons, .blend defaults)')
    print('    still needs manual replacement - see docs/REBRANDING.md section 3.2')
    print('  * build, then walk the verification checklist in docs/REBRANDING.md section 5')
    print('  * review the diff: git diff --name-only  (must stay inside branding-paths.txt,')
    print('    and never touch the no-touch paths listed at the top of that file)')
    if not args.apply:
        print('  * nothing was written (dry-run)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
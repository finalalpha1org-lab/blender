# tools/rebrand — branding automation

Runs the Final Effect 3D branding pass over a checkout of this fork. It exists so branding can be re-applied after **every** upstream sync instead of being hand-patched (see `docs/SYNC.md`).

## Usage

```
python3 tools/rebrand/apply_branding.py            # dry-run: report only
python3 tools/rebrand/apply_branding.py --apply    # write the changes
```

Then review and commit:

```
git diff --stat
git diff --name-only        # every path must be inside tools/rebrand/branding-paths.txt
git add -A && git commit -m 'brand: apply Final Effect 3D identity'
```

## What it does

| Pass | Behaviour |
|---|---|
| Text pass | Replaces the standalone word `Blender` with the product name inside allow-listed text files |
| Build identity | `project(Blender)`, `BLENDER_WIN_APPID`, `BLENDER_WIN_APPID_FRIENDLY_NAME` in the root `CMakeLists.txt` |
| Guards | Never touches no-touch paths (`blenloader/`, file-format constants, `COPYING`, `AUTHORS`, `doc/license/`, `release/license/`, `locale/` unless enabled) and never rewrites attribution lines (SPDX, copyright, licence wording) |
| Idempotent | A second run reports zero replacements, so the pass is safe to repeat |

## What it does **not** do

- **Artwork.** `release/datafiles/splash.png`, `icons*`, `startup.blend` and the installer bitmaps need new artwork; the script only tells you they exist.
- **Structural renames.** The `.desktop` entry, AppStream id and macOS bundle keep their Blender-derived names until you flip the switches in `brand.conf` and follow the references (the script prints them).
- **Localisation.** The 49 `.po` catalogs (about 82 MB) are only rewritten when `REPLACE_LOCALE = 1`; that is a deliberate, separate decision.
- **Trademark review.** It removes the wordmark from text; whether the result is free of trademark exposure is verified by the checklist in `docs/REBRANDING.md` section 5.

## Configuration (`brand.conf`)

All product identity lives in one file: `PRODUCT_NAME`, `PRODUCT_SLUG`, `COMPANY`, `APP_ID`, plus switches.

Defaults and the reasoning behind them:

- `REPLACE_WORD_BLENDER = 1` — the core of the rebrand.
- `REPLACE_URLS = 0` — upstream documentation links remain valid and useful.
- `REPLACE_LOWER_BLENDER = 0` — lowercase `blender` appears in paths, build targets, config directories and API names; changing it breaks add-ons, `.blend` files and user setups (docs/PLAN.md ADR-3). **Leave off.**
- `REPLACE_BLENDER_FOUNDATION = 0` — most mentions are attribution and must stay.
- `KEEP_USER_PATHS = 1` — Blender user config/cache paths stay unchanged in phase 1 (docs/PLAN.md ADR-5).

## Files

| File | Role |
|---|---|
| `brand.conf` | product identity and switches |
| `branding-paths.txt` | allow-list of paths the patch may touch (shared with CI) |
| `apply_branding.py` | the pass itself |
| `check_divergence.py` | CI check: divergence from upstream and drift outside the allow-list |
# Keeping this fork in sync with upstream Blender

This fork has two branches with different rules. Mixing them up is the main way this project becomes expensive to maintain.

| Branch | Purpose | Rule |
|---|---|---|
| `main` | pristine mirror of `blender/blender` main | never commit here; it must stay identical to upstream |
| `final-effect-3d` | upstream main + our branding and product commits | rebase onto upstream main, never merge |

## Routine

1. **Update the mirror.** GitHub UI: fork page -> *Sync fork* -> *Update branch*. Or locally:

```
git fetch upstream
git checkout main
git merge --ff-only upstream/main
git push origin main
```

2. **Rebase our branch:**

```
git fetch upstream
git checkout final-effect-3d
git rebase upstream/main
```

3. **Re-run the rebrand script** if a conflict or an upstream change touched branding files (see `docs/REBRANDING.md` in the Final-Effect-3D repository). Never hand-patch brand strings into upstream code - fix the script instead.

4. **Check that the patch is still confined to branding files:**

```
git diff --name-only upstream/main...HEAD
```

Every path printed must appear in `tools/rebrand/branding-paths.txt`. The same check runs in CI.

5. **Push** (rebasing rewrites this branch's history, which is expected):

```
git push --force-with-lease origin final-effect-3d
```

6. **Build and verify** using the checklist in `docs/REBRANDING.md` section 5 before any release.

## Why rebase instead of merge

Merging upstream into the branding branch interleaves our small patch with upstream history, so every later sync fights the previous merges and conflicts accumulate. A rebase keeps the branding work as a short, reviewable commit series sitting on top of current upstream - that is what makes a weekly sync a ten-minute job.

## Cadence

- **Weekly:** steps 1, 2, 4. The `fork-sync` workflow posts a divergence report as a reminder.
- **Before each release:** full sync, rebuild, complete verification checklist.
- **On upstream release candidates (alpha/beta/rc):** evaluate deliberately; adopt a new upstream minor version only when we choose to ship it.
- **Tags:** never push upstream tags into this fork. Tag our own releases on the branding branch, for example `v5.4.0-fe3d.1`.

## Expected conflicts

Conflicts should only happen in files listed in `tools/rebrand/branding-paths.txt`. Resolve them by taking upstream's version and re-running the rebrand script. If a conflict appears **outside** that list, stop and review: something in the branch is not branding and does not belong on it.

## Automation

`.github/workflows/fork-sync.yml` runs three checks:

- how far `main` differs from upstream (should always be zero),
- how far the branding branch is behind, and whether every changed path is on the branding allow-list (`tools/rebrand/check_divergence.py`),
- a rebase dry-run against upstream main (manual dispatch only, because it needs the full repository history).

The scheduled trigger only fires when the workflow exists on the repository **default branch**. Recommended: once branding work starts, set the fork's default branch to `final-effect-3d` so clones, pull requests and scheduled workflows all point at our product branch while `main` remains the pristine mirror.

## See also

- `../REBRANDING.md` and `../COMPLIANCE.md` are in this repository's `docs/` folder for the product planning documents.
- `tools/rebrand/branding-paths.txt` - the allow-list used by the CI check.
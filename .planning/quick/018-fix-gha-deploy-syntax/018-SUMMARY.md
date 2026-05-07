# Quick Task 018: Fix GitHub Actions Deploy Syntax — Summary

**Executed:** 2026-05-07
**Status:** Complete

## What Was Done
Resolved a critical failure in the GitHub Actions pipeline (`deploy-beta.yml`) caused by the use of the illegal `--source` option and a positional service name argument with `google-agents-cli deploy`.

1. **CLI Audit:** Verified via `google-agents-cli deploy --help` that the command does not support a `--source` option nor positional arguments for the service name, as it is a Click-based wrapper around `gcloud` that dispatches based on `pyproject.toml` configuration.
2. **Workflow Refactor:** Switched the deployment step in `.github/workflows/deploy-beta.yml` to use `gcloud run deploy` directly. This provides full support for:
   - Source-based builds (`--source .`).
   - Custom service names (`bot-tiendalasmotos-beta`), which the higher-level CLI would otherwise default to the project name `bot-tiendalasmotos`.
   - Explicit environment variable configuration via `--set-env-vars`.
3. **Trigger:** Committed and pushed the changes to the `beta` branch, re-triggering the pipeline.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| .github/workflows/deploy-beta.yml | Modified | Switched to direct gcloud run deploy syntax |

## Verification
| Check | Result |
|-------|--------|
| `google-agents-cli deploy --help` | ✅ Confirmed lack of `--source` option |
| `grep "gcloud run deploy" ...` | ✅ Verified correct command syntax |
| `git push origin beta` | ✅ Successfully pushed to remote |

---
*Completed: 2026-05-07*

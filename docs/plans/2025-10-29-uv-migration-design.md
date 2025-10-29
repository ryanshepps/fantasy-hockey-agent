# UV Package Manager Migration Design

**Date:** 2025-10-29
**Status:** Approved

## Overview

Migrate the fantasy-hockey-test project from pip to uv package manager to achieve faster dependency resolution, reproducible builds via lock files, and modern Python tooling.

## Goals

1. **Speed:** Faster dependency installation in CI/CD and local development
2. **Reproducibility:** Use uv.lock to ensure exact dependency versions across all environments
3. **Modern tooling:** Adopt uv as modern replacement for pip and virtualenv management
4. **Simplicity:** Keep configuration minimal while gaining these benefits

## Project Context

- **Project type:** Script-based application (not installable package)
- **Entry point:** `fantasy_hockey_agent.py`
- **Structure:** Organized modules (models/, modules/, tools/) with cross-module imports
- **Deployment:** GitHub Actions (scheduled daily job + manual trigger)
- **Python version:** 3.11

## Design Decisions

### 1. Dependency Configuration

**Approach:** Migrate everything to pyproject.toml, remove requirements.txt

**pyproject.toml structure:**
```toml
[project]
name = "fantasy-hockey-test"
requires-python = ">=3.11"
dependencies = [
    "yfpy>=17.0.0",
    "python-dotenv>=1.0.0",
    "anthropic>=0.39.0",
    "nhl-api-py>=1.0.0",
]

[dependency-groups]
dev = [
    "ruff>=0.8.0",
]

# Existing [tool.ruff] configuration remains unchanged
```

**Rationale:**
- Modern standard: pyproject.toml is the Python packaging standard (PEP 621)
- Single source of truth: All configuration in one file
- Lock file support: uv.lock ensures reproducible installs
- Dev dependencies: Separate ruff as development-only dependency

### 2. GitHub Actions Integration

**Approach:** Use official astral-sh/setup-uv@v4 action

**Workflow changes (both code-quality.yml and fantasy-hockey-analysis.yml):**

```yaml
steps:
  - name: Checkout repository
    uses: actions/checkout@v4

  - name: Install uv
    uses: astral-sh/setup-uv@v4

  - name: Set up Python
    uses: actions/setup-python@v5
    with:
      python-version: '3.11'

  - name: Install dependencies
    run: uv sync
```

**Key changes:**
- Add setup-uv action before Python setup
- Replace `pip install -r requirements.txt` with `uv sync`
- Remove pip cache configuration (uv has built-in caching)
- All other workflow steps remain unchanged

**Rationale:**
- Official support: Maintained by uv creators (Astral)
- Automatic caching: Built into the action
- Simple: Minimal configuration required
- Fast: Significantly faster than pip in CI

### 3. Lock File Management

**Strategy:**
- Commit `uv.lock` to git repository
- CI uses `uv sync` to install from lock file
- Local development uses same lock file

**Workflow for dependency changes:**

| Action | Command | Effect |
|--------|---------|--------|
| Add dependency | `uv add <package>` | Updates pyproject.toml and uv.lock |
| Remove dependency | `uv remove <package>` | Updates pyproject.toml and uv.lock |
| Update all deps | `uv lock --upgrade` | Refreshes uv.lock with latest versions |
| Install from lock | `uv sync` | Installs exact versions from uv.lock |
| Add dev dependency | `uv add --dev <package>` | Adds to dev dependency group |

**Rationale:**
- Reproducibility: Same versions in CI and local development
- Fast installs: Lock file eliminates resolution step
- Easy updates: Simple commands for common operations

## Migration Steps

1. **Update pyproject.toml**
   - Add [project] section with dependencies from requirements.txt
   - Add [dependency-groups] for dev dependencies
   - Keep existing [tool.ruff] configuration

2. **Generate lock file**
   - Run `uv lock` locally
   - Verify uv.lock is created

3. **Update GitHub Actions workflows**
   - Modify code-quality.yml
   - Modify fantasy-hockey-analysis.yml
   - Add setup-uv action, replace pip commands

4. **Clean up**
   - Remove requirements.txt
   - Commit all changes

5. **Verify**
   - Test code-quality workflow on PR
   - Test fantasy-hockey-analysis with manual trigger (dry_run=true)
   - Confirm faster dependency installation

## Files Modified

- `pyproject.toml` - Add dependencies, keep ruff config
- `.github/workflows/code-quality.yml` - Add uv setup, replace pip
- `.github/workflows/fantasy-hockey-analysis.yml` - Add uv setup, replace pip
- `requirements.txt` - Delete (replaced by pyproject.toml)
- `uv.lock` - New file (generated, committed to git)

## Expected Benefits

1. **Speed improvements:**
   - CI dependency installation: 10-20x faster than pip
   - Local development: Instant installs from cached lock file

2. **Reproducibility:**
   - Exact same dependency versions in all environments
   - No "works on my machine" issues

3. **Developer experience:**
   - Simple commands: `uv sync`, `uv add`, `uv remove`
   - No need to manage virtualenv separately
   - Lock file prevents dependency drift

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking CI workflows | Test with manual trigger before merging |
| Lock file merge conflicts | Standard practice: resolve by running `uv lock` |
| Team unfamiliar with uv | Commands similar to pip, documentation provided |
| uv not installed locally | Installation is simple: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

## Success Criteria

- ✅ Both GitHub Actions workflows run successfully with uv
- ✅ Dependencies install faster than with pip
- ✅ Lock file committed and used consistently
- ✅ No breaking changes to application behavior
- ✅ requirements.txt successfully removed

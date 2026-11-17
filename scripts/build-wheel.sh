#!/usr/bin/env bash
# build-wheel.sh — build a release wheel with the TypeScript engine bundled.
#
# Usage:
#   ./scripts/build-wheel.sh [--outdir DIR]
#
# Steps:
#   1. Build the TypeScript package (typescript/dist/) — dist/ must exist
#      at packaging time because poetry-core has no build hooks, so tsc
#      cannot run inside `poetry build` / `python -m build`. Wheels run no
#      code at install time either, so dist/ cannot be built on install.
#   2. Build the wheel with `python -m build --wheel` (installing the
#      `build` package with pip first if it is missing). Falls back to
#      `poetry build` only if `python -m build` cannot be made to work
#      and poetry is available.
#   3. Verify the wheel contains typescript/src/ and typescript/dist/,
#      then print the built wheel path.
#
# Requirements: Node + npm (or Bun) for the TS build, Python 3 with pip
# for the wheel build. The wheel bundles the TS *sources* and the
# prebuilt dist/; engine="ts" at runtime still needs Bun or Node on PATH
# (Poetry cannot install a JavaScript runtime).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUTDIR="$ROOT/dist"
while [ $# -gt 0 ]; do
    case "$1" in
        --outdir)
            OUTDIR="$2"; shift 2 ;;
        --outdir=*)
            OUTDIR="${1#--outdir=}"; shift ;;
        -h|--help)
            echo "Usage: $0 [--outdir DIR]"; exit 0 ;;
        *)
            echo "error: unknown argument: $1" >&2; exit 2 ;;
    esac
done

die() { echo "error: $*" >&2; exit 1; }

# --- 1. Build the TypeScript package -------------------------------------
if command -v npm >/dev/null 2>&1; then
    echo "Building TypeScript package (npm run build)..."
    (cd typescript && npm run build)
elif command -v bun >/dev/null 2>&1; then
    echo "Building TypeScript package (bun run build)..."
    (cd typescript && bun run build)
else
    die "neither npm nor bun found on PATH — install Node.js (https://nodejs.org) or Bun (https://bun.sh) to build the TypeScript engine"
fi
[ -f typescript/dist/cli.js ] || die "typescript/dist/cli.js missing after the TS build"

# --- 2. Build the wheel ---------------------------------------------------
# Pick a Python that can run `python -m build`: an explicit $PYBIN, the
# repo's .venv, or a throwaway venv created here (system Pythons are
# often PEP 668 externally-managed, so `pip install --user build` is not
# reliable; a venv never touches the system Python).
PYBIN="${PYBIN:-python3}"
pick_python() {
    if "$1" -m build --version >/dev/null 2>&1; then
        PYBIN="$1"; return 0
    fi
    return 1
}
if ! pick_python "$PYBIN"; then
    if [ -x "$ROOT/.venv/bin/python" ] && pick_python "$ROOT/.venv/bin/python"; then
        :
    else
        echo "No Python with the 'build' package found; creating a temporary build venv..."
        BUILD_TMP="$(mktemp -d)"
        trap 'rm -rf "$BUILD_TMP"' EXIT
        if "$PYBIN" -m venv "$BUILD_TMP/build-venv" >/dev/null 2>&1 \
            && "$BUILD_TMP/build-venv/bin/python" -m pip install -q build >/dev/null 2>&1 \
            && pick_python "$BUILD_TMP/build-venv/bin/python"; then
            :
        else
            die "could not get a Python with the 'build' package (tried $PYBIN, .venv, and a temporary venv) — install it with: $PYBIN -m pip install --break-system-packages build, or set PYBIN to a Python that already has it, or install poetry"
        fi
    fi
fi

build_with_python_build() {
    # Isolated build first (fetches poetry-core); if the isolated env
    # cannot be created (e.g. no venv module) and poetry-core is already
    # importable here, retry without isolation.
    if "$PYBIN" -m build --wheel --outdir "$OUTDIR" 2>/dev/null; then
        return 0
    fi
    if "$PYBIN" -c "import poetry.core" >/dev/null 2>&1; then
        echo "isolated build failed; retrying with --no-isolation..."
        "$PYBIN" -m build --wheel --no-isolation --outdir "$OUTDIR"
    else
        return 1
    fi
}

if ! "$PYBIN" -m build --version >/dev/null 2>&1; then
    if command -v poetry >/dev/null 2>&1; then
        echo "no 'python -m build' available; falling back to 'poetry build'..."
        poetry build --format wheel --output "$OUTDIR"
    else
        die "no Python with the 'build' package found (tried $PYBIN, .venv, and a temporary venv) and no 'poetry' fallback is installed — install it with: $PYBIN -m pip install --break-system-packages build, or set PYBIN to a Python that already has it, or install poetry"
    fi
elif ! build_with_python_build; then
    if command -v poetry >/dev/null 2>&1; then
        echo "python -m build failed; falling back to 'poetry build'..."
        poetry build --format wheel --output "$OUTDIR"
    else
        die "could not build the wheel with 'python -m build' and no 'poetry' fallback is installed"
    fi
fi

WHEEL="$(ls -t "$OUTDIR"/*.whl 2>/dev/null | head -n 1)"
[ -n "$WHEEL" ] || die "no wheel produced in $OUTDIR"

# --- 3. Verify the TS engine is bundled -----------------------------------
command -v unzip >/dev/null 2>&1 || die "unzip not found — cannot verify the wheel contents"
unzip -l "$WHEEL" | grep -q "typescript/src/cli.ts" \
    || die "wheel is missing typescript/src/cli.ts — the TS sources were not bundled"
unzip -l "$WHEEL" | grep -q "typescript/dist/cli.js" \
    || die "wheel is missing typescript/dist/cli.js — run the TS build first"
TS_FILES="$(unzip -l "$WHEEL" | grep -c typescript || true)"

echo "Built wheel: $WHEEL"
echo "Bundled TypeScript files in wheel: $TS_FILES"

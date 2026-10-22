#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

ANTLR_VERSION="4.13.1"
ANTLR_JAR="${ANTLR_JAR:-$HOME/.local/share/antlr/antlr-${ANTLR_VERSION}-complete.jar}"
EXPECTED_SHA512=""

echo "[1/5] checking python >= 3.9"
PYBIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYBIN" ]; then
    echo "error: python3 not found on PATH" >&2
    exit 1
fi

"$PYBIN" - <<'PYEOF'
import sys
if sys.version_info < (3, 9):
    sys.stderr.write("error: python >= 3.9 required (found %s)\n" % sys.version.split()[0])
    raise SystemExit(1)
PYEOF

echo "[2/5] installing pinned python dependencies"
"$PYBIN" -m pip install --requirement requirements.txt

echo "[3/5] checking java (needed once, for ANTLR codegen)"
if ! command -v java >/dev/null 2>&1; then
    echo "error: java not found. Install any JRE 11+, then re-run ./setup.sh" >&2
    exit 1
fi

echo "[4/5] fetching ANTLR ${ANTLR_VERSION} complete jar"
mkdir -p "$(dirname "$ANTLR_JAR")"
if [ ! -f "$ANTLR_JAR" ]; then
    if ! curl -fSL --retry 3 -o "$ANTLR_JAR" \
        "https://www.antlr.org/download/antlr-${ANTLR_VERSION}-complete.jar"; then
        echo "error: jar download failed (offline?). Place it manually at: $ANTLR_JAR" >&2
        exit 1
    fi
fi

echo "[5/5] generating python parser from grammar/GremlinC.g4"
mkdir -p src/gen
java -jar "$ANTLR_JAR" -Dlanguage=Python3 -visitor -o src/gen grammar/GremlinC.g4
touch src/gen/__init__.py

echo "done. next: cp .env.example .env && python3 validator.py"
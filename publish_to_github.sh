#!/usr/bin/env bash
# Publish this project to GitHub as akshith-types/gremlin.
# Run once, on your own computer, from the project folder:   bash publish_to_github.sh
# Creates a PRIVATE repo by default (the course manual prohibits sharing full source
# with other students). Pass --public to make it public instead.
set -euo pipefail
cd "$(dirname "$0")"

OWNER="akshith-types"
REPO="gremlin"
VISIBILITY="--private"
[ "${1:-}" = "--public" ] && VISIBILITY="--public"

if [ ! -d .git ]; then
    git init -b main
fi
git add -A
if ! git diff --cached --quiet; then
    git commit -m "GREMLIN: adversarial puzzle compiler (BCSE307P Review 3)" \
               -m "Strings and arrays, type checker, M1-M6 mutation rules, HTML report, 37 tests."
fi

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    # GitHub CLI is installed and logged in: create the repo and push in one go
    if gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
        git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$OWNER/$REPO.git"
        git push -u origin main
    else
        gh repo create "$OWNER/$REPO" $VISIBILITY --source=. --remote=origin --push \
            --description "Adversarial puzzle compiler: dataflow-driven unsound mutations of three-address code, proven by differential execution"
    fi
else
    echo
    echo "GitHub CLI not found or not logged in. Two options:"
    echo "  A) brew install gh && gh auth login     then run this script again"
    echo "  B) create an EMPTY repo named '$REPO' at https://github.com/new (no README), then run:"
    echo "       git remote add origin https://github.com/$OWNER/$REPO.git"
    echo "       git push -u origin main"
    exit 0
fi
echo "Done: https://github.com/$OWNER/$REPO"

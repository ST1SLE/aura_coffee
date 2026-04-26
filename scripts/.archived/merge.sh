#!/usr/bin/env bash
# Мержит worktree-ветки в порядке merge_order из phase-plan.yaml.
#
# Использование:
#   ./scripts/merge.sh plans/phase3.yaml
#   ./scripts/merge.sh plans/phase3.yaml --dry-run   # показать порядок без мержа
#
# Останавливается на первом конфликте. После ручного разрешения — запустить снова,
# скрипт пропустит уже смерженные ветки.

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"
cd "$REPO_ROOT"

PLAN_FILE="${1:-}"
DRY_RUN=false
if [[ "${2:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

if [[ -z "$PLAN_FILE" ]]; then
    echo "Usage: $0 <phase-plan.yaml> [--dry-run]" >&2
    exit 1
fi

if [[ ! -f "$PLAN_FILE" ]]; then
    echo "error: plan file not found: $PLAN_FILE" >&2
    exit 1
fi

# --- Зависимости ---

for cmd in jq; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "error: $cmd not found in PATH" >&2
        exit 1
    fi
done

# --- Парсинг YAML → JSON (в temp-файл) ---

PLAN_JSON_FILE=$(mktemp)
SORTED_FILE=$(mktemp)
trap 'rm -f "$PLAN_JSON_FILE" "$SORTED_FILE"' EXIT

python3 -c "
import sys, json
sys.path.insert(0, '/usr/lib/python3/dist-packages')
try:
    import yaml
except ImportError:
    print('error: PyYAML not found. Install: pip install pyyaml', file=sys.stderr)
    sys.exit(1)

with open(sys.argv[1]) as f:
    data = yaml.safe_load(f)

with open(sys.argv[2], 'w') as out:
    json.dump(data, out)
" "$PLAN_FILE" "$PLAN_JSON_FILE"

BASE_BRANCH=$(jq -r '.base_branch' "$PLAN_JSON_FILE")
PHASE=$(jq -r '.phase' "$PLAN_JSON_FILE")

# Сортировка фич по merge_order
jq -c '[.features | sort_by(.merge_order) | .[]]' "$PLAN_JSON_FILE" > "$SORTED_FILE"
FEATURE_COUNT=$(jq -r 'length' "$SORTED_FILE")

echo "=== Merge: Phase $PHASE ==="
echo "Base branch: $BASE_BRANCH"
echo "Features to merge: $FEATURE_COUNT"
echo ""

# --- Проверки (пропускаются для --dry-run) ---

if ! $DRY_RUN; then
    CURRENT_BRANCH=$(git branch --show-current)
    if [[ "$CURRENT_BRANCH" != "$BASE_BRANCH" ]]; then
        echo "error: not on base branch '$BASE_BRANCH' (currently on '$CURRENT_BRANCH')" >&2
        echo "  run: git checkout $BASE_BRANCH" >&2
        exit 1
    fi

    if [[ -n "$(git status --porcelain)" ]]; then
        echo "error: working directory is not clean" >&2
        echo "  commit or stash changes before merging" >&2
        exit 1
    fi
fi

# --- Мерж по порядку ---

WORKTREE_DIR="$REPO_ROOT/.worktrees"
MERGED=0
SKIPPED=0

for i in $(seq 0 $((FEATURE_COUNT - 1))); do
    NAME=$(jq -r ".[$i].name" "$SORTED_FILE")
    MERGE_ORDER=$(jq -r ".[$i].merge_order" "$SORTED_FILE")
    BRANCH_NAME="feat/$NAME"
    WORKTREE_PATH="$WORKTREE_DIR/$NAME"

    echo "--- [$MERGE_ORDER] $NAME (branch: $BRANCH_NAME) ---"

    # Проверяем, существует ли ветка
    if ! git rev-parse --verify "$BRANCH_NAME" &>/dev/null; then
        echo "  warning: branch $BRANCH_NAME does not exist, skipping"
        SKIPPED=$((SKIPPED + 1))
        echo ""
        continue
    fi

    # Проверяем, уже смержена ли ветка
    if git merge-base --is-ancestor "$BRANCH_NAME" HEAD 2>/dev/null; then
        echo "  already merged, skipping"
        SKIPPED=$((SKIPPED + 1))
        echo ""
        continue
    fi

    if $DRY_RUN; then
        COMMIT_COUNT=$(git rev-list --count "$BASE_BRANCH".."$BRANCH_NAME" 2>/dev/null || echo "?")
        echo "  [dry-run] would merge $BRANCH_NAME ($COMMIT_COUNT commits ahead)"
        echo ""
        continue
    fi

    # --- Мерж ---

    echo "  Merging..."
    if git merge --no-ff "$BRANCH_NAME" -m "Merge $BRANCH_NAME (phase $PHASE, order $MERGE_ORDER)"; then
        echo "  Merged successfully."
        MERGED=$((MERGED + 1))

        # --- Очистка worktree ---

        if [[ -d "$WORKTREE_PATH" ]]; then
            echo "  Removing worktree..."
            git worktree remove "$WORKTREE_PATH" --force 2>&1 | sed 's/^/  /'
        fi

        # --- Удаление ветки ---

        echo "  Deleting branch $BRANCH_NAME..."
        git branch -d "$BRANCH_NAME" 2>&1 | sed 's/^/  /'

        # --- Очистка файла промпта ---

        PROMPT_FILE="$WORKTREE_DIR/.prompt-$NAME.txt"
        if [[ -f "$PROMPT_FILE" ]]; then
            rm "$PROMPT_FILE"
        fi
    else
        echo ""
        echo "  CONFLICT detected while merging $BRANCH_NAME!"
        echo ""
        echo "  Resolve the conflict manually:"
        echo "    1. Fix conflicting files (see above)"
        echo "    2. git add <resolved files>"
        echo "    3. git commit"
        echo "    4. Re-run: $0 $PLAN_FILE"
        echo ""
        echo "  Remaining features after this one:"
        for j in $(seq $((i + 1)) $((FEATURE_COUNT - 1))); do
            REMAINING=$(jq -r ".[$j].name" "$SORTED_FILE")
            echo "    - $REMAINING"
        done
        exit 1
    fi

    echo ""
done

# --- Очистка пустой .worktrees ---

if [[ -d "$WORKTREE_DIR" ]] && [[ -z "$(ls -A "$WORKTREE_DIR" 2>/dev/null)" ]]; then
    rmdir "$WORKTREE_DIR"
    echo "Cleaned up empty .worktrees directory."
fi

echo "=== Merge complete ==="
echo "Merged: $MERGED"
echo "Skipped: $SKIPPED (already merged or missing)"
echo ""
if [[ $MERGED -gt 0 ]]; then
    echo "Next: test the result manually or run the test suite."
fi

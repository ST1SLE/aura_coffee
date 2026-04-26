#!/usr/bin/env bash
# Создаёт git worktrees и запускает Claude-сессии в gnome-terminal табах.
#
# Использование:
#   ./scripts/orchestrate.sh plans/phase3.yaml
#   ./scripts/orchestrate.sh plans/phase3.yaml --dry-run   # показать команды без запуска
#
# Требования: python3 (с PyYAML), jq, gnome-terminal, claude CLI

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

for cmd in jq gnome-terminal claude; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "error: $cmd not found in PATH" >&2
        exit 1
    fi
done

# --- Парсинг YAML → JSON (в temp-файл, чтобы обойти shell expansion) ---

PLAN_JSON_FILE=$(mktemp)
trap 'rm -f "$PLAN_JSON_FILE"' EXIT

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

# Все jq-вызовы работают с файлом напрямую — нет проблем с echo/printf
BASE_BRANCH=$(jq -r '.base_branch' "$PLAN_JSON_FILE")
PHASE=$(jq -r '.phase' "$PLAN_JSON_FILE")
DESCRIPTION=$(jq -r '.description // ""' "$PLAN_JSON_FILE")
FEATURE_COUNT=$(jq -r '.features | length' "$PLAN_JSON_FILE")

# Массив групп через readarray
readarray -t GROUPS_ARR < <(jq -r '[.features[].parallel_group] | unique | sort | .[]' "$PLAN_JSON_FILE")

echo "=== Orchestrate: Phase $PHASE ==="
echo "Description: $DESCRIPTION"
echo "Base branch: $BASE_BRANCH"
echo "Features: $FEATURE_COUNT"
echo "Parallel groups: ${#GROUPS_ARR[@]}"
echo ""

# --- Проверка: base_branch существует ---

if ! git rev-parse --verify "$BASE_BRANCH" &>/dev/null; then
    echo "error: base branch '$BASE_BRANCH' does not exist" >&2
    exit 1
fi

# --- Инструкции для агента по типу фичи ---

backend_workflow() {
    local name="$1"
    cat <<INST
## Workflow (TDD — два цикла)

Выполни ОБА цикла последовательно в этом worktree:

### Цикл 1: RED (failing tests)
1. Запусти: /opsx:propose ${name}-red
2. Запусти: /opsx:apply ${name}-red
3. Запусти: /opsx:archive ${name}-red

### Цикл 2: GREEN (implementation)
1. Запусти: /opsx:propose ${name}-green
2. Запусти: /opsx:apply ${name}-green
3. Запусти: /opsx:archive ${name}-green

После завершения обоих циклов — закоммить все изменения и скажи DONE.
INST
}

frontend_workflow() {
    local name="$1"
    cat <<INST
## Workflow (один цикл)

1. Запусти: /opsx:propose ${name}
2. Запусти: /opsx:apply ${name}
3. Запусти: /opsx:archive ${name}

После завершения — закоммить все изменения и скажи DONE.
INST
}

# --- Основной цикл по группам ---

WORKTREE_DIR="$REPO_ROOT/.worktrees"
mkdir -p "$WORKTREE_DIR"

for group in "${GROUPS_ARR[@]}"; do
    # Сохраняем фичи группы в temp-файл
    GROUP_FILE=$(mktemp)
    jq -c "[.features[] | select(.parallel_group == $group)]" "$PLAN_JSON_FILE" > "$GROUP_FILE"
    GROUP_SIZE=$(jq -r 'length' "$GROUP_FILE")

    echo "--- Group $group ($GROUP_SIZE features) ---"

    # Собираем launcher-пути для запуска табов
    LAUNCHERS=()
    TAB_NAMES=()

    for i in $(seq 0 $((GROUP_SIZE - 1))); do
        NAME=$(jq -r ".[$i].name" "$GROUP_FILE")
        TYPE=$(jq -r ".[$i].type" "$GROUP_FILE")
        PROMPT=$(jq -r ".[$i].prompt" "$GROUP_FILE")
        FILE_ZONES=$(jq -r ".[$i].file_zones[]" "$GROUP_FILE" 2>/dev/null | tr '\n' ', ' | sed 's/,$//')

        WORKTREE_PATH="$WORKTREE_DIR/$NAME"
        BRANCH_NAME="feat/$NAME"

        echo "  [$NAME] type=$TYPE worktree=$WORKTREE_PATH branch=$BRANCH_NAME"

        # --- Создание worktree ---

        if [[ -d "$WORKTREE_PATH" ]]; then
            echo "  [$NAME] worktree already exists, reusing"
        else
            if $DRY_RUN; then
                echo "  [dry-run] git worktree add $WORKTREE_PATH -b $BRANCH_NAME $BASE_BRANCH"
            else
                git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME" "$BASE_BRANCH" 2>&1 | sed 's/^/  /'
            fi
        fi

        # --- setup-worktree-env.sh ---

        if $DRY_RUN; then
            echo "  [dry-run] cd $WORKTREE_PATH && ./scripts/setup-worktree-env.sh"
        else
            if [[ -f "$WORKTREE_PATH/scripts/setup-worktree-env.sh" ]]; then
                (cd "$WORKTREE_PATH" && bash ./scripts/setup-worktree-env.sh) 2>&1 | sed 's/^/  /'
            else
                echo "  [$NAME] warning: setup-worktree-env.sh not found, skipping port setup"
            fi
        fi

        # --- Промпт для агента ---

        if [[ "$TYPE" == "backend" ]]; then
            WORKFLOW_INSTRUCTIONS=$(backend_workflow "$NAME")
        else
            WORKFLOW_INSTRUCTIONS=$(frontend_workflow "$NAME")
        fi

        AGENT_PROMPT="Start implementing feature: $NAME

## Task
$PROMPT

## Context
- Worktree: $WORKTREE_PATH
- Branch: $BRANCH_NAME
- Base branch: $BASE_BRANCH
- File zones: $FILE_ZONES
- Feature type: $TYPE

$WORKFLOW_INSTRUCTIONS

## Rules
- Follow PDD and AGENTS.md constraints
- Commit after each archive (no push)
- If you hit ambiguity or a design question — ASK, do not guess
- When fully done with all cycles, say DONE"

        # --- Генерация launcher-скрипта (обходит проблемы с вложенным экранированием) ---

        PROMPT_FILE="$WORKTREE_DIR/.prompt-$NAME.txt"
        LAUNCHER="$WORKTREE_DIR/.launch-$NAME.sh"

        if ! $DRY_RUN; then
            printf '%s\n' "$AGENT_PROMPT" > "$PROMPT_FILE"

            # --allowedTools принимает variadic аргументы, поэтому используем
            # запятую как разделитель — иначе $PROMPT съедается как имя инструмента
            cat > "$LAUNCHER" <<LAUNCHER_EOF
#!/usr/bin/env bash
cd '$WORKTREE_PATH'
PROMPT=\$(cat '$PROMPT_FILE')
claude \\
    --name '$NAME' \\
    --allowedTools 'Bash(openspec *),Bash(git add:*),Bash(git commit *),Bash(git status*),Bash(git diff*),Bash(git log*),Bash(git show*),Bash(docker compose *),Bash(pytest *),Bash(python3 *),Bash(python3.12 *),Bash(python *),Bash(npm run *),Bash(npm test *),Bash(npx vitest *),Bash(npx tsc *),Bash(npx eslint *),Bash(npx openspec *),Bash(ruff *),Bash(pip install *),Bash(pip3 install *),Bash(uv pip *),Bash(uv run *),Bash(curl *),Bash(./scripts/setup-worktree-env.sh),Bash(./scripts/up.sh*),Bash(chmod *),Bash(ls *),Bash(mkdir *),Bash(wc *),Bash(grep *),Read,Edit,Write,Glob,Grep,Skill,Agent' \\
    -- "\$PROMPT"
echo ''
echo '--- Session ended. Press Enter to close ---'
read
LAUNCHER_EOF
            chmod +x "$LAUNCHER"
        fi

        if $DRY_RUN; then
            echo "  [dry-run] gnome-terminal tab: $NAME"
            echo "  [dry-run] launcher: $LAUNCHER"
            echo ""
        else
            LAUNCHERS+=("$LAUNCHER")
            TAB_NAMES+=("$NAME")
        fi
    done

    rm -f "$GROUP_FILE"

    # --- Запуск gnome-terminal: один вызов на таб ---
    # gnome-terminal трактует "--" как конец ВСЕХ опций (POSIX),
    # поэтому несколько --tab ... -- cmd в одном вызове не работают.
    # Решение: первый вызов создаёт окно, остальные добавляют табы.

    if ! $DRY_RUN && [[ ${#LAUNCHERS[@]} -gt 0 ]]; then
        echo ""
        echo "  Launching gnome-terminal with ${#LAUNCHERS[@]} tabs..."

        # Функция для запуска gnome-terminal без snap-переменных
        launch_terminal() {
            (
                unset GTK_PATH GTK_EXE_PREFIX GTK_IM_MODULE_FILE
                unset GIO_MODULE_DIR GDK_BACKEND GDK_PIXBUF_MODULE_FILE
                unset LOCPATH GSETTINGS_SCHEMA_DIR XDG_DATA_HOME
                export XDG_DATA_DIRS="${XDG_DATA_DIRS_VSCODE_SNAP_ORIG:-/usr/share/ubuntu:/usr/share/gnome:/usr/local/share/:/usr/share/:/var/lib/snapd/desktop}"
                export XDG_CONFIG_DIRS="${XDG_CONFIG_DIRS_VSCODE_SNAP_ORIG:-/etc/xdg/xdg-ubuntu:/etc/xdg}"
                gnome-terminal "$@" &
                disown
            )
        }

        # Первый таб — создаёт новое окно (без --tab, иначе появится лишний пустой таб)
        launch_terminal --window --title "${TAB_NAMES[0]}" -- bash "${LAUNCHERS[0]}"

        # Остальные табы — добавляются в последнее активное окно
        for idx in $(seq 1 $((${#LAUNCHERS[@]} - 1))); do
            sleep 0.3
            launch_terminal --tab --title "${TAB_NAMES[$idx]}" -- bash "${LAUNCHERS[$idx]}"
        done

        echo "  Launched. Sessions will ask you if they need decisions."
    fi

    echo ""
done

echo "=== All groups launched ==="
echo ""
echo "Next steps:"
echo "  1. Work in each Claude session (they'll ask if stuck)"
echo "  2. When all sessions say DONE, run:"
echo "     ./scripts/merge.sh $PLAN_FILE"

#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
REQUIREMENTS_FILE="$ROOT_DIR/infra/production/host-requirements.env"
MODE="${1:---deploy}"

if [[ ! -r "$REQUIREMENTS_FILE" ]]; then
    echo "Missing production host requirements: $REQUIREMENTS_FILE" >&2
    exit 2
fi

# shellcheck disable=SC1090
source "$REQUIREMENTS_FILE"

version_ge() {
    # Compare dotted numeric versions without relying on sort -V (not universal
    # on older CentOS installations).
    local have="$1"
    local need="$2"
    local IFS=.
    local -a have_parts=($have)
    local -a need_parts=($need)
    local length="${#have_parts[@]}"
    local i h n
    if [[ "${#need_parts[@]}" -gt "$length" ]]; then
        length="${#need_parts[@]}"
    fi
    for ((i = 0; i < length; i++)); do
        h="${have_parts[i]:-0}"
        n="${need_parts[i]:-0}"
        h="${h//[^0-9]/}"
        n="${n//[^0-9]/}"
        h="${h:-0}"
        n="${n:-0}"
        if ((10#$h > 10#$n)); then return 0; fi
        if ((10#$h < 10#$n)); then return 1; fi
    done
    return 0
}

failures=0
warnings=0

ok() { printf 'OK   %s\n' "$*"; }
warn() { printf 'WARN %s\n' "$*"; warnings=$((warnings + 1)); }
fail_check() { printf 'FAIL %s\n' "$*"; failures=$((failures + 1)); }

check_command() {
    local command_name="$1"
    if command -v "$command_name" >/dev/null 2>&1; then
        ok "$command_name -> $(command -v "$command_name")"
    else
        fail_check "missing command: $command_name"
    fi
}

printf '===== PLANETS INTEL HOST PREREQUISITES =====\n'
printf 'mode=%s\n' "$MODE"
printf 'requirements=%s\n' "$REQUIREMENTS_FILE"

printf '\n===== REQUIRED COMMANDS =====\n'
for command_name in $HOST_REQUIRED_DEPLOY_COMMANDS; do
    check_command "$command_name"
done

printf '\n===== VERSIONS =====\n'
bash_version="${BASH_VERSION%%(*}"
if version_ge "$bash_version" "$HOST_BASH_MIN"; then
    ok "bash $bash_version >= $HOST_BASH_MIN"
else
    fail_check "bash $bash_version < required $HOST_BASH_MIN"
fi

if command -v git >/dev/null 2>&1; then
    git_version="$(git --version | awk '{print $3}')"
    if version_ge "$git_version" "$HOST_GIT_MIN"; then
        ok "git $git_version >= $HOST_GIT_MIN"
    else
        fail_check "git $git_version < required $HOST_GIT_MIN"
    fi
fi

if command -v docker >/dev/null 2>&1; then
    docker_version="$(docker version --format '{{.Server.Version}}' 2>/dev/null || true)"
    if [[ -z "$docker_version" ]]; then
        fail_check "Docker daemon is unavailable"
    elif version_ge "$docker_version" "$HOST_DOCKER_MIN"; then
        ok "docker server $docker_version >= $HOST_DOCKER_MIN"
    else
        fail_check "docker server $docker_version < required $HOST_DOCKER_MIN"
    fi

    compose_version="$(docker compose version --short 2>/dev/null || true)"
    if [[ -z "$compose_version" ]]; then
        fail_check "docker compose v2 plugin is unavailable"
    elif [[ "${compose_version%%.*}" == "$HOST_DOCKER_COMPOSE_MAJOR" ]]; then
        ok "docker compose $compose_version (major $HOST_DOCKER_COMPOSE_MAJOR)"
    else
        fail_check "docker compose $compose_version; required major $HOST_DOCKER_COMPOSE_MAJOR"
    fi
fi

printf '\n===== HOST PYTHON BASELINE =====\n'
if command -v python3 >/dev/null 2>&1; then
    python_version="$(python3 -c 'import sys; print("{}.{}.{}".format(*sys.version_info[:3]))' 2>/dev/null || true)"
    if [[ -n "$python_version" ]] && version_ge "$python_version" "$HOST_SYSTEM_PYTHON_MIN"; then
        ok "system python3 $python_version >= maintenance baseline $HOST_SYSTEM_PYTHON_MIN"
    else
        warn "system python3 ${python_version:-unknown} is below maintenance baseline $HOST_SYSTEM_PYTHON_MIN"
    fi
else
    warn "system python3 is absent; normal deploy does not require it, some maintenance helpers do"
fi
printf 'INFO host Node.js is not required; frontend build image: %s\n' "$FRONTEND_BUILD_IMAGE"
printf 'INFO host Python 3.11 is not required; backend runtime image: %s\n' "$BACKEND_RUNTIME_IMAGE"
printf 'INFO database image: %s\n' "$DATABASE_IMAGE"

if [[ "$MODE" == "--network" || "$MODE" == "--all" ]]; then
    printf '\n===== NETWORK MAINTENANCE COMMANDS =====\n'
    for command_name in $HOST_REQUIRED_NETWORK_COMMANDS; do
        check_command "$command_name"
    done
    for command_name in $HOST_OPTIONAL_NETWORK_DIAGNOSTICS; do
        if command -v "$command_name" >/dev/null 2>&1; then
            ok "optional diagnostic $command_name available"
        else
            warn "optional diagnostic $command_name missing (CentOS package: bind-utils)"
        fi
    done
fi

if [[ "$MODE" == "--deploy" || "$MODE" == "--all" ]]; then
    printf '\n===== BUILD NETWORK =====\n'
    if grep -Eq "^[[:space:]]*nameserver[[:space:]]+$PRODUCTION_KNOWN_BAD_DNS([[:space:]]|$)" /etc/resolv.conf 2>/dev/null; then
        fail_check "resolver still uses known-unreachable production DNS $PRODUCTION_KNOWN_BAD_DNS; run scripts/maintenance/fix-networkmanager-dns.sh"
    else
        ok "resolver does not use known-bad DNS $PRODUCTION_KNOWN_BAD_DNS"
    fi

    if getent ahostsv4 "$DOCKER_REGISTRY_HOST" >/dev/null 2>&1; then
        ok "DNS resolves $DOCKER_REGISTRY_HOST"
    else
        fail_check "DNS cannot resolve $DOCKER_REGISTRY_HOST"
    fi

    set +e
    registry_result="$(curl -sS -o /dev/null -w 'http=%{http_code} remote_ip=%{remote_ip} total=%{time_total}s' --connect-timeout 8 --max-time 15 "$DOCKER_REGISTRY_URL" 2>&1)"
    registry_rc=$?
    set -e
    if [[ "$registry_rc" -eq 0 ]]; then
        ok "Docker Registry reachable: $registry_result (HTTP 401 is expected without auth)"
    else
        fail_check "Docker Registry unreachable: curl_exit=$registry_rc $registry_result"
    fi
fi

printf '\n===== RESULT =====\n'
printf 'failures=%d warnings=%d\n' "$failures" "$warnings"
if [[ "$failures" -ne 0 ]]; then
    echo "Host prerequisite check FAILED." >&2
    exit 1
fi

echo "Host prerequisite check OK."

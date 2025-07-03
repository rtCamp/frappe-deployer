#!/usr/bin/env bash
# Helper functions for frappe-deployer GitHub Action
# Based on your original helpers.sh

set -o errexit
set -o errtrace  
set -o nounset
set -o pipefail

# Define environment variables
LOG_LEVEL="${LOG_LEVEL:-6}"
NO_COLOR="${NO_COLOR:-}"

RED="\033[31m"
GREEN="\033[32m"
CYAN="\033[36m"
YELLOW='\033[0;33m'
BLUE="\033[34m"
ENDCOLOR="\033[0m"

### Logging Functions
function __log () {
  local log_level="${1}"
  shift

  local color_debug="\\x1b[35m"
  local color_info="\\x1b[32m"
  local color_notice="\\x1b[34m"
  local color_warning="\\x1b[33m"
  local color_error="\\x1b[31m"
  local color_critical="\\x1b[1;31m"
  local color_alert="\\x1b[1;37;41m"
  local color_emergency="\\x1b[1;4;5;37;41m"

  local colorvar="color_${log_level}"
  local color="${!colorvar:-${color_error}}"
  local color_reset="\\x1b[0m"

  if [[ "${NO_COLOR:-}" = "true" ]] || { [[ "${TERM:-}" != "xterm"* ]] && [[ "${TERM:-}" != "screen"* ]]; } || [[ ! -t 2 ]]; then
    if [[ "${NO_COLOR:-}" != "false" ]]; then
      color=""; color_reset=""
    fi
  fi

  local log_line=""
  while IFS=$'\n' read -r log_line; do
    width=9
    padding=$(( ($width - ${#log_level}) / 2 ))
    echo -e "$(date -u +"%Y-%m-%d %H:%M:%S UTC") ${color}$(printf "[%${padding}s%s%${padding}s]" "" "${log_level}" "" )${color_reset} ${log_line}" 1>&2
  done <<< "${@:-}"
}

function emergency () { __log emergency "${@}"; exit 1; }
function alert ()     { [[ "${LOG_LEVEL:-0}" -ge 1 ]] && __log alert "${@}"; true; }
function critical ()  { [[ "${LOG_LEVEL:-0}" -ge 2 ]] && __log critical "${@}"; true; }
function error ()     { [[ "${LOG_LEVEL:-0}" -ge 3 ]] && __log error "${@}"; true; }
function warn ()      { [[ "${LOG_LEVEL:-0}" -ge 4 ]] && __log warning "${@}"; true; }
function notice ()    { [[ "${LOG_LEVEL:-0}" -ge 5 ]] && __log notice "${@}"; true; }
function info ()      { [[ "${LOG_LEVEL:-0}" -ge 6 ]] && __log info "${@}"; true; }
function debug ()     { [[ "${LOG_LEVEL:-0}" -ge 7 ]] && __log debug "${@}"; true; }

function check_command_status () {
    if [ "$?" -gt "$1" ]; then
        emergency "$2"
    else
        info "$3"
    fi
}

# Remote execution function
remote_execute() {
    [[ "${REMOTE_USER}" ]] || emergency "REMOTE_USER not found."
    [[ "${REMOTE_HOST}" ]] || emergency "REMOTE_HOST not found."

    local path=$(echo "$1")
    local cmd=$(echo "$2")

    info "Executing on remote: cd $path && $cmd"
    ssh -o StrictHostKeyChecking=no "${REMOTE_USER}"@"${REMOTE_HOST}" "cd $path && $cmd"
}

# SSH setup function
setup_ssh() {
    SSH_DIR="$HOME/.ssh"
    mkdir -p "$SSH_DIR"
    chmod 700 "$SSH_DIR"

    [[ "${SSH_PRIVATE_KEY:-}" ]] || emergency "SSH_PRIVATE_KEY is not set."

    if [[ -n "$SSH_PRIVATE_KEY" ]]; then
        echo "$SSH_PRIVATE_KEY" | tr -d '\r' > "$SSH_DIR/id_rsa"
        chmod 600 "$SSH_DIR/id_rsa"
        eval "$(ssh-agent -s)"
        ssh-add "$SSH_DIR/id_rsa"

        # Add server to known hosts
        ssh-keyscan -H "$REMOTE_HOST" >> "$SSH_DIR/known_hosts" 2>/dev/null || true

        cat > "$SSH_DIR/config" <<EOL
Host $REMOTE_HOST
    HostName $REMOTE_HOST
    IdentityFile ${SSH_DIR}/id_rsa
    User $REMOTE_USER
    StrictHostKeyChecking no
EOL
    fi
}

# User authorization check
check_user_authorization() {
    if [ -n "${ALLOWED_USERS:-}" ]; then
        local actor=$(echo "$GITHUB_ACTOR" | tr '[:upper:]' '[:lower:]')
        local allowed_users=$(echo "$ALLOWED_USERS" | tr '[:upper:]' '[:lower:]')
        
        if [[ ! ",$allowed_users," == *",$actor,"* ]]; then
            emergency "User ${GITHUB_ACTOR} is not allowed to run this deployment."
        fi
        info "User ${GITHUB_ACTOR} authorized to run deployment (restricted mode)"
    else
        info "User ${GITHUB_ACTOR} authorized to run deployment (unrestricted mode)"
    fi
}

# Configuration file validation
validate_config_file() {
    local config_file="$1"
    
    if [ ! -f "$config_file" ]; then
        emergency "Configuration file not found: $config_file"
    fi
    
    info "Using configuration: $config_file"
}

# Binary validation function
validate_binary() {
    local binary_path="$1"
    
    if [ ! -f "$binary_path" ]; then
        emergency "Binary not found: $binary_path"
    fi
    
    if [ ! -x "$binary_path" ]; then
        emergency "Binary is not executable: $binary_path"
    fi
    
    info "Binary validated: $binary_path"
}

# Test binary on remote server
test_remote_binary() {
    local remote_binary_path="$1"
    
    info "Testing binary on remote server"
    ssh -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
        "${remote_binary_path} --version" || emergency "Binary test failed on remote server"
    
    info "Binary test passed on remote server"
}

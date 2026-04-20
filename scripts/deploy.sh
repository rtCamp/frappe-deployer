#!/bin/bash
__dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

if [[ "${DEBUG:-}" == "true" ]]; then
	set -x
fi

source "$__dir/helpers.sh"

toml_get() {
	local toml_file="$1"
	local key_path="$2"
	[[ -f "${toml_file}" ]] || return 1
	python3 -c "import sys,tomllib; d=tomllib.load(open(sys.argv[1],'rb')); print(d.get('ship',{}).get(sys.argv[2],''))" "${toml_file}" "${key_path}" 2>/dev/null || echo ""
}

build_switch_flags() {
	local cmd=""
	
	if [ "${INPUT_DRAIN_WORKERS:-false}" == "true" ]; then
		cmd="${cmd} --drain-workers"
	else
		cmd="${cmd} --no-drain-workers"
	fi

	if [ -n "${INPUT_DRAIN_WORKERS_TIMEOUT:-}" ]; then
		cmd="${cmd} --drain-workers-timeout ${INPUT_DRAIN_WORKERS_TIMEOUT}"
	fi

	if [ -n "${INPUT_DRAIN_WORKERS_POLL:-}" ]; then
		cmd="${cmd} --drain-workers-poll ${INPUT_DRAIN_WORKERS_POLL}"
	fi

	if [ "${INPUT_SKIP_STALE_WORKERS:-true}" == "true" ]; then
		cmd="${cmd} --skip-stale-workers"
	else
		cmd="${cmd} --no-skip-stale-workers"
	fi

	if [ -n "${INPUT_SKIP_STALE_TIMEOUT:-}" ]; then
		cmd="${cmd} --skip-stale-timeout ${INPUT_SKIP_STALE_TIMEOUT}"
	fi

	if [ "${INPUT_MIGRATE:-true}" == "true" ]; then
		cmd="${cmd} --migrate"
	else
		cmd="${cmd} --no-migrate"
	fi

	if [ -n "${INPUT_MIGRATE_TIMEOUT:-}" ]; then
		cmd="${cmd} --migrate-timeout ${INPUT_MIGRATE_TIMEOUT}"
	fi

	if [ -n "${INPUT_MIGRATE_COMMAND:-}" ]; then
		cmd="${cmd} --migrate-command ${INPUT_MIGRATE_COMMAND@Q}"
	fi

	if [ -n "${INPUT_MAINTENANCE_MODE_PHASES:-}" ]; then
		for phase in ${INPUT_MAINTENANCE_MODE_PHASES}; do
			cmd="${cmd} --maintenance-mode-phases ${phase}"
		done
	fi

	if [ -n "${INPUT_WORKER_KILL_TIMEOUT:-}" ]; then
		cmd="${cmd} --worker-kill-timeout ${INPUT_WORKER_KILL_TIMEOUT}"
	fi

	if [ -n "${INPUT_WORKER_KILL_POLL:-}" ]; then
		cmd="${cmd} --worker-kill-poll ${INPUT_WORKER_KILL_POLL}"
	fi

	if [ -n "${INPUT_ADDITIONAL_COMMANDS:-}" ]; then
		cmd="${cmd} ${INPUT_ADDITIONAL_COMMANDS}"
	fi

	echo "${cmd}"
}

parse_app_env() {
	while IFS= read -r line; do
		[[ -z "${line// /}" ]] && continue
		[[ "${line}" == \#* ]] && continue
		kv="${line#*:}"
		if [[ "${kv}" == *"="* ]]; then
			echo "${kv}"
		else
			warn "app_env: skipping malformed line (expected 'KEY=VALUE' or 'app-name:KEY=VALUE'): ${line}"
		fi
	done <<<"${INPUT_APP_ENV:-}"
}

pull_command() {
	REMOTE_PORT="${SSH_PORT:-22}"

	[[ "${SSH_PRIVATE_KEY:-}" ]] || emergency "ENV: ${CYAN} SSH_PRIVATE_KEY ${ENDCOLOR} is missing for 'pull' command."
	[[ "${FMD_GITHUB_TOKEN:-}" ]] || emergency "ENV: ${CYAN} FMD_GITHUB_TOKEN ${ENDCOLOR} is missing."
	[[ "${INPUT_SITENAME:-}" ]] || emergency "Input: ${CYAN} sitename ${ENDCOLOR} is missing."

	TEMP_SSH_DIR=$(mktemp -d /tmp/ssh_dir.XXXXXX)
	export HOME="${TEMP_SSH_DIR}"
	trap 'rm -rf "${TEMP_SSH_DIR}"' EXIT

	TOML_CONFIG_FILE=""
	if [[ -n "${FMD_CONFIG_PATH:-}" ]]; then
		TOML_CONFIG_FILE="${GITHUB_WORKSPACE}/${FMD_CONFIG_PATH}"
	elif [[ -n "${FMD_CONFIG_CONTENT:-}" ]]; then
		TOML_CONFIG_FILE=$(mktemp /tmp/fmd_config_content.XXXXXX.toml)
		echo "${FMD_CONFIG_CONTENT}" >"${TOML_CONFIG_FILE}"
	fi

	if [[ -z "${SSH_SERVER:-}" ]] && [[ -n "${TOML_CONFIG_FILE}" ]]; then
		SSH_SERVER=$(toml_get "${TOML_CONFIG_FILE}" "host")
	fi
	[[ -n "${SSH_SERVER}" ]] || emergency "Either set ${CYAN}ssh_server${ENDCOLOR} input or define ${CYAN}[ship].host${ENDCOLOR} in TOML config."

	if [[ -z "${SSH_USER:-}" ]] && [[ -n "${TOML_CONFIG_FILE}" ]]; then
		SSH_USER=$(toml_get "${TOML_CONFIG_FILE}" "ssh_user")
		SSH_USER="${SSH_USER:-frappe}"
	fi
	[[ -n "${SSH_USER}" ]] || emergency "Either set ${CYAN}ssh_user${ENDCOLOR} input or define ${CYAN}[ship].ssh_user${ENDCOLOR} in TOML config."

	REMOTE_HOST="${SSH_SERVER}"
	REMOTE_USER="${SSH_USER}"

	COMMAND="pull ${INPUT_SITENAME} --github-token ${FMD_GITHUB_TOKEN}"
	COMMAND="${COMMAND} --configure"
	COMMAND="${COMMAND}$(build_switch_flags)"

	setup_ssh

	current_datetime=$(date +"%Y-%m-%d_%H-%M-%S")

	REMOTE_APP_ENV_FILE=""
	if [[ -n "${INPUT_APP_ENV:-}" ]]; then
		REMOTE_APP_ENV_FILE="/tmp/.fmd_app_env_${current_datetime}"
		LOCAL_APP_ENV_TMP=$(mktemp)

		parse_app_env >"${LOCAL_APP_ENV_TMP}"

		rsync -az -e "ssh -p ${REMOTE_PORT} -o StrictHostKeyChecking=no" \
			"${LOCAL_APP_ENV_TMP}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_APP_ENV_FILE}"
		ssh -p "${REMOTE_PORT}" -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" "chmod 600 ${REMOTE_APP_ENV_FILE}"
		rm -f "${LOCAL_APP_ENV_TMP}"
	fi

	REMOTE_FMD_SRC="/tmp/fmd_src_${current_datetime}"
	rsync -az --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
		-e "ssh -p ${REMOTE_PORT} -o StrictHostKeyChecking=no" \
		"${GITHUB_ACTION_PATH}/" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_FMD_SRC}/"

	ssh -p "${REMOTE_PORT}" -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
		"cd /home/${REMOTE_USER} && test -x /home/${REMOTE_USER}/.local/bin/uv || curl -LsSf https://astral.sh/uv/install.sh | sh"

	ssh -p "${REMOTE_PORT}" -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
		"cd /home/${REMOTE_USER} && mkdir -p /home/${REMOTE_USER}/.fmd/logs && rm -rf /home/${REMOTE_USER}/.fmd/venv && /home/${REMOTE_USER}/.local/bin/uv venv /home/${REMOTE_USER}/.fmd/venv --python 3.10 && /home/${REMOTE_USER}/.local/bin/uv pip install --python /home/${REMOTE_USER}/.fmd/venv/bin/python ${REMOTE_FMD_SRC}"

	COMMAND_LINE="${COMMAND}"

	if [[ "${FMD_CONFIG_PATH:-}" ]]; then
		LOCAL_CONFIG_PATH="${GITHUB_WORKSPACE}/${FMD_CONFIG_PATH}"
		REMOTE_CONFIG_PATH="/tmp/$(basename "${FMD_CONFIG_PATH}")_${current_datetime}"
		rsync -az -e "ssh -p ${REMOTE_PORT} -o StrictHostKeyChecking=no" \
			"${LOCAL_CONFIG_PATH}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_CONFIG_PATH}"
		COMMAND_LINE="${COMMAND_LINE} --config-path ${REMOTE_CONFIG_PATH}"
	fi

	if [[ "${FMD_CONFIG_CONTENT:-}" ]]; then
		LOCAL_CONFIG_CONTENT_TMP=$(mktemp)
		REMOTE_CONFIG_CONTENT_PATH="/tmp/fmd_config_content_${current_datetime}.toml"
		echo "${FMD_CONFIG_CONTENT}" >"${LOCAL_CONFIG_CONTENT_TMP}"
		rsync -az -e "ssh -p ${REMOTE_PORT} -o StrictHostKeyChecking=no" \
			"${LOCAL_CONFIG_CONTENT_TMP}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_CONFIG_CONTENT_PATH}"
		COMMAND_LINE="${COMMAND_LINE} --config-path ${REMOTE_CONFIG_CONTENT_PATH}"
		rm -f "${LOCAL_CONFIG_CONTENT_TMP}"
	fi

	if [[ "${FMD_CONFIG_OVERRIDES:-}" ]]; then
		LOCAL_CONFIG_OVERRIDES_TMP=$(mktemp)
		REMOTE_CONFIG_OVERRIDES_PATH="/tmp/fmd_config_overrides_${current_datetime}.toml"
		echo "${FMD_CONFIG_OVERRIDES}" >"${LOCAL_CONFIG_OVERRIDES_TMP}"
		rsync -az -e "ssh -p ${REMOTE_PORT} -o StrictHostKeyChecking=no" \
			"${LOCAL_CONFIG_OVERRIDES_TMP}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_CONFIG_OVERRIDES_PATH}"
		COMMAND_LINE="${COMMAND_LINE} --config-overrides ${REMOTE_CONFIG_OVERRIDES_PATH}"
		rm -f "${LOCAL_CONFIG_OVERRIDES_TMP}"
	fi

	FRAPPE_DEPLOYER_CMD="/home/${REMOTE_USER}/.fmd/venv/bin/frappe-deployer ${COMMAND_LINE}"
	if [[ -n "${REMOTE_APP_ENV_FILE}" ]]; then
		FRAPPE_DEPLOYER_CMD="set -a && . ${REMOTE_APP_ENV_FILE} && set +a && ${FRAPPE_DEPLOYER_CMD}"
	fi

	ssh -p "${REMOTE_PORT}" -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
		"cd /home/${REMOTE_USER}/.fmd/logs && ${FRAPPE_DEPLOYER_CMD} 2>&1"

	DEPLOY_EXIT_CODE=$?

	ssh -p "${REMOTE_PORT}" -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
		"rm -rf ${REMOTE_FMD_SRC}" || true
	if [[ -n "${REMOTE_APP_ENV_FILE}" ]]; then
		ssh -p "${REMOTE_PORT}" -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
			"rm -f ${REMOTE_APP_ENV_FILE}" || true
	fi

	if [ "${DEPLOY_EXIT_CODE}" -eq 0 ]; then
		echo "deployment_status=success" >>"${GITHUB_OUTPUT}"
	else
		echo "deployment_status=failure" >>"${GITHUB_OUTPUT}"
		exit ${DEPLOY_EXIT_CODE}
	fi
}

ship_command() {
	REMOTE_PORT="${SSH_PORT:-22}"

	[[ "${SSH_PRIVATE_KEY:-}" ]] || emergency "ENV: ${CYAN} SSH_PRIVATE_KEY ${ENDCOLOR} is missing for 'ship' command."
	[[ "${FMD_GITHUB_TOKEN:-}" ]] || emergency "ENV: ${CYAN} FMD_GITHUB_TOKEN ${ENDCOLOR} is missing."
	[[ "${FMD_CONFIG_PATH:-}" ]] || emergency "Input: ${CYAN} config_path ${ENDCOLOR} is required for 'ship' command."

	TEMP_SSH_DIR=$(mktemp -d /tmp/ssh_dir.XXXXXX)
	export HOME="${TEMP_SSH_DIR}"
	trap 'rm -rf "${TEMP_SSH_DIR}"' EXIT

	TOML_CONFIG_FILE="${GITHUB_WORKSPACE}/${FMD_CONFIG_PATH}"

	if [[ -z "${SSH_SERVER:-}" ]]; then
		SSH_SERVER=$(toml_get "${TOML_CONFIG_FILE}" "host")
		[[ -n "${SSH_SERVER}" ]] || emergency "Either set ${CYAN}ssh_server${ENDCOLOR} input or define ${CYAN}[ship].host${ENDCOLOR} in TOML config."
	fi

	if [[ -z "${SSH_USER:-}" ]]; then
		SSH_USER=$(toml_get "${TOML_CONFIG_FILE}" "ssh_user")
		SSH_USER="${SSH_USER:-frappe}"
	fi

	REMOTE_HOST="${SSH_SERVER}"
	REMOTE_USER="${SSH_USER}"

	setup_ssh

	COMMAND="deploy ship --config ${GITHUB_WORKSPACE}/${FMD_CONFIG_PATH}"
	COMMAND="${COMMAND} --github-token ${FMD_GITHUB_TOKEN}"

	if [ -n "${INPUT_EXISTING_RELEASE:-}" ]; then
		COMMAND="${COMMAND} --existing-release ${INPUT_EXISTING_RELEASE}"
	fi

	if [ "${INPUT_SKIP_RSYNC:-false}" == "true" ]; then
		COMMAND="${COMMAND} --skip-rsync"
	fi

	if [ -n "${INPUT_RUNNER_IMAGE:-}" ]; then
		COMMAND="${COMMAND} --runner-image ${INPUT_RUNNER_IMAGE}"
	fi

	COMMAND="${COMMAND}$(build_switch_flags)"

	if [[ -n "${INPUT_APP_ENV:-}" ]]; then
		while read -r kv; do
			export "${kv?}"
		done < <(parse_app_env)
	fi

	if [[ "${FMD_CONFIG_OVERRIDES:-}" ]]; then
		LOCAL_CONFIG_OVERRIDES_TMP=$(mktemp)
		echo "${FMD_CONFIG_OVERRIDES}" >"${LOCAL_CONFIG_OVERRIDES_TMP}"
		COMMAND="${COMMAND} --config-overrides ${LOCAL_CONFIG_OVERRIDES_TMP}"
	fi

	fmd ${COMMAND}
	DEPLOY_EXIT_CODE=$?

	if [[ -n "${LOCAL_CONFIG_OVERRIDES_TMP:-}" ]]; then
		rm -f "${LOCAL_CONFIG_OVERRIDES_TMP}"
	fi

	RELEASE_ID=$(find . -maxdepth 1 -type d -name 'release_*' | sort -r | head -1 | xargs basename 2>/dev/null || echo "")
	if [[ -n "${RELEASE_ID}" ]]; then
		echo "release_id=${RELEASE_ID}" >>"${GITHUB_OUTPUT}"
	fi

	if [ "${DEPLOY_EXIT_CODE}" -eq 0 ]; then
		echo "deployment_status=success" >>"${GITHUB_OUTPUT}"
	else
		echo "deployment_status=failure" >>"${GITHUB_OUTPUT}"
		exit ${DEPLOY_EXIT_CODE}
	fi
}

build_image_command() {
	[[ "${FMD_GITHUB_TOKEN:-}" ]] || emergency "ENV: ${CYAN} FMD_GITHUB_TOKEN ${ENDCOLOR} is missing."

	COMMAND="build-image --push --github-token ${FMD_GITHUB_TOKEN}"

	if [[ "${FMD_CONFIG_PATH:-}" ]]; then
		COMMAND="${COMMAND} --config-path ${GITHUB_WORKSPACE}/${FMD_CONFIG_PATH}"
	fi

	if [[ "${FMD_CONFIG_CONTENT:-}" ]]; then
		LOCAL_CONFIG_CONTENT_TMP=$(mktemp)
		echo "${FMD_CONFIG_CONTENT}" >"${LOCAL_CONFIG_CONTENT_TMP}"
		COMMAND="${COMMAND} --config-path ${LOCAL_CONFIG_CONTENT_TMP}"
	fi

	if [[ "${FMD_CONFIG_OVERRIDES:-}" ]]; then
		LOCAL_CONFIG_OVERRIDES_TMP=$(mktemp)
		echo "${FMD_CONFIG_OVERRIDES}" >"${LOCAL_CONFIG_OVERRIDES_TMP}"
		COMMAND="${COMMAND} --config-overrides ${LOCAL_CONFIG_OVERRIDES_TMP}"
	fi

	if [[ "${INPUT_OUTPUT_DIR:-}" ]]; then
		COMMAND="${COMMAND} --output-dir ${INPUT_OUTPUT_DIR}"
	fi

	if [[ "${INPUT_FORCE}" == "true" ]]; then
		COMMAND="${COMMAND} --force"
	fi

	if [[ "${INPUT_IMAGE_TYPE:-}" ]]; then
		COMMAND="${COMMAND} --image-type ${INPUT_IMAGE_TYPE}"
	fi

	if [[ -n "${INPUT_APP_ENV:-}" ]]; then
		while read -r kv; do
			export "${kv?}"
		done < <(parse_app_env)
	fi

	fmd ${COMMAND}
	BUILD_EXIT_CODE=$?

	if [[ -n "${LOCAL_CONFIG_CONTENT_TMP:-}" ]]; then
		rm -f "${LOCAL_CONFIG_CONTENT_TMP}"
	fi
	if [[ -n "${LOCAL_CONFIG_OVERRIDES_TMP:-}" ]]; then
		rm -f "${LOCAL_CONFIG_OVERRIDES_TMP}"
	fi

	if [ "${BUILD_EXIT_CODE}" -eq 0 ]; then
		echo "deployment_status=success" >>"${GITHUB_OUTPUT}"
	else
		echo "deployment_status=failure" >>"${GITHUB_OUTPUT}"
		exit ${BUILD_EXIT_CODE}
	fi
}

main() {
	if [ "${INPUT_COMMAND}" == "pull" ]; then
		pull_command
	elif [ "${INPUT_COMMAND}" == "ship" ]; then
		ship_command
	elif [ "${INPUT_COMMAND}" == "build-image" ]; then
		build_image_command
	else
		emergency "Invalid command: ${INPUT_COMMAND}. Must be 'pull' or 'ship'."
	fi
}

main

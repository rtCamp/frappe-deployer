#!/bin/bash
__dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

if [[ "${DEBUG:-}" == "true" ]]; then
	set -x
fi

source "$__dir/helpers.sh"

pull_command() {
	REMOTE_HOST="${SSH_SERVER}"
	REMOTE_USER="${SSH_USER}"

	[[ "${REMOTE_HOST:-}" ]] || emergency "ENV: ${CYAN} SSH_SERVER ${ENDCOLOR} is missing for 'pull' command."
	[[ "${REMOTE_USER:-}" ]] || emergency "ENV: ${CYAN} SSH_USER ${ENDCOLOR} is missing for 'pull' command."
	[[ "${SSH_PRIVATE_KEY:-}" ]] || emergency "ENV: ${CYAN} SSH_PRIVATE_KEY ${ENDCOLOR} is missing for 'pull' command."

	[[ "${FRAPPE_DEPLOYER_GITHUB_TOKEN:-}" ]] || emergency "ENV: ${CYAN} FRAPPE_DEPLOYER_GITHUB_TOKEN ${ENDCOLOR} is missing."
	[[ "${INPUT_SITENAME:-}" ]] || emergency "Input: ${CYAN} sitename ${ENDCOLOR} is missing."

	# Construct COMMAND
	COMMAND="pull ${INPUT_SITENAME} --github-token ${FRAPPE_DEPLOYER_GITHUB_TOKEN}"
	COMMAND="${COMMAND} --configure"

	if [ "${INPUT_DRAIN_WORKERS:-false}" == "true" ]; then
		COMMAND="${COMMAND} --drain-workers"
	else
		COMMAND="${COMMAND} --no-drain-workers"
	fi

	if [ -n "${INPUT_DRAIN_WORKERS_TIMEOUT:-}" ]; then
		COMMAND="${COMMAND} --drain-workers-timeout ${INPUT_DRAIN_WORKERS_TIMEOUT}"
	fi

	if [ -n "${INPUT_DRAIN_WORKERS_POLL:-}" ]; then
		COMMAND="${COMMAND} --drain-workers-poll ${INPUT_DRAIN_WORKERS_POLL}"
	fi

	if [ "${INPUT_SKIP_STALE_WORKERS:-true}" == "true" ]; then
		COMMAND="${COMMAND} --skip-stale-workers"
	else
		COMMAND="${COMMAND} --no-skip-stale-workers"
	fi

	if [ -n "${INPUT_SKIP_STALE_TIMEOUT:-}" ]; then
		COMMAND="${COMMAND} --skip-stale-timeout ${INPUT_SKIP_STALE_TIMEOUT}"
	fi

	if [ "${INPUT_MIGRATE:-true}" == "true" ]; then
		COMMAND="${COMMAND} --migrate"
	else
		COMMAND="${COMMAND} --no-migrate"
	fi

	if [ -n "${INPUT_MIGRATE_TIMEOUT:-}" ]; then
		COMMAND="${COMMAND} --migrate-timeout ${INPUT_MIGRATE_TIMEOUT}"
	fi

	if [ -n "${INPUT_MIGRATE_COMMAND:-}" ]; then
		COMMAND="${COMMAND} --migrate-command '${INPUT_MIGRATE_COMMAND}'"
	fi

	if [ -n "${INPUT_MAINTENANCE_MODE_PHASES:-}" ]; then
		for phase in ${INPUT_MAINTENANCE_MODE_PHASES}; do
			COMMAND="${COMMAND} --maintenance-mode-phases ${phase}"
		done
	fi

	if [ -n "${INPUT_WORKER_KILL_TIMEOUT:-}" ]; then
		COMMAND="${COMMAND} --worker-kill-timeout ${INPUT_WORKER_KILL_TIMEOUT}"
	fi

	if [ -n "${INPUT_WORKER_KILL_POLL:-}" ]; then
		COMMAND="${COMMAND} --worker-kill-poll ${INPUT_WORKER_KILL_POLL}"
	fi

	if [ -n "${INPUT_ADDITIONAL_COMMANDS:-}" ]; then
		COMMAND="${COMMAND} ${INPUT_ADDITIONAL_COMMANDS}"
	fi

	SSH_KEY_PATH="/tmp/ssh_key"
	echo "${SSH_PRIVATE_KEY}" >"${SSH_KEY_PATH}"
	chmod 600 "${SSH_KEY_PATH}"
	setup_ssh

	current_datetime=$(date +"%Y-%m-%d_%H-%M-%S")

	# Transfer per-app env vars to remote as a secure temp file.
	# Format: one "app-name:KEY=VALUE" per line — app-name is stripped, KEY=VALUE is forwarded.
	REMOTE_APP_ENV_FILE=""
	if [[ -n "${INPUT_APP_ENV:-}" ]]; then
		REMOTE_APP_ENV_FILE="/tmp/.fmd_app_env_${current_datetime}"
		LOCAL_APP_ENV_TMP=$(mktemp)

		while IFS= read -r line; do
			[[ -z "${line// /}" ]] && continue
			[[ "${line}" == \#* ]] && continue
			kv="${line#*:}" # strip "app-name:" prefix
			if [[ "${kv}" == *"="* ]]; then
				printf "%s\n" "${kv}" >>"${LOCAL_APP_ENV_TMP}"
			else
				warn "app_env: skipping malformed line (expected 'app-name:KEY=VALUE'): ${line}"
			fi
		done <<<"${INPUT_APP_ENV}"

		rsync -az -e "ssh -i ${SSH_KEY_PATH} -o StrictHostKeyChecking=no" \
			"${LOCAL_APP_ENV_TMP}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_APP_ENV_FILE}"
		ssh -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" "chmod 600 ${REMOTE_APP_ENV_FILE}"
		rm -f "${LOCAL_APP_ENV_TMP}"
	fi

	REMOTE_FMD_SRC="/tmp/fmd_src_${current_datetime}"
	rsync -az --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
		-e "ssh -i ${SSH_KEY_PATH} -o StrictHostKeyChecking=no" \
		"${GITHUB_ACTION_PATH}/" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_FMD_SRC}/"

	remote_execute "/home/${REMOTE_USER}" \
		"test -x /home/${REMOTE_USER}/.local/bin/uv || curl -LsSf https://astral.sh/uv/install.sh | sh"

	remote_execute "/home/${REMOTE_USER}" \
		"mkdir -p /home/${REMOTE_USER}/.fmd/logs && rm -rf /home/${REMOTE_USER}/.fmd/venv && /home/${REMOTE_USER}/.local/bin/uv venv /home/${REMOTE_USER}/.fmd/venv --python 3.10 && /home/${REMOTE_USER}/.local/bin/uv pip install --python /home/${REMOTE_USER}/.fmd/venv/bin/python ${REMOTE_FMD_SRC}"

	COMMAND_LINE="${COMMAND}"

	if [[ "${FRAPPE_DEPLOYER_CONFIG_PATH:-}" ]]; then
		LOCAL_CONFIG_PATH="${GITHUB_WORKSPACE}/${FRAPPE_DEPLOYER_CONFIG_PATH}"
		REMOTE_CONFIG_PATH="/tmp/$(basename ${FRAPPE_DEPLOYER_CONFIG_PATH})_${current_datetime}"
		rsync -az -e "ssh -i ${SSH_KEY_PATH} -o StrictHostKeyChecking=no" "${LOCAL_CONFIG_PATH}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_CONFIG_PATH}"
		COMMAND_LINE="${COMMAND_LINE} --config-path ${REMOTE_CONFIG_PATH}"
	fi

	if [[ "${FRAPPE_DEPLOYER_CONFIG_CONTENT:-}" ]]; then
		COMMAND_LINE="${COMMAND_LINE} --config-content '${FRAPPE_DEPLOYER_CONFIG_CONTENT}'"
	fi

	FRAPPE_DEPLOYER_CMD="/home/${REMOTE_USER}/.fmd/venv/bin/frappe-deployer ${COMMAND_LINE}"
	if [[ -n "${REMOTE_APP_ENV_FILE}" ]]; then
		FRAPPE_DEPLOYER_CMD="set -a && . ${REMOTE_APP_ENV_FILE} && set +a && ${FRAPPE_DEPLOYER_CMD}"
	fi

	remote_execute "/home/${REMOTE_USER}/.fmd/logs" \
		"${FRAPPE_DEPLOYER_CMD} 2>&1"

	ssh -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" "rm -rf ${REMOTE_FMD_SRC}" || true
	if [[ -n "${REMOTE_APP_ENV_FILE}" ]]; then
		ssh -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" "rm -f ${REMOTE_APP_ENV_FILE}" || true
	fi
}

build_image_command() {
	[[ "${FRAPPE_DEPLOYER_GITHUB_TOKEN:-}" ]] || emergency "ENV: ${CYAN} FRAPPE_DEPLOYER_GITHUB_TOKEN ${ENDCOLOR} is missing."

	COMMAND="build-image --push --github-token ${FRAPPE_DEPLOYER_GITHUB_TOKEN}"

	if [[ "${FRAPPE_DEPLOYER_CONFIG_PATH:-}" ]]; then
		COMMAND="${COMMAND} --config-path ${GITHUB_WORKSPACE}/${FRAPPE_DEPLOYER_CONFIG_PATH}"
	fi

	if [[ "${FRAPPE_DEPLOYER_CONFIG_CONTENT:-}" ]]; then
		COMMAND="${COMMAND} --config-content '${FRAPPE_DEPLOYER_CONFIG_CONTENT}'"
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

	# Here we execute frappe-deployer locally, not on a remote server.
	# The user needs to ensure docker is available.
	frappe-deployer ${COMMAND}
}

main() {
	if [ "${INPUT_COMMAND}" == "pull" ]; then
		pull_command
	elif [ "${INPUT_COMMAND}" == "build-image" ]; then
		build_image_command
	else
		emergency "Invalid command: ${INPUT_COMMAND}. Must be 'pull' or 'build-image'."
	fi
}

main

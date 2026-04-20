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

merge_toml() {
	local user_toml="$1"
	local generated_toml="$2"
	python3 - "${user_toml}" "${generated_toml}" << 'PYTHON_EOF'
import sys
import tomllib

def deep_merge(base, override):
	"""Deep merge override into base, modifying base in place."""
	for key, value in override.items():
		if key in base and isinstance(base[key], dict) and isinstance(value, dict):
			deep_merge(base[key], value)
		else:
			base[key] = value
	return base

user_toml = sys.argv[1] if len(sys.argv) > 1 else ""
generated_toml = sys.argv[2] if len(sys.argv) > 2 else ""

merged = {}

# Parse user TOML (if provided)
if user_toml and user_toml.strip():
	try:
		merged = tomllib.loads(user_toml)
	except Exception as e:
		print(f"Error parsing user config_overrides: {e}", file=sys.stderr)
		sys.exit(1)

# Parse generated TOML (if provided)
if generated_toml and generated_toml.strip():
	try:
		generated = tomllib.loads(generated_toml)
		deep_merge(merged, generated)
	except Exception as e:
		print(f"Error parsing generated config: {e}", file=sys.stderr)
		sys.exit(1)

# Output merged TOML
if merged:
	import io
	try:
		# Use tomli_w if available (Python 3.11+), otherwise manual formatting
		try:
			import tomli_w
			print(tomli_w.dumps(merged), end='')
		except ImportError:
			# Manual TOML formatting (simple cases only)
			for section, values in merged.items():
				if isinstance(values, dict):
					print(f"[{section}]")
					for key, val in values.items():
						if isinstance(val, bool):
							print(f"{key} = {str(val).lower()}")
						elif isinstance(val, str):
							print(f'{key} = "{val}"')
						elif isinstance(val, list):
							formatted_list = ", ".join([f'"{item}"' if isinstance(item, str) else str(item) for item in val])
							print(f"{key} = [{formatted_list}]")
						else:
							print(f"{key} = {val}")
					print()
				else:
					# Top-level key-value
					if isinstance(values, bool):
						print(f"{section} = {str(values).lower()}")
					elif isinstance(values, str):
						print(f'{section} = "{values}"')
					else:
						print(f"{section} = {values}")
	except Exception as e:
		print(f"Error formatting merged TOML: {e}", file=sys.stderr)
		sys.exit(1)
PYTHON_EOF
}

build_config_overrides() {
	local host="${1:-}"
	local ssh_user="${2:-}"
	local ssh_port="${3:-22}"
	local overrides=""

	if [[ -n "${host}" ]]; then
		overrides+="[ship]\n"
		overrides+="host = \"${host}\"\n"
		overrides+="ssh_user = \"${ssh_user}\"\n"
		overrides+="ssh_port = ${ssh_port}\n"
		overrides+="\n"
	fi

	overrides+="[switch]\n"

	if [ "${INPUT_MIGRATE:-true}" == "true" ]; then
		overrides+="migrate = true\n"
	else
		overrides+="migrate = false\n"
	fi

	if [ -n "${INPUT_MIGRATE_TIMEOUT:-}" ]; then
		overrides+="migrate_timeout = ${INPUT_MIGRATE_TIMEOUT}\n"
	fi

	if [ "${INPUT_DRAIN_WORKERS:-false}" == "true" ]; then
		overrides+="drain_workers = true\n"
	else
		overrides+="drain_workers = false\n"
	fi

	if [ "${INPUT_MAINTENANCE_MODE:-false}" == "true" ]; then
		overrides+="maintenance_mode = true\n"
	else
		overrides+="maintenance_mode = false\n"
	fi

	if [ -n "${INPUT_MAINTENANCE_MODE_PHASES:-}" ]; then
		overrides+="maintenance_mode_phases = ["
		for phase in ${INPUT_MAINTENANCE_MODE_PHASES}; do
			overrides+="\"${phase}\", "
		done
		overrides="${overrides%, }"
		overrides+="]\n"
	fi

	if [ "${INPUT_BACKUPS:-false}" == "true" ]; then
		overrides+="backups = true\n"
	else
		overrides+="backups = false\n"
	fi

	if [ "${INPUT_ROLLBACK:-false}" == "true" ]; then
		overrides+="rollback = true\n"
	else
		overrides+="rollback = false\n"
	fi

	echo -e "${overrides}"
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

	setup_ssh

	current_datetime=$(date +"%Y-%m-%d_%H-%M-%S")

	BASE_CONFIG_CONTENT=""
	if [[ "${FMD_CONFIG_PATH:-}" ]]; then
		BASE_CONFIG_CONTENT=$(cat "${GITHUB_WORKSPACE}/${FMD_CONFIG_PATH}")
	elif [[ "${FMD_CONFIG_CONTENT:-}" ]]; then
		BASE_CONFIG_CONTENT="${FMD_CONFIG_CONTENT}"
	fi

	GENERATED_OVERRIDES=$(build_config_overrides "${REMOTE_HOST}" "${REMOTE_USER}" "${REMOTE_PORT}")
	AFTER_USER_OVERRIDES=$(merge_toml "${BASE_CONFIG_CONTENT}" "${FMD_CONFIG_OVERRIDES:-}")
	MERGED_CONFIG=$(merge_toml "${AFTER_USER_OVERRIDES}" "${GENERATED_OVERRIDES}")

	LOCAL_CONFIG_TMP=$(mktemp --suffix=.toml)
	echo "${MERGED_CONFIG}" >"${LOCAL_CONFIG_TMP}"

	REMOTE_FMD_SRC="/tmp/fmd_src_${current_datetime}"
	rsync -az --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
		-e "ssh -p ${REMOTE_PORT} -o StrictHostKeyChecking=no" \
		"${GITHUB_ACTION_PATH}/" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_FMD_SRC}/"

	ssh -p "${REMOTE_PORT}" -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
		"cd /home/${REMOTE_USER} && test -x /home/${REMOTE_USER}/.local/bin/uv || curl -LsSf https://astral.sh/uv/install.sh | sh"

	ssh -p "${REMOTE_PORT}" -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
		"cd /home/${REMOTE_USER} && mkdir -p /home/${REMOTE_USER}/.fmd/logs && rm -rf /home/${REMOTE_USER}/.fmd/venv && /home/${REMOTE_USER}/.local/bin/uv venv /home/${REMOTE_USER}/.fmd/venv --python 3.10 && /home/${REMOTE_USER}/.local/bin/uv pip install --python /home/${REMOTE_USER}/.fmd/venv/bin/python ${REMOTE_FMD_SRC}"

	REMOTE_CONFIG_PATH="/tmp/fmd_config_${current_datetime}.toml"
	rsync -az -e "ssh -p ${REMOTE_PORT} -o StrictHostKeyChecking=no" \
		"${LOCAL_CONFIG_TMP}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_CONFIG_PATH}"
	rm -f "${LOCAL_CONFIG_TMP}"

	COMMAND_LINE="${COMMAND} --config ${REMOTE_CONFIG_PATH}"
	FRAPPE_DEPLOYER_CMD="/home/${REMOTE_USER}/.fmd/venv/bin/frappe-deployer ${COMMAND_LINE}"

	ssh -p "${REMOTE_PORT}" -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
		"cd /home/${REMOTE_USER}/.fmd/logs && ${FRAPPE_DEPLOYER_CMD} 2>&1"

	DEPLOY_EXIT_CODE=$?

	ssh -p "${REMOTE_PORT}" -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
		"rm -rf ${REMOTE_FMD_SRC}" || true

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

	BASE_CONFIG_CONTENT=$(cat "${GITHUB_WORKSPACE}/${FMD_CONFIG_PATH}")
	GENERATED_OVERRIDES=$(build_config_overrides "${REMOTE_HOST}" "${REMOTE_USER}" "${REMOTE_PORT}")
	AFTER_USER_OVERRIDES=$(merge_toml "${BASE_CONFIG_CONTENT}" "${FMD_CONFIG_OVERRIDES:-}")
	MERGED_CONFIG=$(merge_toml "${AFTER_USER_OVERRIDES}" "${GENERATED_OVERRIDES}")

	LOCAL_CONFIG_TMP=$(mktemp --suffix=.toml)
	echo "${MERGED_CONFIG}" >"${LOCAL_CONFIG_TMP}"

	COMMAND="deploy ship --config ${LOCAL_CONFIG_TMP}"
	COMMAND="${COMMAND} --github-token ${FMD_GITHUB_TOKEN}"

	if [ -n "${INPUT_EXISTING_RELEASE:-}" ]; then
		COMMAND="${COMMAND} --existing-release ${INPUT_EXISTING_RELEASE}"
	fi

	if [ "${INPUT_SKIP_RSYNC:-false}" == "true" ]; then
		COMMAND="${COMMAND} --skip-rsync"
	fi

	fmd ${COMMAND}
	DEPLOY_EXIT_CODE=$?

	rm -f "${LOCAL_CONFIG_TMP}"

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

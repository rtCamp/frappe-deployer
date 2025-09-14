#!/bin/bash
source "$(dirname "$0")/helpers.sh"

init() {
    info "Initializing frappe-deployer GitHub Action"
    
    # Set remote connection variables
    REMOTE_HOST="${SSH_SERVER}"
    REMOTE_USER="${SSH_USER}"
    BINARY_PATH="/fmd"

    # Validate required environment variables
    [[ "${REMOTE_HOST:-}" ]] || emergency "ENV: SSH_SERVER is missing."
    [[ "${REMOTE_USER:-}" ]] || emergency "ENV: SSH_USER is missing."
    [[ "${FRAPPE_DEPLOYER_COMMAND:-}" ]] || emergency "ENV: FRAPPE_DEPLOYER_COMMAND is missing."
    [[ "${SSH_PRIVATE_KEY:-}" ]] || emergency "ENV: SSH_PRIVATE_KEY is missing."

    # Check user authorization
    check_user_authorization

    # Setup SSH
    setup_ssh
    
    info "Initialization completed successfully"
}

deploy() {
    info "Starting frappe-deployer deployment"

    # Get binary size for logging
    BINARY_SIZE=$(du -h "$BINARY_PATH" | cut -f1)
    info "Binary size: $BINARY_SIZE"
    
    # Copy fmd binary to remote server
    info "Copying fmd binary to remote server"
    remote_binary_path="/tmp/frappe-deployer-$(date +%s)"
    
    remote_copy "$BINARY_PATH" "${remote_binary_path}"
    
    info "Setting up binary on remote server"
    remote_execute "/tmp" "chmod +x ${remote_binary_path}"
    test_remote_binary "${remote_binary_path}"
    
    # Handle config file if provided
    local final_command="$FRAPPE_DEPLOYER_COMMAND"
    local remote_config_path=""
    
    if [[ "${FRAPPE_DEPLOYER_CONFIG_PATH:-}" ]] && [[ -f "$FRAPPE_DEPLOYER_CONFIG_PATH" ]]; then
        info "Config file provided: $FRAPPE_DEPLOYER_CONFIG_PATH"
        validate_config_file "$FRAPPE_DEPLOYER_CONFIG_PATH"
        
        # Generate unique remote config path
        local current_datetime=$(date +"%Y-%m-%d_%H-%M-%S")
        remote_config_path="/tmp/$(basename ${FRAPPE_DEPLOYER_CONFIG_PATH})_${current_datetime}"
        
        info "Copying config file to remote server: $remote_config_path"
        remote_copy "$FRAPPE_DEPLOYER_CONFIG_PATH" "${remote_config_path}"
        
        # Update command to use remote config path
        final_command="$final_command --config-path $remote_config_path"
    else
        info "No config file provided or file not found, using command-line arguments only"
    fi
    
    # Log the final command (mask sensitive info)
    local masked_command=$(echo "$final_command" | sed 's/--github-token [^ ]*/--github-token ***MASKED***/g')
    info "Executing frappe-deployer command: $masked_command"
    
    # Create logs directory and execute frappe-deployer on remote
    info "Executing fmd on remote server"
    set +e  # Don't exit immediately on error to allow cleanup
    remote_execute "~/.frappe_deployer_logs" "mkdir -p ~/.frappe_deployer_logs && \
    echo 'Starting deployment at \$(date)' && \
    ${remote_binary_path} ${final_command} 2>&1 && \
    echo 'Deployment completed at \$(date)'"
    
    local exit_code=$?
    set -e  # Re-enable exit on error
    
    # Cleanup remote files
    info "Cleaning up temporary files on remote server"
    remote_execute "/" "rm -f ${remote_binary_path} ${remote_config_path}" || true
    
    if [[ $exit_code -eq 0 ]]; then
        info "Deployment completed successfully"
    else
        emergency "Deployment failed with exit code: $exit_code"
    fi
}

generate_summary() {
    info "Generating deployment summary"
    
    cat << EOF

==================================================
🚀 Frappe Deployment Summary
==================================================
Environment:     ${ENVIRONMENT:-unknown}
Server:          $REMOTE_HOST
User:            $REMOTE_USER
Triggered by:    ${GITHUB_ACTOR:-unknown}
Repository:      ${GITHUB_REPOSITORY:-unknown}
Commit:          ${GITHUB_SHA:-unknown}
Binary Path:     ${BINARY_PATH:-unknown}
==================================================

EOF
}

# Main execution flow
main() {
    info "🚀 Starting Frappe Deployer GitHub Action"

    init
    deploy
    generate_summary
    
    info "✅ Frappe Deployer GitHub Action completed successfully"
}

main "$@"

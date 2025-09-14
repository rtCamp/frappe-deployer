#!/bin/bash
source /helpers.sh

init() {
    info "Initializing frappe-deployer GitHub Action"
    
    # Set remote connection variables
    REMOTE_HOST="${SSH_SERVER}"
    REMOTE_USER="${SSH_USER}"

    # Validate required environment variables
    [[ "${REMOTE_HOST:-}" ]] || emergency "ENV: ${CYAN}SSH_SERVER${ENDCOLOR} is missing."
    [[ "${REMOTE_USER:-}" ]] || emergency "ENV: ${CYAN}SSH_USER${ENDCOLOR} is missing."
    [[ "${FRAPPE_DEPLOYER_COMMAND:-}" ]] || emergency "ENV: ${CYAN}FRAPPE_DEPLOYER_COMMAND${ENDCOLOR} is missing."
    [[ "${SSH_PRIVATE_KEY:-}" ]] || emergency "ENV: ${CYAN}SSH_PRIVATE_KEY${ENDCOLOR} is missing."

    # Check user authorization
    check_user_authorization

    # Setup SSH
    setup_ssh
    
    info "Initialization completed successfully"
}

deploy() {
    info "Starting frappe-deployer deployment"
    
    # Find the frappe-deployer binary
    BINARY_PATH="/fmd"
    if [[ ! -f "$BINARY_PATH" ]]; then
        # Try alternative locations
        BINARY_PATH=$(find /frappe-deployer -name "frappe-deployer" -type f -executable 2>/dev/null | head -1)
        if [[ ! -f "$BINARY_PATH" ]]; then
            emergency "frappe-deployer binary not found. Available files:"
            find /frappe-deployer -type f -name "*frappe*" || true
            exit 1
        fi
    fi
    
    info "Found frappe-deployer binary at: $BINARY_PATH"
    
    # Get binary size for logging
    BINARY_SIZE=$(du -h "$BINARY_PATH" | cut -f1)
    info "Binary size: $BINARY_SIZE"
    
    # Copy PYAPP binary to remote server
    info "Copying frappe-deployer binary to remote server"
    remote_binary_path="/tmp/frappe-deployer-$(date +%s)"
    
    scp -o StrictHostKeyChecking=no \
        "$BINARY_PATH" \
        "${REMOTE_USER}@${REMOTE_HOST}:${remote_binary_path}"
    
    # Make binary executable on remote and test it
    info "Setting up binary on remote server"
    ssh -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
        "chmod +x ${remote_binary_path} && ${remote_binary_path} --version"
    
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
        scp -o StrictHostKeyChecking=no "$FRAPPE_DEPLOYER_CONFIG_PATH" \
            "${REMOTE_USER}@${REMOTE_HOST}:${remote_config_path}"
        
        # Update command to use remote config path
        final_command="$final_command --config-path $remote_config_path"
    else
        info "No config file provided or file not found, using command-line arguments only"
    fi
    
    # Log the final command (mask sensitive info)
    local masked_command=$(echo "$final_command" | sed 's/--github-token [^ ]*/--github-token ***MASKED***/g')
    info "Executing frappe-deployer command: $masked_command"
    
    # Create logs directory and execute frappe-deployer on remote
    info "Executing frappe-deployer on remote server"
    set +e  # Don't exit immediately on error to allow cleanup
    ssh -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
        "mkdir -p ~/.frappe_deployer_logs && \
         cd ~/.frappe_deployer_logs && \
         echo 'Starting deployment at \$(date)' && \
         ${remote_binary_path} ${final_command} 2>&1 && \
         echo 'Deployment completed at \$(date)'"
    
    local exit_code=$?
    set -e  # Re-enable exit on error
    
    # Cleanup remote files
    info "Cleaning up temporary files on remote server"
    ssh -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
        "rm -f ${remote_binary_path} ${remote_config_path}" 2>/dev/null || true
    
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
    
    # Initialize environment and SSH
    init
    
    # Execute deployment
    deploy
    
    # Generate summary
    generate_summary
    
    info "✅ Frappe Deployer GitHub Action completed successfully"
}

# Run main function
main "$@"

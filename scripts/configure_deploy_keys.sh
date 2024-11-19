#!/bin/bash

# Array of repository names to configure deploy keys for
repos=(
    "REPLACE_ME_WITH_FIRST_REPO"
    "REPLACE_ME_WITH_SECOND_REPO"
)

# Configure github token
GITHUB_TOKEN="REPLACE_ME_WITH_GITHUB_TOKEN"


GITHUB_ORG_NAME="REPLACE_ME_WITH_ORG_NAME"
SSH_COMMENT_EMAIL='REPLACE_ME_WITH_EMAIL'


server_hostname=$(hostname)
ssh_dir="$HOME/.ssh"
key_dir="$ssh_dir/deploy_keys"

ssh_config="$ssh_dir/deploy_keys_config"
timestamp=$(date +"%Y%m%d%H%M%S")

# Backup existing SSH config file if it exists
if [[ -f "$ssh_config" ]]; then
    cp "$ssh_config" "$ssh_config.bak-$timestamp"
fi

# Backup existing deploy keys directory if it exists
if [[ -d "$key_dir" ]]; then
    mv "$key_dir" "$key_dir-bak-$timestamp"
fi

# Create the deploy keys directory
mkdir -p "$key_dir"

# Clear the SSH config file
> "$ssh_config"

# Loop through each repository in the repos array
for repo in "${repos[@]}"; do

    echo "Configuring for ${repo}"

    key_path="$key_dir/${repo}_deploy_key"
    ssh-keygen -t ed25519 -C "${hostname} ${app} ${SSH_COMMENT_EMAIL}" -N "" -f "$key_path"

    # Add SSH config entry
    cat >> "$ssh_config" <<EOL
Host ${repo}
    HostName github.com
    User git
    IdentityFile ${key_path}
    IdentitiesOnly yes
EOL

    # Read the public key
    pub_key=$(cat "${key_path}.pub")

    header_auth="Authorization: token ${GITHUB_TOKEN}"
    header_accept='Accept: application/vnd.github+json'
    header_api='X-GitHub-Api-Version: 2022-11-28'

    # Check if the deploy key already exists
    existing_keys=$(curl -s \
        -H "$header_auth" \
        -H "$header_accept" \
        -H "$header_api" \
        https://api.github.com/repos/${GITHUB_ORG_NAME}/${repo}/keys)

    key_id=$(echo "$existing_keys" | jq -r ".[] | select(.title == \"deploy-key-$server_hostname\") | .id")

    if [ -n "$key_id" ]; then
        # Delete the existing deploy key
        #
        curl -X DELETE \
            -H "$header_auth" \
            -H "$header_accept" \
            -H "$header_api" \
            https://api.github.com/repos/${GITHUB_ORG_NAME}/${repo}/keys/${key_id}
        echo "Existing deploy key for ${repo} deleted."
    fi

     # Add the new deploy key to the GitHub repository
    curl -X POST \
        -H "$header_auth" \
        -H "$header_accept" \
        -H "$header_api" \
        https://api.github.com/repos/${GITHUB_ORG_NAME}/${repo}/keys \
        -d "{\"title\":\"deploy-key-${server_hostname}\",\"key\":\"${pub_key}\",\"read_only\":true}"
    echo "Deploy key for ${repo} added."
done

echo "SSH keys and config have been set up, and deploy keys have been updated in GitHub repositories."

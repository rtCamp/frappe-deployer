from pathlib import Path
import secrets
from frappe_deployer.helpers import gen_name_with_timestamp

RELEASE_DIR_NAME = 'release'
DATA_DIR_NAME = 'deployment-data'
BACKUP_DIR_NAME = 'deployment-backup'

RELEASE_SUFFIX = gen_name_with_timestamp(RELEASE_DIR_NAME)
LOG_FILE_NAME = Path(f'./frappe-deployer-run-{RELEASE_SUFFIX}')

# Generate a random bypass token that developers can use
BYPASS_TOKEN = secrets.token_hex(16)  # 32 character hex string

MAINTENANCE_MODE_CONFIG = """
# Developer bypass route - sets bypass cookie
location /{BYPASS_TOKEN}/ {{
    add_header Set-Cookie "maintenance_bypass={BYPASS_TOKEN};Path=/;HttpOnly;Secure";
    rewrite ^/{BYPASS_TOKEN}/(.*) /$1 break;
    proxy_pass http://$host;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}}

# Check for bypass cookie and proxy if present
location / {{
    if ($cookie_maintenance_bypass = "{BYPASS_TOKEN}") {{
        proxy_pass http://$host;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        break;
    }}
    return 307 /maintenance-mode;
}}

# Maintenance mode page
location /maintenance-mode {{
    default_type text/html;
    return 200 '<!DOCTYPE html>
    <html>
    <head><title>Maintenance</title></head>
    <body>
        <h1>Site Under Maintenance</h1>
        <p>We are performing scheduled maintenance. Please try again later.</p>
    </body>
    </html>';
}}
"""

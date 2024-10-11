from pathlib import Path
from frappe_deployer.helpers import gen_name_with_timestamp

RELEASE_DIR_NAME = 'release'
DATA_DIR_NAME = 'deployment-data'
BACKUP_DIR_NAME = 'deployment-backup'

RELEASE_SUFFIX = gen_name_with_timestamp(RELEASE_DIR_NAME)
LOG_FILE_NAME = Path(f'./frappe-deployer-run-{RELEASE_SUFFIX}')

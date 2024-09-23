from frappe_manager.utils import docker
import re


commit_pattern = re.compile(r'0-9a-f{40}$', re.IGNORECASE)
is_commit = commit_pattern.match('xd')

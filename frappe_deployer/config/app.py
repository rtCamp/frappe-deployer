from typing import Optional
from pydantic import BaseModel, Field, model_validator

import os

from frappe_deployer.config.utils import get_repo_url, is_ref_commit

# Disable terminal prompts in Git
os.environ['GIT_TERMINAL_PROMPT'] = '0'

class AppConfig(BaseModel):
    repo: str
    repo_url: str
    ref: Optional[str] = None
    shallow_clone: bool = Field(True)
    is_ref_commit: bool = Field(False)
    exists: bool = Field(False)

    @property
    def dir_name(self):
        return self.repo.split('/')[-1]

    @model_validator(mode='before')
    def post_init(cls, values):
        # Perform additional initialization or validation here
        repo_url = values.get('repo_url')
        repo = values.get('repo')
        ref = values.get('ref')

        if not repo_url:
            try:
                values['repo_url'] = get_repo_url(repo,ref)
                values['exists'] = True
            except RuntimeError as e:
                values['repo_url'] = str(e)

        if is_ref_commit(ref):
            values['is_ref_commit'] = True

        return values


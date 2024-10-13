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

    @classmethod
    def from_dict(cls, data: dict['str','str']) -> 'AppConfig':
        repo = data.get('repo', None)
        ref= data.get('ref', None)
        repo_url = data.get('repo_url', None)
        shallow_clone = data.get('shallow_clone', True)
        is_ref_commit = data.get('shallow_clone', False)

        if not repo:
            raise ValueError("repo value not provided in config")

        # Perform additional initialization or validation here
        if not repo_url:
            exists = False
            try:
                repo_url = get_repo_url(repo, ref)
                exists = True
            except RuntimeError as e:
                repo_url = str(e)

        return cls(repo=repo,repo_url=repo_url,ref=ref,shallow_clone=shallow_clone, is_ref_commit=is_ref_commit,exists=exists)


    @model_validator(mode='before')
    def post_init(cls, values):
        ref = values.get('ref')

        if is_ref_commit(ref):
            values['is_ref_commit'] = True

        return values

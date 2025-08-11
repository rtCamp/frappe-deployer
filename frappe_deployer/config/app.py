from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator

import os

from frappe_deployer.config.utils import get_repo_url, is_ref_commit

# Disable terminal prompts in Git
os.environ['GIT_TERMINAL_PROMPT'] = '0'

class AppConfig(BaseModel):
    repo: str
    repo_url: Optional[str] = None
    ref: Optional[str] = None
    subdir_path: Optional[str] = None
    shallow_clone: bool = Field(True)
    is_ref_commit: bool = Field(False)
    exists: bool = Field(False)
    remove_remote: bool = Field(False)
    remote_name: str = Field("upstream", description="Name of the remote to use during cloning")
    fm_pre_build: Optional[str] = Field(None, description="Command to run before build in FM mode")
    fm_post_build: Optional[str] = Field(None, description="Command to run after build in FM mode")

    @property
    def dir_name(self):
        if self.subdir_path:
            return self.subdir_path.split('/')[-1]

        return self.repo.split('/')[-1]

    def configure_app(self, token: Optional[str] = None, remove_remote: bool = False, remote_name: Optional[str] = None, fm_pre_build: Optional[str] = None, fm_post_build: Optional[str] = None):
        self.is_ref_commit = is_ref_commit(self.ref)
        self.remove_remote = remove_remote
        
        # Set remote name if provided
        if remote_name:
            self.remote_name = remote_name
        
        # Set build commands if provided
        if fm_pre_build:
            self.fm_pre_build = fm_pre_build
        if fm_post_build:
            self.fm_post_build = fm_post_build

        if not self.repo_url:
            try:
                repo_url = get_repo_url(self.repo, self.ref, token)
                self.exists = True
            except RuntimeError as e:
                repo_url = str(e)

            self.repo_url = repo_url

    # @classmethod
    # def from_dict(cls, data: dict['str', Any], token: Optional[str] = None, remove_remote: bool = False) -> 'AppConfig':
    #     repo = data.get('repo', None)
    #     ref= data.get('ref', None)
    #     repo_url = data.get('repo_url', None)
    #     data['remove_remote'] = remove_remote
    #     # shallow_clone = data.get('shallow_clone', True)
    #     # is_ref_commit = data.get('is_ref_commit', False)

    #     if not repo:
    #         raise ValueError("App's 'repo' key not provided in config.")

    #     if not repo_url:
    #         try:
    #             repo_url = get_repo_url(repo, ref, token)
    #             data['exists'] = True
    #         except RuntimeError as e:
    #             repo_url = str(e)

    #     data['repo_url'] = repo_url
    #     return cls(**data)


    # @model_validator(mode='before')
    # def post_init(cls, values):
    #     ref = values.get('ref')

    #     if is_ref_commit(ref):
    #         values['is_ref_commit'] = True

    #     return values

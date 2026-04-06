import os
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from fmd.config.utils import get_repo_url, is_ref_commit

os.environ["GIT_TERMINAL_PROMPT"] = "0"


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo: str
    repo_url: Optional[str] = None
    ref: Optional[str] = None
    app_name: Optional[str] = None
    subdir_path: Optional[str] = None
    shallow_clone: bool = Field(True)
    is_ref_commit: bool = Field(False)
    exists: bool = Field(False)
    remove_remote: bool = Field(False)
    symlink: bool = Field(False)
    remote_name: str = Field("upstream")
    before_bench_build: Optional[str] = Field(None)
    after_bench_build: Optional[str] = Field(None)
    host_before_bench_build: Optional[str] = Field(None)
    host_after_bench_build: Optional[str] = Field(None)
    before_python_install: Optional[str] = Field(None)
    after_python_install: Optional[str] = Field(None)
    host_before_python_install: Optional[str] = Field(None)
    host_after_python_install: Optional[str] = Field(None)

    @property
    def dir_name(self) -> str:
        if self.app_name:
            return self.app_name
        if self.subdir_path:
            return self.subdir_path.split("/")[-1]
        return self.repo.split("/")[-1]

    def configure_app(
        self,
        token: Optional[str] = None,
        before_bench_build: Optional[str] = None,
        after_bench_build: Optional[str] = None,
        host_before_bench_build: Optional[str] = None,
        host_after_bench_build: Optional[str] = None,
        before_python_install: Optional[str] = None,
        after_python_install: Optional[str] = None,
        host_before_python_install: Optional[str] = None,
        host_after_python_install: Optional[str] = None,
    ) -> None:
        self.is_ref_commit = is_ref_commit(self.ref)

        if before_bench_build and not self.before_bench_build:
            self.before_bench_build = before_bench_build
        if after_bench_build and not self.after_bench_build:
            self.after_bench_build = after_bench_build
        if host_before_bench_build and not self.host_before_bench_build:
            self.host_before_bench_build = host_before_bench_build
        if host_after_bench_build and not self.host_after_bench_build:
            self.host_after_bench_build = host_after_bench_build
        if before_python_install and not self.before_python_install:
            self.before_python_install = before_python_install
        if after_python_install and not self.after_python_install:
            self.after_python_install = after_python_install
        if host_before_python_install and not self.host_before_python_install:
            self.host_before_python_install = host_before_python_install
        if host_after_python_install and not self.host_after_python_install:
            self.host_after_python_install = host_after_python_install

        if not self.repo_url:
            try:
                repo_url = get_repo_url(self.repo, self.ref, token)
                self.exists = True
            except RuntimeError as e:
                repo_url = str(e)
            self.repo_url = repo_url

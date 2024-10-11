import git
from git.exc import GitCommandError
from typing import Optional

def is_ref_commit(ref: Optional[str]):
    if ref is None:
        return False
    return len(ref) == 40 and all(c in '0123456789abcdef' for c in ref.lower())

def __check_ref_exists_for_url__(repo_url: str, ref: Optional[str]) -> bool:
    """
    Check if a ref (branch, tag, or commit) exists in the Git repository.

    :param repo_url: The URL of the repository.
    :param ref: The ref to check, can be a tag, branch, or commit.
    :return: True if the ref exists, False otherwise.
    """
    try:
        # Use git ls-remote to list refs
        remote_refs = git.cmd.Git().ls_remote(repo_url)
        refs = [line.split()[1] for line in remote_refs.splitlines()]

        if ref is None:
            return True

        # Check if ref exists
        if f"refs/heads/{ref}" in refs or f"refs/tags/{ref}" in refs or is_ref_commit(ref):
            return True

        return False

    except GitCommandError:
        return False

def get_repo_url(repo:str, ref:str, token: Optional[str] = None) -> str:
    repo_urls = []
    if token:
        repo_urls += [f"https://{token}:x-oauth-basic@github.com/{repo}"]

    repo_urls += [f"https://github.com/{repo}", f"git@github.com:{repo}.git"]

    not_accessible_urls = []

    for repo_url in repo_urls:
        if not __check_ref_exists_for_url__(repo_url, ref):
            not_accessible_urls.append(repo_url)
            continue

        return repo_url

    raise RuntimeError(f"Repo: [yellow]{repo}[/yellow] with ref '{ref}' doesn't exists or not accessible. Tried urls [blue]{ ' '.join(not_accessible_urls) }[/blue]")

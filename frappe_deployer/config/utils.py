from frappe_manager.logger.log import richprint
import git
from git.exc import GitCommandError
from typing import Optional

def is_ref_commit(ref: Optional[str]) -> bool:
    if ref is None:
        return False
    return len(ref) == 40 and all(c in '0123456789abcdef' for c in ref.lower())

def __check_ref_exists_for_url__(repo_url: str, ref: Optional[str] = None) -> bool:
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

def get_repo_url(repo:str, ref: Optional[str] = None, token: Optional[str] = None) -> str:

    url = f"https://github.com/{repo}"

    repo_urls = [(url,"https")]

    if token:
        repo_urls += [(f"https://{token}:x-oauth-basic@github.com/{repo}","token")]

    repo_urls += [(f"git@github.com:{repo}.git","ssh")]

    not_accessible_urls = []

    for repo_url, auth_method in repo_urls:
        if not __check_ref_exists_for_url__(repo_url, ref):
            not_accessible_urls.append(auth_method)
            continue

        print_string = f"Repo Accessible: [green]{repo}[/green]"
        print_string += f" Ref: '{ref}'" if ref else ''
        print_string += f" Auth Method: '{auth_method}'"
        print_string += f" Url: [blue]{url}[/blue]"

        richprint.print(print_string)

        return repo_url

    raise RuntimeError(f"Repo Inaccessible: [yellow]{repo}[/yellow] Ref: '{ref}'. Tried auth methods: [blue]{ ' '.join(auth_method for auth_method in not_accessible_urls) }[/blue]")

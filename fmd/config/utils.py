import os as _os

try:
    from frappe_manager.output_manager import RichOutputHandler as _RichOutputHandler

    richprint = _RichOutputHandler()
    if _os.environ.get("CI", "").lower() == "true":
        richprint.set_interactive_mode(non_interactive_flag=True)
except Exception:

    def richprint(*args, **kwargs):
        print(*args)


try:
    import git
    from git.exc import GitCommandError
except Exception:

    class _GitRemoteStub:
        def ls_remote(self, *args, **kwargs):
            return ""

    class _GitCmdStub:
        Git = _GitRemoteStub

    class _GitModuleStub:
        cmd = _GitCmdStub()

    git = _GitModuleStub()

    class GitCommandError(Exception):
        pass


from typing import Optional


def is_ref_commit(ref: Optional[str]) -> bool:
    if ref is None:
        return False
    return len(ref) == 40 and all(c in "0123456789abcdef" for c in ref.lower())


def __check_ref_exists_for_url__(repo_url: str, ref: Optional[str] = None) -> bool:
    try:
        remote_refs = git.cmd.Git().ls_remote(repo_url)
        refs = [line.split()[1] for line in remote_refs.splitlines()]

        if ref is None:
            return True

        if f"refs/heads/{ref}" in refs or f"refs/tags/{ref}" in refs or is_ref_commit(ref):
            return True

        return False

    except GitCommandError:
        return False


def get_repo_url(repo: str, ref: Optional[str] = None, token: Optional[str] = None) -> str:
    url = f"https://github.com/{repo}"

    # Without a token, SSH is the only method that can reach a private repo,
    # so trying it before anonymous HTTPS avoids a guaranteed failed attempt
    # per private repo on developer machines. The SSH probe is bounded and
    # non-interactive (see GIT_SSH_COMMAND in fmd/config/app.py), so hosts
    # without a usable key fall through to HTTPS quickly.
    #
    # With a token, anonymous HTTPS stays first on purpose: the chosen URL is
    # what we clone from and is retained as the remote (AppConfig.remove_remote
    # defaults to False), so public repos must not end up with the token
    # embedded in .git/config.
    ssh_url = (f"git@github.com:{repo}.git", "ssh")
    https_url = (url, "https")

    if token:
        repo_urls = [https_url, (f"https://{token}@github.com/{repo}", "token"), ssh_url]
    else:
        repo_urls = [ssh_url, https_url]

    not_accessible_urls = []

    for repo_url, auth_method in repo_urls:
        if not __check_ref_exists_for_url__(repo_url, ref):
            not_accessible_urls.append(auth_method)
            continue

        print_string = f"Repo Accessible: [green]{repo}[/green]"
        print_string += f" Ref: '{ref}'" if ref else ""
        print_string += f" Auth Method: '{auth_method}'"
        print_string += f" Url: [blue]{url}[/blue]"

        richprint.print(print_string)

        return repo_url

    raise RuntimeError(
        f"Repo Inaccessible: [yellow]{repo}[/yellow] Ref: '{ref}'. "
        f"Tried auth methods: [blue]{' '.join(auth_method for auth_method in not_accessible_urls)}[/blue]"
    )

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import fmd.config.utils as utils
from fmd.config.utils import get_repo_url

# importing app applies the GIT_SSH_COMMAND / GIT_TERMINAL_PROMPT defaults
import fmd.config.app  # noqa: F401

REPO = "rtCamp/private-app"
TOKEN = "ghp_dummytoken"

PASS = []
FAIL = []


def check(label, got, expected):
    if got == expected:
        PASS.append(label)
        print(f"  PASS  {label}")
    else:
        FAIL.append(label)
        print(f"  FAIL  {label}  ->  expected {expected!r}, got {got!r}")


class Probes:
    """Records probe order and answers accessibility from a fixed set."""

    def __init__(self, accessible):
        self.accessible = accessible
        self.order = []

    def __call__(self, repo_url, ref=None):
        if repo_url.startswith("git@"):
            method = "ssh"
        elif "@github.com" in repo_url:
            method = "token"
        else:
            method = "https"
        self.order.append(method)
        return method in self.accessible


def run(accessible, token=None):
    probes = Probes(accessible)
    original = utils.__check_ref_exists_for_url__
    utils.__check_ref_exists_for_url__ = probes
    try:
        try:
            url = get_repo_url(REPO, None, token)
        except RuntimeError:
            url = None
    finally:
        utils.__check_ref_exists_for_url__ = original
    return probes.order, url


# -- no token: SSH is probed before anonymous HTTPS ---------------------------
print("\n-- no token --")

order, url = run({"ssh"})
check("no token, private repo: ssh probed first", order[0], "ssh")
check("no token, private repo: no wasted https probe", order, ["ssh"])
check("no token, private repo: clones over ssh", url, f"git@github.com:{REPO}.git")

order, url = run({"https"})
check("no token, no ssh key: falls back to https", url, f"https://github.com/{REPO}")
check("no token, no ssh key: ssh tried before https", order, ["ssh", "https"])

order, url = run(set())
check("no token, nothing reachable: raises", url, None)


# -- token: anonymous HTTPS stays ahead of the token URL ----------------------
print("\n-- with token --")

order, url = run({"https", "token", "ssh"}, token=TOKEN)
check("token, public repo: anonymous https wins", url, f"https://github.com/{REPO}")
check("token, public repo: token never probed", "token" in order, False)
check("token, public repo: token absent from clone url", TOKEN in (url or ""), False)

order, url = run({"token", "ssh"}, token=TOKEN)
check("token, private repo: token url used", url, f"https://{TOKEN}@github.com/{REPO}")
check("token, private repo: https probed first", order[0], "https")

order, url = run({"ssh"}, token=TOKEN)
check("token, token rejected: falls through to ssh", url, f"git@github.com:{REPO}.git")
check("token, token rejected: probe order", order, ["https", "token", "ssh"])


# -- the ssh probe must be bounded and non-interactive ------------------------
print("\n-- ssh probe hardening --")

ssh_command = os.environ.get("GIT_SSH_COMMAND", "")
check("GIT_TERMINAL_PROMPT disabled", os.environ.get("GIT_TERMINAL_PROMPT"), "0")
check("ssh probe is non-interactive", "BatchMode=yes" in ssh_command, True)
check("ssh probe has a connect timeout", "ConnectTimeout=" in ssh_command, True)
check("ssh probe does not retry", "ConnectionAttempts=1" in ssh_command, True)


# -- summary ------------------------------------------------------------------
print(f"\n{'=' * 54}")
print(f"  {len(PASS)} passed  /  {len(FAIL)} failed  /  {len(PASS) + len(FAIL)} total")
if FAIL:
    print("\nFailed:")
    for f in FAIL:
        print(f"  - {f}")
    sys.exit(1)

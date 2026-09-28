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

check("GIT_TERMINAL_PROMPT disabled", os.environ.get("GIT_TERMINAL_PROMPT"), "0")


def probe_command(git_ssh_command):
    previous = os.environ.get("GIT_SSH_COMMAND")
    if git_ssh_command is None:
        os.environ.pop("GIT_SSH_COMMAND", None)
    else:
        os.environ["GIT_SSH_COMMAND"] = git_ssh_command
    try:
        return utils.__probe_ssh_command__()
    finally:
        if previous is None:
            os.environ.pop("GIT_SSH_COMMAND", None)
        else:
            os.environ["GIT_SSH_COMMAND"] = previous


for label, configured in [
    ("default", None),
    ("project default", "ssh -o StrictHostKeyChecking=accept-new"),
    ("custom env", "ssh -i /home/deploy/.ssh/id_deploy"),
    ("empty env", ""),
]:
    command = probe_command(configured)
    check(f"{label}: probe is non-interactive", "BatchMode=yes" in command, True)
    check(f"{label}: probe has a connect timeout", "ConnectTimeout=5" in command, True)
    check(f"{label}: probe does not retry", "ConnectionAttempts=1" in command, True)

# a custom ssh command must survive, only the probe guarantees are added
command = probe_command("ssh -i /home/deploy/.ssh/id_deploy")
check("custom env: custom options preserved", "-i /home/deploy/.ssh/id_deploy" in command, True)

# an explicit operator timeout must not be silently overridden
command = probe_command("ssh -o ConnectTimeout=30")
check("explicit timeout respected", "ConnectTimeout=5" in command, False)
check("explicit timeout still bounded", "ConnectTimeout=30" in command, True)

# an environment that disables the guarantees must not win: ssh keeps the first
# value for a repeated -o, so the forced options have to come first
command = probe_command("ssh -o BatchMode=no -o ConnectionAttempts=9")
options = [part for part in command.split() if "=" in part]
check("hostile env: BatchMode forced on", options.index("BatchMode=yes") < options.index("BatchMode=no"), True)
check(
    "hostile env: ConnectionAttempts forced down",
    options.index("ConnectionAttempts=1") < options.index("ConnectionAttempts=9"),
    True,
)
check("hostile env: still bounded", "ConnectTimeout=5" in command, True)

# the forced options must precede user options in every case
command = probe_command("ssh -o BatchMode=no")
check("forced options come first", command.split().index("BatchMode=yes") < command.split().index("BatchMode=no"), True)

# the probe applies its command without mutating the ambient environment
os.environ["GIT_SSH_COMMAND"] = "ssh -o StrictHostKeyChecking=accept-new"
utils.__probe_ssh_command__()
check(
    "probe does not mutate GIT_SSH_COMMAND",
    os.environ["GIT_SSH_COMMAND"],
    "ssh -o StrictHostKeyChecking=accept-new",
)


# -- summary ------------------------------------------------------------------
print(f"\n{'=' * 54}")
print(f"  {len(PASS)} passed  /  {len(FAIL)} failed  /  {len(PASS) + len(FAIL)} total")
if FAIL:
    print("\nFailed:")
    for f in FAIL:
        print(f"  - {f}")
    sys.exit(1)

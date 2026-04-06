import shlex
import subprocess
from typing import Optional


class SSHClient:
    def __init__(self, host: str, user: str, port: int = 22) -> None:
        self.host = host
        self.user = user
        self.port = port

    def _base_cmd(self) -> list[str]:
        return [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-p",
            str(self.port),
            f"{self.user}@{self.host}",
        ]

    def run(self, command: str, workdir: Optional[str] = None, capture: bool = True) -> str:
        remote_cmd = f"cd {shlex.quote(workdir)} && {command}" if workdir else command
        result = subprocess.run(
            self._base_cmd() + [remote_cmd],
            capture_output=capture,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"SSH command failed (exit {result.returncode}): {command}\n{result.stderr}")
        return result.stdout if capture else ""

    def run_list(self, command: list[str], workdir: Optional[str] = None, capture: bool = True) -> str:
        return self.run(shlex.join(command), workdir=workdir, capture=capture)

    def rsync(self, local_src: str, remote_dest: str, options: list[str] = []) -> None:
        ssh_opt = f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {self.port}"
        cmd = (
            ["rsync", "-az", "--delete", "-e", ssh_opt]
            + options
            + [
                local_src,
                f"{self.user}@{self.host}:{remote_dest}",
            ]
        )
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"rsync failed (exit {result.returncode}):\n{result.stderr}")

    def is_symlink(self, remote_path: str) -> bool:
        try:
            self.run(f"test -L {shlex.quote(remote_path)}")
            return True
        except RuntimeError:
            return False

    def path_exists(self, remote_path: str) -> bool:
        try:
            self.run(f"test -e {shlex.quote(remote_path)}")
            return True
        except RuntimeError:
            return False

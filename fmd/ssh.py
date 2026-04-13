import select
import shlex
import subprocess
import time
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

    def _log_command(self, command: str, command_type: str = "SSH") -> None:
        try:
            from fmd.logger import get_logger

            get_logger().debug(f"COMMAND [{command_type}] [{self.user}@{self.host}]: {command}")
        except Exception:
            pass

    def _stream_output(self, proc: "subprocess.Popen[bytes]") -> tuple[str, str]:
        try:
            from fmd.logger import get_logger

            logger = get_logger()
        except Exception:
            logger = None

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        streams = {proc.stdout: ("stdout", stdout_lines), proc.stderr: ("stderr", stderr_lines)}
        open_streams = set(streams)

        while open_streams:
            readable, _, _ = select.select(list(open_streams), [], [])
            for fd in readable:
                line = fd.readline()
                if not line:
                    open_streams.discard(fd)
                    continue
                decoded = line.decode(errors="replace").rstrip()
                tag, store = streams[fd]
                store.append(decoded)
                print(decoded)
                if logger and decoded:
                    logger.debug(f"{'OUTPUT' if tag == 'stdout' else 'STDERR'}: {decoded}")

        proc.wait()
        return "\n".join(stdout_lines), "\n".join(stderr_lines)

    def _log_timing(self, start: float, command: str, label: str) -> None:
        from fmd.runner.base import _DIM, _RESET

        elapsed = time.time() - start
        print(f"{_DIM}$ [{label}] {command}  ({elapsed:.2f}s){_RESET}")
        try:
            from fmd.logger import get_logger

            get_logger().debug(f"TIMING: {elapsed:.2f}s for [{label}]: {command}")
        except Exception:
            pass

    def run(self, command: str, workdir: Optional[str] = None, capture: bool = True) -> str:
        remote_cmd = f"cd {shlex.quote(workdir)} && {command}" if workdir else command
        self._log_command(remote_cmd)
        start = time.time()

        proc = subprocess.Popen(
            self._base_cmd() + [remote_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout_str, stderr_str = self._stream_output(proc)

        self._log_timing(start, remote_cmd, "ssh")

        if proc.returncode != 0:
            stderr_detail = stderr_str.strip()
            detail = f"\n{stderr_detail}" if stderr_detail else ""
            raise RuntimeError(f"SSH command failed (exit {proc.returncode}): {command}{detail}")
        return stdout_str if capture else ""

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
        label = f"rsync {local_src} -> {self.user}@{self.host}:{remote_dest}"
        self._log_command(label, "RSYNC")
        start = time.time()

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr_str = self._stream_output(proc)

        self._log_timing(start, f"{self.user}@{self.host}:{remote_dest}", "rsync")

        if proc.returncode != 0:
            raise RuntimeError(f"rsync failed (exit {proc.returncode}):\n{stderr_str}")

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

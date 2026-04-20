import subprocess
from pathlib import Path

from fmd.config.config import Config
from fmd.managers.release import ReleaseManager
from fmd.runner.docker import DockerRunner
from fmd.runner.host import HostRunner
from fmd.ssh import SSHClient


class ShipManager:
    def __init__(
        self, config: Config, release_runner: DockerRunner, exec_runner: DockerRunner, host_runner: HostRunner, printer
    ) -> None:
        if not config.ship:
            raise RuntimeError("No [ship] section in config — cannot use ShipManager.")

        self.config = config
        self.printer = printer
        self.ssh = SSHClient(config.ship.host, config.ship.ssh_user, config.ship.ssh_port)

        docker_host = f"ssh://{config.ship.ssh_user}@{config.ship.host}"

        platform = self._detect_platform()

        if platform and not config.release.platform:
            config.release.platform = platform
            release_runner.platform = platform

        self.printer.print(f"[dim]platform wired → release_runner.platform={release_runner.platform!r}[/dim]")

        self.remote_image_runner = DockerRunner(
            mode="image",
            config=config,
            verbose=config.verbose,
            printer=printer,
            docker_host=docker_host,
            platform=platform,
        )

        self.release_manager = ReleaseManager(
            config,
            release_runner,
            exec_runner,
            host_runner,
            printer,
        )

    def _detect_platform(self) -> str | None:
        if self.config.release.platform:
            self.printer.print(f"[dim]platform: using config override → {self.config.release.platform}[/dim]")
            return self.config.release.platform

        try:
            arch = self.ssh.run("uname -m", capture=True).strip()
            self.printer.print(f"[dim]platform: remote uname -m → {arch!r}[/dim]")
            if arch == "x86_64":
                self.printer.print("[dim]platform: detected linux/amd64[/dim]")
                return "linux/amd64"
            elif arch == "aarch64":
                self.printer.print("[dim]platform: detected linux/arm64[/dim]")
                return "linux/arm64"
            else:
                self.printer.warning(f"Unknown remote architecture '{arch}', Docker will use default platform")
                return None
        except Exception as e:
            self.printer.warning(f"Failed to detect remote architecture: {e}")
            return None

    def _pull_image_locally(self, image: str) -> None:
        import importlib
        import time

        from fmd.logger import get_logger
        from fmd.runner.base import _DIM, _RESET

        _dc = importlib.import_module("frappe_manager.docker.docker_client")
        _DockerClient = getattr(_dc, "DockerClient")

        cmd = ["docker", "pull", image]
        if self.config.release.platform:
            cmd += ["--platform", self.config.release.platform]

        try:
            get_logger().debug(f"COMMAND [pull]: {' '.join(cmd)}")
        except Exception:
            pass

        self.printer.change_head(f"Pulling image {image} locally")
        start = time.time()
        stream = _DockerClient().pull(
            container_name=image,
            platform=self.config.release.platform or None,
            stream=True,
        )
        self.printer.live_lines(stream, lines=6, log_prefix="pull")
        elapsed = time.time() - start

        print(f"{_DIM}$ [pull] {' '.join(cmd)}  ({elapsed:.2f}s){_RESET}")
        try:
            get_logger().debug(f"TIMING: {elapsed:.2f}s for command: {' '.join(cmd)}")
        except Exception:
            pass

        self.printer.print(f"Image [blue]{image}[/blue] ready")

    def _rsync_release(self, release_name: str) -> None:
        local_src = str(self.config.workspace_root / "workspace" / release_name) + "/"
        remote_dest = f"{self.config.ship.remote_path}/workspace/{release_name}/"
        self.printer.change_head(f"Syncing release {release_name} to remote")
        self.ssh.rsync(local_src, remote_dest, self.config.ship.rsync_options)
        self.printer.print("Release synced")

    def _rsync_config(self, config_path: Path) -> None:
        self.printer.change_head("Syncing config to remote")
        self.ssh.rsync(str(config_path), f"{self.config.ship.remote_path}/")
        self.printer.print("Config synced")

    def _ensure_uv_on_remote(self) -> None:
        self.printer.change_head("Ensuring uv is available on remote")
        try:
            self.ssh.run("command -v uv || command -v ~/.local/bin/uv")
            self.printer.print("uv already installed")
        except RuntimeError:
            self.printer.change_head("Installing uv on remote")
            self.ssh.run("curl -LsSf https://astral.sh/uv/install.sh | sh")
            self.printer.print("uv installed")

    def _get_uvx_path(self) -> str:
        try:
            return self.ssh.run("command -v uvx").strip()
        except RuntimeError:
            return f"/home/{self.config.ship.ssh_user}/.local/bin/uvx"

    def _resolve_fmd_source(self) -> str:
        if self.config.ship.fmd_source:
            return self.config.ship.fmd_source

        import os
        import subprocess
        import typer

        fmd_action_ref = os.environ.get("FMD_ACTION_REF", "")
        if fmd_action_ref:
            typer.echo(f"[DEBUG] Using FMD_ACTION_REF: {fmd_action_ref}")
            return f"git+https://github.com/rtcamp/frappe-deployer.git@{fmd_action_ref}"

        local_fmd_root = Path(__file__).parent.parent.parent
        local_git_dir = local_fmd_root / ".git"

        typer.echo(f"[DEBUG] local_fmd_root: {local_fmd_root}")
        typer.echo(f"[DEBUG] .git exists: {local_git_dir.exists()}")

        if local_git_dir.exists():
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=local_fmd_root, capture_output=True, text=True
            )
            typer.echo(f"[DEBUG] git rev-parse --abbrev-ref HEAD: {result.stdout.strip()} (returncode={result.returncode})")
            
            if result.returncode == 0 and result.stdout.strip() not in ("HEAD", ""):
                branch = result.stdout.strip()
                fmd_source = f"git+https://github.com/rtcamp/frappe-deployer.git@{branch}"
                typer.echo(f"[DEBUG] Using branch: {fmd_source}")
                return fmd_source

            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=local_fmd_root, capture_output=True, text=True
            )
            typer.echo(f"[DEBUG] git rev-parse HEAD: {result.stdout.strip()} (returncode={result.returncode})")
            
            if result.returncode == 0:
                commit_sha = result.stdout.strip()
                fmd_source = f"git+https://github.com/rtcamp/frappe-deployer.git@{commit_sha}"
                typer.echo(f"[DEBUG] Using commit SHA: {fmd_source}")
                return fmd_source

        default_source = "git+https://github.com/rtcamp/frappe-deployer.git@main"
        typer.echo(f"[DEBUG] Falling back to default: {default_source}")
        return default_source

    def _rsync_fmd_source_if_local(self, fmd_source: str) -> str:
        if not fmd_source.startswith("git+file://"):
            return fmd_source

        local_fmd_root = Path(__file__).parent.parent.parent
        remote_fmd_path = "~/.fmd-source"

        self.printer.change_head("Syncing local fmd source to remote")
        self.ssh.rsync(
            str(local_fmd_root) + "/",
            f"{remote_fmd_path}/",
            [
                "--exclude=.venv",
                "--exclude=__pycache__",
                "--exclude=*.pyc",
                "--exclude=.pytest_cache",
                "--exclude=*.egg-info",
            ],
        )
        self.printer.print("FMD source synced")

        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=local_fmd_root, capture_output=True, text=True
        )
        branch = result.stdout.strip() if result.returncode == 0 else "main"

        return f"git+file://{remote_fmd_path.replace('~', '/home/' + self.config.ship.ssh_user)}@{branch}"

    def _remote_fmd_command(self, args: list[str], capture: bool = False) -> str:
        uvx_path = self._get_uvx_path()
        fmd_source = self._resolve_fmd_source()
        fmd_source = self._rsync_fmd_source_if_local(fmd_source)

        cmd = [uvx_path, "--from", fmd_source, "fmd"] + args
        return self.ssh.run_list(cmd, capture=capture)

    def _remote_configure_if_needed(self, remote_config_path: str) -> None:
        remote_bench = f"{self.config.ship.remote_path}/workspace/frappe-bench"
        if not self.ssh.is_symlink(remote_bench):
            self.printer.change_head("Remote bench not configured — running fmd release configure")
            self._remote_fmd_command(
                ["release", "configure", "--config", remote_config_path, "--no-backups"], capture=False
            )
            self.printer.print("Remote configure complete")

    def _remote_switch(self, release_name: str, remote_config_path: str) -> None:
        self.printer.change_head(f"Switching remote to release {release_name}")
        self._remote_fmd_command(
            ["release", "switch", "--config", remote_config_path, self.config.bench_name, release_name], capture=False
        )
        self.printer.print(f"Remote switched to [blue]{release_name}[/blue]")

    def deploy(self, config_path: Path, existing_release: str | None = None, skip_rsync: bool = False) -> None:
        if existing_release:
            local_release_path = self.config.workspace_root / "workspace" / existing_release
            if not local_release_path.exists() and not skip_rsync:
                raise RuntimeError(f"Existing release {existing_release} not found at {local_release_path}")
            release_name = existing_release
            self.printer.print(f"Using existing release [blue]{release_name}[/blue]")
        else:
            image = self.remote_image_runner._resolve_image()
            self._pull_image_locally(image)

            self.config.release.runner_image = image

            release_name = self.release_manager.create()
            self.printer.print(f"Release [blue]{release_name}[/blue] created locally")

        if not skip_rsync:
            self._rsync_release(release_name)
        else:
            self.printer.print("Skipping release rsync (--skip-rsync enabled)")

        self._rsync_config(config_path)

        remote_config_path = f"{self.config.ship.remote_path}/{config_path.name}"

        self._ensure_uv_on_remote()
        self._remote_configure_if_needed(remote_config_path)
        self._remote_switch(release_name, remote_config_path)

        self.printer.print(f"Ship deploy complete — remote is on [blue]{release_name}[/blue]")

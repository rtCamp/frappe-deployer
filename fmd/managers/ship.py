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

        self.remote_image_runner = DockerRunner(
            mode="image",
            config=config,
            verbose=config.verbose,
            printer=printer,
            docker_host=docker_host,
        )

        self.release_manager = ReleaseManager(
            config,
            release_runner,
            exec_runner,
            host_runner,
            printer,
        )

    def _pull_image_locally(self, image: str) -> None:
        self.printer.change_head(f"Pulling image {image} locally")
        result = subprocess.run(["docker", "pull", image], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"docker pull failed:\n{result.stderr}")
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

        local_fmd_root = Path(__file__).parent.parent.parent
        local_git_dir = local_fmd_root / ".git"

        if local_git_dir.exists():
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=local_fmd_root, capture_output=True, text=True
            )
            branch = result.stdout.strip() if result.returncode == 0 else "main"
            return f"git+https://github.com/rtcamp/frappe-deployer.git@{branch}"

        return "git+https://github.com/rtcamp/frappe-deployer.git@main"

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
            self._remote_fmd_command(["release", "configure", "--config", remote_config_path], capture=False)
            self.printer.print("Remote configure complete")

    def _remote_switch(self, release_name: str, remote_config_path: str) -> None:
        self.printer.change_head(f"Switching remote to release {release_name}")
        self._remote_fmd_command(["release", "switch", "--config", remote_config_path, release_name], capture=False)
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
            self._rsync_config(config_path)
        else:
            self.printer.print("Skipping rsync (--skip-rsync enabled)")

        remote_config_path = f"{self.config.ship.remote_path}/{config_path.name}"

        self._ensure_uv_on_remote()
        self._remote_configure_if_needed(remote_config_path)
        self._remote_switch(release_name, remote_config_path)

        self.printer.print(f"Ship deploy complete — remote is on [blue]{release_name}[/blue]")

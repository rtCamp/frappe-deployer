import subprocess
from pathlib import Path

from fmd.config.config import Config
from fmd.managers.release import ReleaseManager
from fmd.runner.docker import DockerRunner
from fmd.runner.host import HostRunner
from fmd.ssh import SSHClient


class ShipManager:
    def __init__(self, config: Config, printer) -> None:
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
        self.local_image_runner = DockerRunner(
            mode="image",
            config=config,
            verbose=config.verbose,
            printer=printer,
            docker_host=None,
        )
        self.host_runner = HostRunner(verbose=config.verbose, printer=printer)

        self.release_manager = ReleaseManager(
            config,
            self.local_image_runner,
            None,
            self.host_runner,
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

    def _ensure_fmd_on_remote(self) -> None:
        self.printer.change_head("Ensuring fmd is available on remote")
        try:
            self.ssh.run("command -v fmd")
        except RuntimeError:
            self.ssh.run("pip install frappe-deployer --quiet || pip install fmd --quiet")
        self.printer.print("fmd available on remote")

    def _remote_configure_if_needed(self, remote_config_path: str) -> None:
        remote_bench = f"{self.config.ship.remote_path}/workspace/frappe-bench"
        if not self.ssh.is_symlink(remote_bench):
            self.printer.change_head("Remote bench not configured — running fmd release configure")
            self.ssh.run_list(["fmd", "release", "configure", "--config", remote_config_path], capture=False)
            self.printer.print("Remote configure complete")

    def _remote_switch(self, release_name: str, remote_config_path: str) -> None:
        self.printer.change_head(f"Switching remote to release {release_name}")
        self.ssh.run_list(["fmd", "release", "switch", "--config", remote_config_path, release_name], capture=False)
        self.printer.print(f"Remote switched to [blue]{release_name}[/blue]")

    def deploy(self, config_path: Path) -> None:
        image = self.remote_image_runner._resolve_image()
        self._pull_image_locally(image)

        self.config.release.runner_image = image

        release_name = self.release_manager.create()
        self.printer.print(f"Release [blue]{release_name}[/blue] created locally")

        self._rsync_release(release_name)

        self._rsync_config(config_path)
        remote_config_path = f"{self.config.ship.remote_path}/{config_path.name}"

        self._ensure_fmd_on_remote()
        self._remote_configure_if_needed(remote_config_path)
        self._remote_switch(release_name, remote_config_path)

        self.printer.print(f"Ship deploy complete — remote is on [blue]{release_name}[/blue]")

import json
import shutil
import socket
from pathlib import Path
from typing import Any, Optional

import frappe_manager
import requests

try:
    from frappe_manager.docker import ComposeFile as _ComposeFile
except ImportError:
    _ComposeFile = None

from fmd.config.config import Config
from fmd.consts import DATA_DIR_NAME
from fmd.helpers import get_relative_path
from fmd.release_directory import BenchDirectory
from fmd.ssh import SSHClient


def _get_current_ip() -> str:
    return requests.get("https://api.ipify.org").text


def _find_available_port(start_port: int = 11000) -> Optional[int]:
    used_ports: set[int] = set()
    benches_dir = frappe_manager.CLI_BENCHES_DIRECTORY
    if benches_dir.exists():
        for bench_dir in benches_dir.iterdir():
            if not bench_dir.is_dir():
                continue
            compose_path = bench_dir / "docker-compose.yml"
            if not compose_path.exists():
                continue
            try:
                cf = _ComposeFile(compose_path) if _ComposeFile else None
                if cf is None:
                    continue
                redis_queue = cf.yml.get("services", {}).get("redis-queue", {})
                for mapping in redis_queue.get("ports", []):
                    if not isinstance(mapping, str):
                        continue
                    parts = mapping.split(":")
                    raw = parts[1] if len(parts) == 3 else parts[0]
                    raw = raw.removeprefix("0.0.0.0:")
                    try:
                        used_ports.add(int(raw))
                    except ValueError:
                        pass
            except Exception:
                continue

    port = start_port
    while port < 65535:
        if port not in used_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(("", port))
                sock.close()
                return port
            except OSError:
                port += 1
            finally:
                sock.close()
        else:
            port += 1
    return None


class RemoteWorkerManager:
    def __init__(self, config: Config, printer: Any) -> None:
        if not config.remote_worker:
            raise RuntimeError("remote_worker config section is required")
        rw = config.remote_worker
        self.config = config
        self.printer = printer
        self.rw = rw
        self.ssh = SSHClient(rw.server_ip, rw.ssh_user, rw.ssh_port)
        self.current = BenchDirectory(config.bench_path)
        self.data = BenchDirectory(config.deploy_dir_path / DATA_DIR_NAME)
        self._remote_base = Path(rw.fm_benches_path) / config.site_name / "workspace"

    def _fm_bench(self):
        from frappe_manager.docker import ComposeFile
        from frappe_manager.compose_project.compose_project import ComposeProject

        bench_path = frappe_manager.CLI_BENCHES_DIRECTORY / self.config.site_name

        class _Bench:
            def __init__(self, path):
                self.path = path
                self.compose_project = ComposeProject(ComposeFile(path / "docker-compose.yml"))

        return _Bench(bench_path)

    def _fm_services_manager(self):
        from frappe_manager import CLI_SERVICES_DIRECTORY
        from frappe_manager.docker import ComposeFile
        from frappe_manager.compose_project.compose_project import ComposeProject

        class _Services:
            def __init__(self, services_path):
                self.compose_project = ComposeProject(ComposeFile(services_path / "docker-compose.yml"))

        return _Services(CLI_SERVICES_DIRECTORY)

    def _is_enabled(self) -> bool:
        services = self._fm_services_manager()
        global_db = services.compose_project.compose_file_manager.yml.get("services", {}).get("global-db", {})
        if not global_db.get("ports"):
            return False
        if not any("3306:3306" in p for p in global_db["ports"]):
            return False
        bench_path = frappe_manager.CLI_BENCHES_DIRECTORY / self.config.site_name
        if not bench_path.exists():
            return False
        bench = self._fm_bench()
        redis = bench.compose_project.compose_file_manager.yml.get("services", {}).get("redis-queue", {})
        return bool(redis.get("ports"))

    def _get_redis_queue_url(self) -> str:
        bench = self._fm_bench()
        redis_config = bench.compose_project.compose_file_manager.yml["services"]["redis-queue"]
        port_mapping = redis_config["ports"][0]
        exposed_port = port_mapping.split(":")[1]
        return f"redis://{_get_current_ip()}:{exposed_port}"

    def enable(self, force: bool = False) -> None:
        if self._is_enabled():
            self.printer.print("Remote worker already enabled.")
            return

        queue_port = _find_available_port()
        if not queue_port:
            raise RuntimeError("No available ports found for redis-queue")

        services = self._fm_services_manager()
        services.compose_project.compose_file_manager.yml["services"]["global-db"]["ports"] = ["0.0.0.0:3306:3306"]
        services.compose_project.compose_file_manager.yml["services"]["global-db"].pop("expose", None)
        services.compose_project.compose_file_manager.write_to_file()
        services.compose_project.start_service(services=["global-db"])

        bench = self._fm_bench()
        bench.compose_project.compose_file_manager.yml["services"]["redis-queue"]["ports"] = [
            f"0.0.0.0:{queue_port}:6379"
        ]
        bench.compose_project.compose_file_manager.yml["services"]["redis-queue"].pop("expose", None)
        bench.compose_project.compose_file_manager.write_to_file()
        bench.compose_project.start_service(services=["redis-queue"])

        self._create_worker_site_config(force=force)

    def _create_worker_site_config(self, force: bool = False) -> None:
        self.printer.change_head("Creating worker site config")
        source_common = self.data.sites / "common_site_config.json"
        target_common = self.data.sites / "common_site_config.workers.json"
        source_site = self.data.sites / self.config.site_name / "site_config.json"
        target_site = self.data.sites / self.config.site_name / "site_config.workers.json"

        if not force and target_common.exists() and target_site.exists():
            self.printer.print("Worker configs already exist. Skipping creation.")
            return

        shutil.copy2(source_common, target_common)
        shutil.copy2(source_site, target_site)

        with open(target_common) as f:
            common_config = json.load(f)
        common_config["redis_queue"] = self._get_redis_queue_url()
        with open(target_common, "w") as f:
            json.dump(common_config, f, indent=4)

        with open(target_site) as f:
            site_config = json.load(f)
        site_config["db_host"] = _get_current_ip()
        with open(target_site, "w") as f:
            json.dump(site_config, f, indent=4)

        self.printer.print(f"Created worker configs with Redis queue URL: {common_config['redis_queue']}")

    def sync(self) -> None:
        self._stop_all_compose_services()
        self._rsync_workspace()
        self._link_worker_configs()
        self._only_start_workers_compose_services()

    def _stop_all_compose_services(self) -> None:
        self.printer.change_head("Stop all remote-worker services")
        self.ssh.run_list(
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.yml",
                "-f",
                "docker-compose.workers.yml",
                "down",
                "--timeout",
                "10",
            ],
            workdir=str(self._remote_base),
        )
        self.printer.print("Stopped all remote-worker services")

    def _rsync_workspace(self) -> None:
        site_name = self.config.site_name
        target_path = f"{self.rw.ssh_user}@{self.rw.server_ip}:{self.rw.fm_benches_path}/{site_name}/workspace"

        rsync_patterns = [
            "--exclude=**/.git/***",
            "--exclude=**/node_modules/***",
            "--exclude=**/__pycache__/***",
            "--exclude=**/.pytest_cache/***",
            "--exclude=**/.cache/***",
            "--exclude=*.pyc",
            "--exclude=*.pyo",
            "--exclude=*.pyd",
            "--exclude=.DS_Store",
            "--exclude=*.log",
            "--exclude=*.swp",
            "--exclude=*.swo",
            "--exclude=*.sql",
        ]

        ssh_opt = f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {self.rw.ssh_port}"

        workspace_src = frappe_manager.CLI_BENCHES_DIRECTORY / site_name / "workspace"

        rsync_dirs = [
            {"src": self.current.path, "dest": None, "excludes": [], "trailing_slash": True},
            {"src": self.current.path.parent / ".pyenv", "dest": None, "excludes": [], "trailing_slash": True},
            {"src": self.current.path.parent / ".nvm", "dest": None, "excludes": [], "trailing_slash": True},
            {"src": self.current.path.parent / ".oh-my-zsh", "dest": None, "excludes": [], "trailing_slash": True},
            {
                "src": self.data.path,
                "dest": None,
                "excludes": [
                    f"--exclude=sites/{site_name}/public/files/***",
                    f"--exclude=sites/{site_name}/private/***",
                ],
                "trailing_slash": True,
            },
        ]

        for dir_cfg in self.rw.include_dirs or []:
            rsync_dirs.append(
                {
                    "src": self.current.path.parent / dir_cfg,
                    "dest": dir_cfg,
                    "excludes": ["--mkpath"],
                    "trailing_slash": True,
                }
            )
        for file_cfg in self.rw.include_files or []:
            rsync_dirs.append(
                {
                    "src": self.current.path.parent / file_cfg,
                    "dest": file_cfg,
                    "excludes": [],
                    "trailing_slash": False,
                }
            )

        import subprocess

        self.printer.print("Starting rsync files")
        for d in rsync_dirs:
            src = d["src"]
            if not src.exists():
                self.printer.print(f"Skipping: {src.absolute()} (not found)")
                continue
            dest_name = str(d["dest"] if d["dest"] else src.name)
            src_str = str(src) + ("/" if d["trailing_slash"] else "")
            dest_str = str(src) + ("/" if d["trailing_slash"] else "")
            cmd = (
                ["rsync", "-avz", "--delete", "--checksum", "-e", ssh_opt]
                + rsync_patterns
                + d["excludes"]
                + [src_str, f"{target_path}/{dest_name}"]
            )
            self.printer.change_head(f"Syncing: {dest_name}")
            subprocess.run(cmd, check=True)
            self.printer.print(f"Synced {dest_name}")

        self.printer.print("Remote sync completed successfully")

    def _link_worker_configs(self) -> None:
        remote_bench_path = self._remote_base / "frappe-bench"

        new_target = self.current.path.readlink().name
        is_symlink = self.ssh.is_symlink(str(remote_bench_path))
        if is_symlink:
            current_target = self.ssh.run(f"readlink {remote_bench_path}").strip()
            self.ssh.run_list(["unlink", str(remote_bench_path)])
            if current_target != new_target:
                self.ssh.run_list(["mv", current_target, new_target], workdir=str(self._remote_base))
        else:
            self.ssh.run_list(["mv", "frappe-bench", new_target], workdir=str(self._remote_base))

        self.ssh.run_list(["ln", "-sfn", new_target, "frappe-bench"], workdir=str(self._remote_base))
        self.printer.print(f"Linked frappe-bench to {new_target}")

        for rel_dir in [
            f"deployment-data/sites/{self.config.site_name}/private/files",
            f"deployment-data/sites/{self.config.site_name}/public/files",
            "frappe-bench/config/pids",
        ]:
            self.ssh.run_list(["mkdir", "-p", rel_dir], workdir=str(self._remote_base))

        def _link_config(src_data: Path, current_bench_dest: Path, remote_path: Path, label: str) -> None:
            relative = get_relative_path(current_bench_dest, src_data)
            self.ssh.run_list(["ln", "-sf", str(relative), str(remote_path)], workdir=str(remote_bench_path))
            self.printer.print(f"Linked {label} to {relative}")

        _link_config(
            self.data.sites / "common_site_config.workers.json",
            self.current.sites / "common_site_config.json",
            remote_bench_path / "sites" / "common_site_config.json",
            "common_site_config.json",
        )
        _link_config(
            self.data.sites / self.config.site_name / "site_config.workers.json",
            self.current.sites / self.config.site_name / "site_config.json",
            remote_bench_path / "sites" / self.config.site_name / "site_config.json",
            "site_config.json",
        )
        self.printer.print("Successfully linked worker config files")

    def _only_start_workers_compose_services(self) -> None:
        self.printer.change_head("Stopping all services other than workers")
        self.ssh.run_list(["docker", "compose", "-f", "docker-compose.yml", "down"], workdir=str(self._remote_base))
        self.ssh.run_list(
            ["docker", "compose", "-f", "docker-compose.yml", "up", "-d", "schedule"],
            workdir=str(self._remote_base),
        )
        self.printer.change_head("Starting remote-worker services")
        self.ssh.run_list(
            ["docker", "compose", "-f", "docker-compose.workers.yml", "up", "-d"],
            workdir=str(self._remote_base),
        )
        self.ssh.run_list(
            ["docker", "compose", "-f", "docker-compose.workers.yml", "restart"],
            workdir=str(self._remote_base),
        )
        self.printer.print("Started remote-worker services")

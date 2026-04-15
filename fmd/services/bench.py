from pathlib import Path
import json
import shutil
import time
from typing import Any, Callable, Optional

from pydantic import BaseModel

from fmd.release_directory import BenchDirectory
from fmd.helpers import extract_timestamp as _extract_timestamp, get_relative_path, human_readable_time


class BenchService:
    def __init__(self, runner: Any, host_runner: Any, config: Any, printer: Any):
        self.runner = runner
        self.host_runner = host_runner
        self.config = config
        self.printer = printer

    def extract_timestamp(self, dir_name: str) -> int:
        return _extract_timestamp(dir_name)

    def get_script_env(
        self,
        bench_path: Path,
        current: BenchDirectory,
        site_name: str,
        app_name: Optional[str] = None,
    ) -> dict[str, str]:
        env: dict[str, str] = {}

        computed: dict[str, str] = {
            "BENCH_PATH": str(bench_path),
            "WORKSPACE_ROOT": str(self.config.workspace_root) if hasattr(self.config, "workspace_root") else "",
            "APPS": ",".join(d.name for d in current.apps.iterdir() if d.is_dir()),
        }

        if site_name:
            computed["SITE_NAME"] = site_name

        if app_name:
            computed["APP_NAME"] = app_name
            computed["APP_PATH"] = self.runner.app_exec_path(current, app_name)

        env.update(computed)

        for field_name in self.config.__class__.model_fields:
            value = getattr(self.config, field_name, None)
            if value is None:
                continue
            env_key = field_name.upper()
            if isinstance(value, list) and value and isinstance(value[0], BaseModel):
                env[env_key] = json.dumps([item.model_dump() for item in value])
            elif isinstance(value, dict):
                env[env_key] = json.dumps(value)
            elif isinstance(value, Path):
                env[env_key] = str(value)
            elif isinstance(value, bool):
                env[env_key] = str(value).lower()
            elif isinstance(value, BaseModel):
                env[env_key] = json.dumps(value.model_dump())
            else:
                env[env_key] = str(value)

        return env

    def _run_script(
        self,
        script_content: Optional[str],
        bench_directory: BenchDirectory,
        current: BenchDirectory,
        bench_path: Path,
        site_name: str,
        host_run: Callable,
        script_type: str,
        container: bool = False,
        app_name: Optional[str] = None,
        custom_workdir: Optional[str] = None,
    ) -> None:
        self.printer.change_head(f"Running {script_type}")

        script_dir = current.path.parent / "deployment_tmp"
        script_dir.mkdir(parents=True, exist_ok=True)

        script_name = f"temp_script_{int(time.time())}.sh"
        script_path = script_dir / script_name

        try:
            content = script_content or ""
            stripped = content.strip()
            if stripped.startswith(("/", "./", "~/")) or Path(stripped).suffix in (".sh", ".py"):
                candidate = Path(stripped).expanduser()
                if candidate.exists():
                    content = candidate.read_text()

            with open(script_path, "w") as script_file:
                script_file.write("set -e\n")
                script_file.write(content)

            script_path.chmod(0o755)

            if container:
                container_script_path = f"/workspace/deployment_tmp/{script_name}"
                workdir = custom_workdir or "/workspace/deployment_tmp"
            else:
                container_script_path = str(script_path)
                workdir = custom_workdir or str(script_dir)

            script_env = self.get_script_env(bench_path, bench_directory, site_name, app_name)

            output = host_run(
                ["bash", container_script_path],
                bench_directory,
                container=container,
                capture_output=True,
                workdir=workdir,
                env=script_env,
            )

            if output and getattr(output, "combined", None):
                for line in output.combined:
                    if line.strip():
                        self.printer.print(line.strip())
            self.printer.print(f"{script_type} done")

        finally:
            try:
                if script_path.exists():
                    script_path.unlink()
                    if not any(script_dir.iterdir()):
                        script_dir.rmdir()
            except Exception as e:
                self.printer.warning(f"Failed to cleanup temporary script: {e}")

    def clear_assets_json(self, bench_directory: BenchDirectory) -> None:
        common_config_path = bench_directory.common_site_config
        if not common_config_path.exists():
            self.printer.warning("common_site_config.json not found, skipping assets_json clear")
            return

        try:
            config = json.loads(common_config_path.read_text())
            redis_cache_url = config.get("redis_cache")
            if not redis_cache_url:
                self.printer.warning("redis_cache not in common_site_config.json, skipping assets_json clear")
                return
            self.runner.run(
                ["redis-cli", "-u", redis_cache_url, "DEL", "assets_json"], bench_directory, capture_output=False
            )
            self.printer.print("Cleared assets_json from Redis cache")
        except Exception as e:
            self.printer.warning(f"Failed to clear assets_json: {e}")

    def bench_clear_cache(
        self, bench_directory: BenchDirectory, bench_cli: str, site_name: str, website_cache: bool = False
    ):
        clear_cache_command = [bench_cli, "--site", site_name, "clear-cache"]
        clear_website_cache_command = [bench_cli, "--site", site_name, "clear-website-cache"]

        self.printer.change_head(f"Clearing cache{' and website cache' if website_cache else ''}")
        for command in [clear_cache_command, clear_website_cache_command]:
            self.runner.run(command, bench_directory, capture_output=False)
            self.printer.print(f"{' '.join(command)} done")

        self.clear_assets_json(bench_directory)

    def bench_install_all_apps_in_python_env(
        self,
        bench_directory: BenchDirectory,
        apps: list,
        current: BenchDirectory,
        bench_path: Path,
        site_name: str,
        host_run: Callable,
    ):
        self.printer.change_head("Installing all apps in python env using uv")

        python_path = f"{self.runner.workdir_for_bench(bench_directory)}/env/bin/python"
        install_cmd = [
            "uv",
            "pip",
            "install",
            "--python",
            python_path,
            "-U",
            "-e",
        ]
        for app in apps:
            app_path = bench_directory.apps / app.dir_name
            if not app_path.is_dir():
                continue
            if app.host_before_python_install:
                self._run_script(
                    app.host_before_python_install,
                    bench_directory,
                    current,
                    bench_path,
                    site_name,
                    host_run,
                    f"host pre-python-install for {app.dir_name}",
                    app_name=app.dir_name,
                )
            if app.before_python_install:
                self._run_script(
                    app.before_python_install,
                    bench_directory,
                    current,
                    bench_path,
                    site_name,
                    host_run,
                    f"pre-python-install for {app.dir_name}",
                    container=True,
                    app_name=app.dir_name,
                )

            try:
                self.runner.run(install_cmd + [f"apps/{app.dir_name}"], bench_directory, capture_output=False)
            except Exception:
                self.printer.print(f"uv failed for {app.dir_name}, falling back to pip")
                self.runner.run(["pip", "install", "-e", f"apps/{app.dir_name}"], bench_directory, capture_output=False)

            if app.after_python_install:
                self._run_script(
                    app.after_python_install,
                    bench_directory,
                    current,
                    bench_path,
                    site_name,
                    host_run,
                    f"post-python-install for {app.dir_name}",
                    container=True,
                    app_name=app.dir_name,
                )
            if app.host_after_python_install:
                self._run_script(
                    app.host_after_python_install,
                    bench_directory,
                    current,
                    bench_path,
                    site_name,
                    host_run,
                    f"host post-python-install for {app.dir_name}",
                    app_name=app.dir_name,
                )

        self.printer.print("Installed apps in python env")

    def bench_setup_requirements(
        self,
        bench_directory: BenchDirectory,
        apps: list,
        bench_cli: str,
        current: BenchDirectory,
        bench_path: Path,
        site_name: str,
        host_run: Callable,
    ):
        from frappe_manager.site_manager.bench_config import (
            extract_node_version_requirement,
            extract_python_version_requirement,
            parse_node_version_for_runtime,
            parse_python_version_for_runtime,
        )

        frappe_app_path = bench_directory.apps / "frappe"
        if frappe_app_path.exists():
            if not self.config.release.python_version:
                detected = extract_python_version_requirement(frappe_app_path)
                if detected:
                    self.config.release.python_version = parse_python_version_for_runtime(detected)
                    self.printer.print(f"Auto-detected Python version: {self.config.release.python_version}")
            if not self.config.release.node_version:
                detected = extract_node_version_requirement(frappe_app_path)
                if detected:
                    self.config.release.node_version = parse_node_version_for_runtime(detected)
                    self.printer.print(f"Auto-detected Node version: {self.config.release.node_version}")

        node_cmd = [bench_cli, "setup", "requirements", "--node"]

        if self.config.release.node_version:
            nv = self.config.release.node_version
            self.printer.change_head(f"Installing Node {nv} via fnm")
            self.runner.run(["fnm", "install", nv, "&&", "fnm", "default", nv], bench_directory, capture_output=False)
            self.printer.print(f"Node {nv} installed and set as default")

        if apps:
            self.printer.change_head("Installing all apps node packages")
            self.runner.run(node_cmd, bench_directory, capture_output=False)
            self.printer.print("Installed all apps node packages")
        else:
            self.printer.print("Skipping node packages install (no apps)")

        if bench_directory.env.exists():
            self.printer.change_head("Backing up existing Python venv")
            env_bak = bench_directory.path / "env.bak"
            if env_bak.exists():
                self.runner.run(["rm", "-rf", "env.bak"], bench_directory, capture_output=False)
            self.runner.run(["mv", "env", "env.bak"], bench_directory, capture_output=False)
            self.printer.print("Backed up env to env.bak")

        self.printer.change_head("Creating Python venv using uv")
        venv_cmd = ["uv", "venv", "env", "--seed", "--relocatable", "--no-project"]
        if self.config.release.python_version:
            venv_cmd += ["--python", self.config.release.python_version]
        self.runner.run(venv_cmd, bench_directory, capture_output=False)
        self.printer.print("Python venv created")

        start_time = time.time()

        self.bench_install_all_apps_in_python_env(bench_directory, apps, current, bench_path, site_name, host_run)

        end_time = time.time()
        elapsed_time = end_time - start_time
        self.printer.print(f"Apps python env install time: {elapsed_time:.2f} seconds")

        self.printer.change_head("Configuring apps.txt")
        apps_txt_path = bench_directory.sites / "apps.txt"
        apps_txt_path.parent.mkdir(parents=True, exist_ok=True)

        with apps_txt_path.open("w") as f:
            for app in apps:
                app_path = bench_directory.apps / app.dir_name
                if not app_path.is_dir():
                    continue
                app_python_module_name = bench_directory.get_app_python_module_name(app_path)
                f.write(f"{app_python_module_name}\n")
        self.printer.print("Configured apps.txt")

    def bench_build(
        self,
        bench_directory: BenchDirectory,
        apps: list,
        bench_cli: str,
        current: BenchDirectory,
        bench_path: Path,
        site_name: str,
        host_run: Callable,
    ):
        self.printer.change_head("Running bench build for all apps")
        for app in apps:
            app_dir_path = self.runner.app_exec_path(bench_directory, app.app_name)
            if app.host_before_bench_build:
                self.printer.print(f"Running host pre-build for {app.app_name}")
                self._run_script(
                    app.host_before_bench_build,
                    bench_directory,
                    current,
                    bench_path,
                    site_name,
                    host_run,
                    f"host pre-build for {app.app_name}",
                    app_name=app.app_name,
                )
            if app.before_bench_build:
                self.printer.print(f"Running pre-build command for {app.app_name} in app directory")
                self._run_script(
                    app.before_bench_build,
                    bench_directory,
                    current,
                    bench_path,
                    site_name,
                    host_run,
                    f"Pre-build script for {app.app_name}",
                    container=True,
                    app_name=app.app_name,
                    custom_workdir=app_dir_path,
                )

        prod_build_cmd = [
            bench_cli,
            "build",
            "--force",
            "--production",
        ]

        if apps:
            self.runner.run(prod_build_cmd[:-1], bench_directory, capture_output=False)
            self.runner.run(prod_build_cmd, bench_directory, capture_output=False)

        for app in apps:
            app_dir_path = self.runner.app_exec_path(bench_directory, app.app_name)
            if app.after_bench_build:
                self.printer.print(f"Running post-build command for {app.app_name} in app directory")
                self._run_script(
                    app.after_bench_build,
                    bench_directory,
                    current,
                    bench_path,
                    site_name,
                    host_run,
                    f"Post-build script for {app.app_name}",
                    container=True,
                    app_name=app.app_name,
                    custom_workdir=app_dir_path,
                )
            if app.host_after_bench_build:
                self.printer.print(f"Running host post-build for {app.app_name}")
                self._run_script(
                    app.host_after_bench_build,
                    bench_directory,
                    current,
                    bench_path,
                    site_name,
                    host_run,
                    f"host post-build for {app.app_name}",
                    app_name=app.app_name,
                )
        self.printer.print("Built all apps")

    def run_bench_migrate(self, bench_directory: BenchDirectory, bench_cli: str) -> None:
        if not self.config.switch.migrate:
            self.printer.print("Skipped. Bench migrate")
            return

        self.printer.change_head("Running bench migrate")
        self.runner.run([bench_cli, "migrate"], bench_directory, capture_output=False)
        self.printer.print("Bench migrate done")

    def bench_symlink(self, bench_path: Path, bench_directory: BenchDirectory):
        self.printer.change_head("Symlinking")

        if bench_path.is_symlink():
            bench_path.unlink()
        elif bench_path.is_dir():
            shutil.rmtree(bench_path)
        elif bench_path.exists():
            bench_path.unlink()

        bench_path.symlink_to(get_relative_path(bench_path, bench_directory.path), True)

    def bench_restart(
        self,
        bench_directory: BenchDirectory,
        bench_path: Path,
        current: BenchDirectory,
        site_name: str,
        host_run: Callable,
        migrate: bool = False,
        migrate_timeout: int = 300,
        migrate_command: Optional[str] = None,
        drain_workers: bool = False,
        drain_workers_timeout: int = 300,
        drain_workers_poll: int = 5,
        skip_stale_workers: bool = True,
        skip_stale_timeout: int = 15,
        worker_kill_timeout: int = 15,
        worker_kill_poll: float = 3.0,
        maintenance_phases: Optional[list] = None,
    ):
        self.printer.change_head("Restart and Migrate")

        args = []

        if migrate:
            args += ["--migrate"]
            if migrate_timeout:
                args += ["--migrate-timeout", str(migrate_timeout)]
            if migrate_command:
                args += ["--migrate-command", migrate_command]

        if drain_workers:
            args += ["--drain-workers"]
            if drain_workers_timeout:
                args += ["--drain-workers-timeout", str(drain_workers_timeout)]
            if drain_workers_poll:
                args += ["--drain-workers-poll", str(drain_workers_poll)]
            if skip_stale_workers:
                args += ["--skip-stale-workers"]
            else:
                args += ["--no-skip-stale-workers"]
            if skip_stale_timeout:
                args += ["--skip-stale-timeout", str(skip_stale_timeout)]
            if worker_kill_timeout:
                args += ["--worker-kill-timeout", str(worker_kill_timeout)]
            if worker_kill_poll:
                args += ["--worker-kill-poll", str(worker_kill_poll)]

        if maintenance_phases:
            for phase in maintenance_phases:
                args += ["--maintenance-mode", phase]

        if self.config.switch.host_before_restart:
            self._run_script(
                self.config.switch.host_before_restart,
                bench_directory,
                current,
                bench_path,
                site_name,
                host_run,
                "host pre-restart",
            )

        if self.config.switch.before_restart:
            self._run_script(
                self.config.switch.before_restart,
                bench_directory,
                current,
                bench_path,
                site_name,
                host_run,
                "container pre-restart",
                container=True,
            )

        start_time = time.time()

        self.runner.restart_services(args, bench_directory)

        if self.config.verbose:
            end_time = time.time()
            elapsed_time = end_time - start_time
            self.printer.print(
                f"Frappe Services Restart Time Taken: {human_readable_time(elapsed_time)}", emoji_code=":robot_face:"
            )
        self.printer.start("Working")
        self.printer.print("Symlinked and restarted")

        if self.config.switch.after_restart:
            self._run_script(
                self.config.switch.after_restart,
                bench_directory,
                current,
                bench_path,
                site_name,
                host_run,
                "container post-restart",
                container=True,
            )

        if self.config.switch.host_after_restart:
            self._run_script(
                self.config.switch.host_after_restart,
                bench_directory,
                current,
                bench_path,
                site_name,
                host_run,
                "host post-restart",
            )

from pathlib import Path
from typing import Any, Callable
import shutil

from fmd.release_directory import BenchDirectory
from fmd.helpers import get_relative_path


class AppService:
    def __init__(self, runner: Any, host_runner: Any, config: Any, printer: Any):
        self.runner = runner
        self.host_runner = host_runner
        self.config = config
        self.printer = printer

    def clone_apps(
        self,
        data: BenchDirectory,
        bench_directory: BenchDirectory,
        apps: list,
        site_name: str,
        is_app_installed: Callable[[str, str], bool],
        overwrite: bool = False,
        backup: bool = True,
    ):
        clone_map = {}

        for app in apps:
            self.printer.change_head(f"Cloning repo {app.repo}")

            if app.symlink:
                key = (app.repo, app.ref)
                if key in clone_map:
                    clone_path = clone_map[key]
                    self.printer.print(f"Reusing clone for {app.repo}@{app.ref} subdir: {app.subdir_path}")
                else:
                    clone_path = data.get_frappe_bench_app_path(
                        app, append_release_name=bench_directory.path.resolve().name, suffix="_clone"
                    )
                    data.clone_app(app, clone_path=clone_path, move_to_subdir=False)
                    clone_map[key] = clone_path
            else:
                clone_path = bench_directory.get_frappe_bench_app_path(app, suffix="_clone")
                bench_directory.clone_app(app, clone_path=clone_path)

            from_dir = clone_path

            if app.symlink:
                if app.subdir_path:
                    from_dir = from_dir / app.subdir_path

            app_name = app.app_name if app.app_name else bench_directory.get_app_python_module_name(from_dir)
            app.app_name = app_name
            to_dir = bench_directory.apps / app_name

            if to_dir.exists():
                if not overwrite:
                    raise FileExistsError(
                        f"App directory '{to_dir}' already exists. Use \"--overwrite\" to overwrite it."
                    )

                archive_base = bench_directory.path / "archived" / "apps"
                archive_base.mkdir(parents=True, exist_ok=True)
                import datetime

                date_str = datetime.datetime.now().strftime("%Y-%m-%d")
                archive_path = archive_base / f"{to_dir.name}-{date_str}"
                shutil.move(str(to_dir), str(archive_path))
                self.printer.print(f"Archived existing app to {archive_path}")

                if not backup:
                    shutil.rmtree(str(archive_path))

            if app.symlink:
                symlink_path = get_relative_path(to_dir, from_dir)
                to_dir.symlink_to(symlink_path, True)
            else:
                shutil.move(str(from_dir), str(to_dir))

            self.printer.print(
                f"{'Remote removed ' if app.remove_remote else ''}Cloned Repo: {app.repo}, Module Name: '{app_name}'"
            )

    def bench_install_apps(
        self,
        bench_directory: BenchDirectory,
        apps: list,
        site_name: str,
        bench_cli: str,
        is_app_installed: Callable[[str, str], bool],
    ) -> None:
        dirs = [d for d in bench_directory.apps.iterdir() if d.is_dir()]
        for app in dirs:
            self._install_app(
                bench_directory.apps / app.name,
                bench_directory,
                site_name,
                bench_cli,
                is_app_installed,
            )

    def _install_app(
        self,
        app_path: Path,
        bench_directory: BenchDirectory,
        site_name: str,
        bench_cli: str,
        is_app_installed: Callable[[str, str], bool],
    ) -> None:
        app_python_module_name = bench_directory.get_app_python_module_name(app_path)

        if is_app_installed(site_name, app_python_module_name):
            self.printer.print(f"App {app_python_module_name} is already installed.")
            return

        self.printer.change_head(f"Installing app {app_python_module_name} in {site_name}")
        install_command = [bench_cli, "--site", site_name, "install-app", app_python_module_name]

        output = self.runner.run(install_command, bench_directory, capture_output=True)

        if hasattr(output, "combined") and f"App {app_python_module_name} already installed" in output.combined:
            self.printer.print(f"App {app_python_module_name} is already installed.")
        else:
            self.printer.print(f"Installed app {app_python_module_name} in {site_name}")

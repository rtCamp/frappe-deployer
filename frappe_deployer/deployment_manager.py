import tempfile
from pathlib import Path
import shutil
import time
import gzip
from typing import Iterable, Literal, Optional, Tuple, Union
from pydantic import BaseModel
from frappe_deployer.config.app import AppConfig
from frappe_deployer.config.fm import FMConfig
from frappe_deployer.config.host import HostConfig

from frappe_manager import CLI_DIR
from frappe_manager.compose_manager.ComposeFile import ComposeFile
from frappe_manager.compose_project.compose_project import ComposeProject
from frappe_manager.logger.log import richprint
from frappe_manager.migration_manager.migration_helpers import (
    MigrationBench,
    MigrationServicesManager,
)
from frappe_manager.services_manager.database_service_manager import (
    DatabaseServerServiceInfo,
    MariaDBManager,
)
from frappe_manager.utils.docker import (
    DockerException,
    SubprocessOutput,
    run_command_with_exit_code,
)
from frappe_deployer.ssh import ssh_run
from frappe_manager.utils.helpers import json
from rich.rule import Rule
from frappe_deployer.config.app import AppConfig
from frappe_deployer.config.config import Config
from frappe_deployer.consts import (
    BACKUP_DIR_NAME,
    DATA_DIR_NAME,
    RELEASE_DIR_NAME,
    RELEASE_SUFFIX,
)
from frappe_deployer.exceptions import SiteAlreadyConfigured
from frappe_deployer.helpers import (
    get_json,
    get_relative_path,
    human_readable_time,
    update_json_keys_in_file_path,
)
from frappe_deployer.release_directory import BenchDirectory

class DeploymentManager:
    apps: list[AppConfig]
    path: Path
    verbose: bool = False
    mode: Literal["fm", "host"] = "fm"

    def __init__(self, config: Config) -> None:
        self.config = config
        self.verbose = config.verbose
        self.site_name = config.site_name
        self.bench_path = config.bench_path

        self.apps = config.apps
        self.mode = config.mode
        self.path = config.deploy_dir_path
        self.printer = richprint
        self.bench_cli = "bench"
        self.fm_helper_cli = "/opt/user/.bin/fm-helper"

        self.current = BenchDirectory(config.bench_path)

        self.data = BenchDirectory(self.path / DATA_DIR_NAME)
        self.backup = BenchDirectory(self.path / BACKUP_DIR_NAME / RELEASE_SUFFIX)
        self.new = BenchDirectory(self.path / RELEASE_SUFFIX)

        self.previous_release_dir = self.current.path.resolve()

        self.printer.start("Working")

    def configure_basic_info(self):
        self.site_installed_apps = self.get_site_installed_apps(self.current)
        self.configure_bench_cli()

    def configure_bench_cli(self):
        # Create a virtual environment in ~/.cache/frappe-deployer-venv
        venv_path = Path.home() / ".cache" / "frappe-deployer-venv"

        if self.mode == 'fm':
            venv_path =  Path("/workspace/.cache/frappe-deployer-venv")

        # Check if the virtual environment exists
        if not venv_path.exists() or not (venv_path / "bin" / "bench").exists():
            self.python_env_create(self.current, venv_path=str(venv_path))

            # Install bench and frappe from given GitHub tags link using uv
            bench_install_command = [
                "uv", "pip",
                "install",
                "--python",
                f"{str(venv_path)}/bin/python",
                "git+https://github.com/frappe/bench.git",
                "git+https://github.com/frappe/frappe.git"
            ]

            self.host_run(
                bench_install_command,
                self.current,
                container=self.mode == "fm",
                capture_output=False
            )

        # Use this bench from this venv in subsequent runs
        self.bench_cli = str((venv_path / "bin" / "bench").absolute())

    def sync_sites_to_data_dir(self):
        """Sync sites from current bench to data directory"""
        self.printer.change_head("Syncing sites to data directory")

        # Create data sites directory if it doesn't exist
        self.data.sites.mkdir(parents=True, exist_ok=True)

        # Move all sites from current bench to data directory
        # NOTE: This is done in configure function for a specific bench

        # Create symlinks from new bench to data directory and handle new files
        for site in self.data.list_sites():
            data_site_path = self.data.sites / site.name
            new_site_path = self.new.sites / site.name
            new_site_path.mkdir(parents=True, exist_ok=True)

            # First, check for new files/dirs in new_site_path that don't exist in data_site_path
            if new_site_path.exists():
                for item in new_site_path.iterdir():
                    data_item_path = data_site_path / item.name
                    if not data_item_path.exists():
                        # Move new item to data directory
                        shutil.move(str(item), str(data_item_path))
                        self.printer.print(f"Moved new item {item.name} to data directory")

            # Create symlinks for all files in data site directory
            for item in data_site_path.iterdir():
                data_item_path = data_site_path / item.name
                site_item_symlink = new_site_path / item.name
                if not site_item_symlink.exists():
                    relative_path = get_relative_path(site_item_symlink, data_item_path)
                    site_item_symlink.symlink_to(relative_path, True)
                    self.printer.print(f"Symlink {site_item_symlink.name} --> {relative_path}")

    def configure_symlinks(self):
        self.printer.change_head("Configuring symlinks")

        # Sync sites to data directory
        self.sync_sites_to_data_dir()

        # common_site_config.json
        if not self.data.common_site_config.exists():
            raise RuntimeError(
                f"{self.data.common_site_config.absolute()} doesn't exist. Please Check"
            )

        self.new.common_site_config.symlink_to(
            get_relative_path(
                self.new.common_site_config, self.data.common_site_config
            ),
            True,
        )
        self.printer.print(f"Symlink [blue]{self.new.common_site_config.name}[/blue] ")

        # config
        if not self.data.config.exists():
            raise RuntimeError(
                f"{self.data.config.absolute()} doesn't exist. Please Check"
            )

        self.new.config.symlink_to(
            get_relative_path(self.new.config, self.data.config), True
        )
        self.printer.print(f"Symlink [blue]{self.new.config.name}[/blue] ")

        # logs
        if not self.data.logs.exists():
            self.printer.print("logs directory doesn't exists recreating it")
            self.data.logs.mkdir(parents=True)

        self.new.logs.symlink_to(get_relative_path(self.new.logs, self.data.logs), True)
        self.printer.print(f"Symlink [blue]{self.new.logs.name}[/blue] ")

    def configure_data_dir(self):

        if not self.data.path.exists():
            self.printer.change_head(f"Creating {DATA_DIR_NAME} dir")
            self.data.path.mkdir()
            self.printer.print("Created release data dir")

        # move all sites
        self.printer.change_head("Moving sites into data dir")
        for site in self.current.list_sites():
            data_site_path = self.data.sites / site.name
            shutil.move(str(site.absolute()), str(data_site_path.absolute()))
            self.printer.print(f"Moved {site.name}")

        # common_site_config.json
        if self.current.common_site_config.exists():
            self.printer.change_head(
                "Moving common_site_config.json into data dir"
            )
            shutil.move(
                str(self.current.common_site_config.absolute()),
                str(self.data.common_site_config.absolute()),
            )
            self.printer.print(
                "Moved common_site_config.json and created symlink"
            )

        # logs
        if self.current.logs.exists():
            self.printer.change_head("Moving logs into data dir")
            shutil.move(
                str(self.current.logs.absolute()),
                str(self.data.logs.absolute()),
            )
            self.printer.print("Moved logs and created symlink")

        # config
        if self.current.config.exists():
            self.printer.change_head("Moving logs into data dir")
            shutil.move(
                str(self.current.config.absolute()),
                str(self.data.config.absolute()),
            )
            self.printer.print("Moved logs and created symlink")


    @staticmethod
    def configure(config: Config, only_move: bool = False, backups: Optional[bool]=None):
        if not backups:
            backups = config.backups

        release = DeploymentManager(config)

        if release.current.path.is_symlink():
            raise SiteAlreadyConfigured(str(release.current.path))

        try:
            if backups:
                release.printer.change_head("Creating backup")
                shutil.copytree(config.bench_path, release.backup.path / 'configure' , symlinks=True)
                release.bench_db_and_configs_backup()
                release.printer.print("Backup completed")
            else:
                release.printer.error('Taking backup is disabled.')

            release.configure_data_dir()

            if only_move:
                return

            release.configure_symlinks()

            # bench
            release.printer.change_head(
                "Moving bench directory, creating initial release"
            )
            shutil.move(
                str(release.current.path.absolute()), str(release.new.path.absolute())
            )

            release.configure_uv(release.new)
            release.bench_setup_requiments(release.new)
            release.bench_symlink_and_restart(release.new)

            release.bench_build(release.new)
            release.bench_install_and_migrate(release.current)

        except Exception as e:
            if backups:
                release.printer.print(f'Rollback\n{"--"*10} ')
                release.printer.change_head(
                    f"Deleting the {release.current.path.name} tangled deployment"
                )
                if release.current.path.exists():
                    if release.current.path.is_symlink():
                        release.current.path.unlink()
                    else:
                        shutil.rmtree(release.current.path)

                release.printer.print(
                    f"Deleted the {release.current.path.name} tangled deployment"
                )

                release.printer.change_head(
                    f"Moving backup {release.backup.path.name} to {release.current.path}"
                )

                if release.backup.path.exists():
                    shutil.move(release.backup.path, release.current.path)

                release.printer.print(
                    f"Moved backup {release.backup.path.name} to {release.current.path}"
                )

                release.printer.change_head(
                    f"Deleting the {release.data.path.name} tangled deployment"
                )

                if release.data.path.exists():
                   shutil.rmtree(release.data.path)

                release.printer.print(
                    f"Deleted the {release.data.path.name} tangled deployment"
                )

            raise e

    def bench_db_and_configs_backup(self):
        if self.config.backups:
            self.printer.change_head("Backing up db, common_site_config and site_config.json")
            (self.backup.sites/ self.site_name).mkdir(exist_ok=True,parents=True)
            shutil.copyfile(self.current.common_site_config, self.backup.common_site_config)
            self.bench_backup(self.site_name)
            self.printer.print("Backed up db, common_site_config and site_config.json")

    def create_new_release(self):
        if not self.bench_path.is_symlink():
            if not self.config.configure:
                raise RuntimeError(
                        "Provided bench is not configured. Please use `configure` subcommand for this."
                    )
        else:
            self.config.configure = False

        self.printer.print(f'Bench: {self.config.bench_name} Site: {self.config.site_name}')

        # create new release dirs
        self.printer.change_head("Configuring new release dirs")

        if not self.config.configure:
            self.bench_db_and_configs_backup()

        if self.config.fm:
            if self.config.fm.restore_db_from_site:
                if not self.config.restore_db_file_path:
                    self.config.restore_db_file_path = self.bench_backup(
                        self.config.fm.restore_db_from_site, using_bench_backup=False,compress=True,sql_delete_after_compress=False
                    )
                    
        for dir in [self.new.path, self.new.apps, self.new.sites]:
            dir.mkdir(exist_ok=True)
            self.printer.print(f"Created dir [blue]{dir.name}[/blue] ")

        self.config.to_toml(self.new.path / f'{self.config.site_name}.toml')

        if self.config.configure:
            if self.config.maintenance_mode:
                start_time = time.time()

                self.printer.print("Enabled maintenance mode")
                self.current.maintenance_mode(self.site_name, True)

            DeploymentManager.configure(config=self.config, only_move=True,backups=True)

            self.printer.change_head(
                "Moving bench directory, creating initial release"
            )

            shutil.move(
                str(self.current.path.absolute()), str(self.path / 'prev_frappe_bench')
            )

            self.bench_path.symlink_to(
                get_relative_path(self.bench_path, self.new.path), True
            )


        self.configure_symlinks()

        self.clone_apps(self.new)

        self.python_env_create(self.new)

        self.bench_setup_requiments(self.new)
        self.bench_build(self.new)

        self.bench_clear_cache(self.current,True)

        if self.config.maintenance_mode:
            start_time = time.time()

            self.printer.print("Enabled maintenance mode")
            self.current.maintenance_mode(self.site_name, True)

        self.sync_configs_with_files(self.config.site_name)

        exception = None

        try:
            self.bench_symlink_and_restart(self.new)

            if self.config.restore_db_file_path:
                self.bench_restore(self.config.restore_db_file_path)

                if self.config.fm:
                    if self.config.fm.restore_db_from_site:
                        
                        if self.config.search_replace:
                            self.search_and_replace_in_database(self.config.fm.restore_db_from_site, self.site_name)

                        if self.config.restore_db_file_path.exists():
                            self.config.restore_db_file_path.unlink()
                            self.printer.print(f'Deleted temporary exported db file {self.config.restore_db_file_path.name}')

                if self.config.fm:
                    if self.config.fm.restore_db_from_site:
                        self.sync_db_encryption_key_from_site(self.config.fm.restore_db_from_site,self.config.fm.restore_db_from_site)

                self.site_installed_apps = self.get_site_installed_apps(self.current)

            self.bench_install_and_migrate(self.current)

        except Exception as e:
            if self.config.rollback:
                exception = e
                self.printer.error(f"Failed to create new release {self.new.path.name}")
                self.printer.stdout.print(Rule(title=f"Rolling back to previous release: {self.previous_release_dir.name}"))

                if self.bench_path.exists():
                    self.bench_path.unlink()

                self.bench_symlink_and_restart(BenchDirectory(self.previous_release_dir))
                self.printer.print("Symlinked previous deployment before new release")

            self.bench_install_and_migrate(self.current)

        self.current.maintenance_mode(self.site_name, False)

        if self.config.maintenance_mode:
            self.printer.print("Disabled maintenance mode")

            if self.config.verbose:
                end_time = time.time()
                elapsed_time = end_time - start_time
                self.printer.print(f"Maintenance Mode Time: {elapsed_time:.2f} seconds",emoji_code=':robot_face:')

        self.cleanup_releases()

        if exception:
            self.printer.error(f"The following error caused the script to rollback changes from {self.previous_release_dir} -> {self.new.path.name}")
            raise exception

    def cleanup_releases(self):
        retain_limit = self.config.releases_retain_limit
        self.printer.change_head(f"Retaining {retain_limit} and cleaning up releases")

        # Get current release directory (resolves symlink)
        current_release_bench_path = self.bench_path.resolve()

        release_dirs = [d for d in self.path.iterdir() if d.is_dir() and d.name.startswith(RELEASE_DIR_NAME)]
        release_dirs.sort(key=lambda d: self.extract_timestamp(d.name), reverse=True)

        # Always keep current release at front
        if current_release_bench_path in release_dirs:
            release_dirs.remove(current_release_bench_path)
            release_dirs.insert(0, current_release_bench_path)

        # Always keep previous release next if it exists
        if self.previous_release_dir in release_dirs and self.previous_release_dir != current_release_bench_path:
            release_dirs.remove(self.previous_release_dir)
            release_dirs.insert(1, self.previous_release_dir)

        # Keep required number of releases
        retain_releases_dirs = release_dirs[:retain_limit]
        releases_to_remove = release_dirs[retain_limit:]

        # Never remove current release
        releases_to_remove = [d for d in releases_to_remove if d != current_release_bench_path]

        for dir_to_remove in releases_to_remove:
            shutil.rmtree(dir_to_remove)

        if releases_to_remove:
            deleted_dir_names = ' '.join([d.name for d in releases_to_remove])
            self.printer.print(f"Deleted releases [blue]{deleted_dir_names}[/blue]")

        self.printer.start("Working")

    def extract_timestamp(self, dir_name: str) -> int:
        try:
            timestamp_str = dir_name.split('_')[-1]
            return int(timestamp_str)
        except ValueError:
            return 0

    def clone_apps(self, bench_directory: 'BenchDirectory'):
        for app in self.apps:
            self.printer.change_head(f"Cloning repo {app.repo}")
            bench_directory.clone_app(app)

            app_name = bench_directory.get_app_python_module_name(
                bench_directory.apps / app.dir_name
            )

            from_dir = bench_directory.apps / app.dir_name
            to_dir = bench_directory.apps / app_name

            shutil.move(str(from_dir),str(to_dir))

            self.printer.print(
                f"{'Remote removed ' if app.remove_remote else ''}Cloned Repo: {app.repo}, Module Name: '{app_name}'"
            )

    def get_dir_size(self, path: Path) -> str:
        """Calculate directory size and return human readable format."""
        import os
        from rich.progress import Progress, SpinnerColumn, TextColumn
        
        total_size = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            task = progress.add_task(f"Calculating size of {path.name}...", total=None)
            
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = Path(dirpath) / f
                    if not fp.is_symlink():  # Skip if it's a symbolic link
                        try:
                            total_size += fp.stat().st_size
                            progress.update(task)
                        except (PermissionError, FileNotFoundError):
                            continue  # Skip files we can't access
        
        # Convert to human readable format
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if total_size < 1024.0:
                return f"{total_size:.1f} {unit}"
            total_size /= 1024.0
        return f"{total_size:.1f} PB"

    def cleanup_workspace_cache(
        self,
        backup_retain_limit: int = 0,
        release_retain_limit: int = 0,
        auto_approve: bool = False,
        show_sizes: bool = False
    ):
        """Cleanup deployment backups, releases and cache directories with interactive prompts.
        Also reports on items that have already been cleaned.
        
        Parameters
        ----------
        backup_retain_limit : int
            Number of backup directories to retain, sorted by timestamp in name. Default 0 to remove all.
        release_retain_limit : int
            Number of release directories to retain. Default 0 to remove all except current.
            Will always preserve current release and its previous release.
        auto_approve : bool
            If True, skip confirmation prompts and auto-approve all deletions
        show_sizes : bool
            Whether to calculate and show directory sizes (can be slow for large directories)
        """
        from rich.prompt import Confirm, Prompt
        from rich.console import Console
        from rich.table import Table
        
        console = Console()
        self.printer.stop()  # Stop the "working" spinner

        def print_items_table(items: list[Path], title: str) -> Table:
            """Create and print a table of items to be deleted"""
            table = Table(title=title)
            table.add_column("Index", justify="right", style="cyan")
            table.add_column("Name", style="magenta") 
            if show_sizes:
                table.add_column("Size", style="green")
            table.add_column("Path", style="blue")
            
            for idx, item in enumerate(items, 1):
                row = [str(idx), item.name]
                if show_sizes:
                    size = self.get_dir_size(item)
                    row.append(size)
                row.append(str(item.absolute()))
                table.add_row(*row)
            
            console.print(table)
            return table

        def get_selected_indices(items: list[Path], prompt_text: str) -> list[int]:
            """Get user selection of items to delete"""
            if not items:
                return []
                
            if auto_approve:
                return list(range(len(items)))
                
            print_items_table(items, prompt_text)
            
            while True:
                selection = Prompt.ask(
                    f"\nEnter indices to delete (1-{len(items)}, 'all' for all, or empty to skip)",
                    default=""
                )
                
                if not selection:
                    return []
                
                if selection.lower() == 'all':
                    return list(range(len(items)))
                    
                try:
                    indices = [int(i.strip()) - 1 for i in selection.split(',')]
                    if all(0 <= i < len(items) for i in indices):
                        return indices
                    console.print("[red]Invalid indices. Please try again.[/red]")
                except ValueError:
                    console.print("[red]Invalid input. Please enter numbers separated by commas or 'all'.[/red]")

        # Cleanup .cache directory
        cache_dir = self.path / '.cache'
        if self.mode == 'host':
            cache_dir = Path.home() / '.cache'

        if not cache_dir.exists():
            console.print(f"\n[blue]Cache directory {cache_dir} doesn't exist - already clean[/blue]")
        else:
            size = self.get_dir_size(cache_dir)
            console.print(f"\n[yellow]Cache directory available for cleanup:[/yellow]")
            size_info = f" ([green]{self.get_dir_size(cache_dir)}[/green])" if show_sizes else ""
            console.print(f"[magenta]{cache_dir.name}[/magenta]{size_info} - [blue]{cache_dir.absolute()}[/blue]")
            try:
                if auto_approve or Confirm.ask(f"Delete cache directory: {cache_dir}?"):
                    shutil.rmtree(cache_dir)
                    console.print(f"[green]Removed {cache_dir.absolute()} directory[/green]")
            except Exception as e:
                console.print(f"[red]Failed to remove {cache_dir.absolute()} directory: {str(e)}[/red]")

        # Cleanup prev_frappe_bench
        prev_bench = self.path / 'prev_frappe_bench'
        if not prev_bench.exists():
            console.print("\n[blue]Previous bench directory doesn't exist - already clean[/blue]")
        else:
            size = self.get_dir_size(prev_bench)
            console.print(f"\n[yellow]Previous bench directory available for cleanup:[/yellow]")
            size_info = f" ([green]{self.get_dir_size(prev_bench)}[/green])" if show_sizes else ""
            console.print(f"[magenta]{prev_bench.name}[/magenta]{size_info} - [blue]{prev_bench.absolute()}[/blue]")
            try:
                if auto_approve or Confirm.ask(f"Delete previous bench directory: {prev_bench}?"):
                    shutil.rmtree(prev_bench)
                    console.print(f"[green]Removed {prev_bench.absolute()} directory[/green]")
            except Exception as e:
                console.print(f"[red]Failed to remove {prev_bench.absolute()}: {str(e)}[/red]")

        # Cleanup deployment backups
        backup_dir = self.path / BACKUP_DIR_NAME

        if backup_dir.exists():
            backup_dirs = [d for d in backup_dir.iterdir() if d.is_dir()]
            backup_dirs.sort(key=lambda x: x.name, reverse=True)

            if not backup_dirs:
                console.print("\n[blue]No backup directories found - already clean[/blue]")
            else:
                # Modified logic: If retain_limit is 0, all backups can be deleted
                # If retain_limit > 0, keep that many backups without asking
                if backup_retain_limit > 0:
                    kept_backups = backup_dirs[:backup_retain_limit]
                    backups_to_remove = backup_dirs[backup_retain_limit:]
                    
                    console.print(f"\n[green]Currently keeping {len(kept_backups)} recent backups:[/green]")
                    for backup in kept_backups:
                        console.print(f"[green]  • {backup.name}[/green]")

                    if not backups_to_remove:
                        console.print(f"[blue]No backup directories to clean - already at {backup_retain_limit} limit[/blue]")
                    else:
                        console.print("\n[yellow]Backup directories that exceed retain limit:[/yellow]")
                        selected_indices = get_selected_indices(
                            backups_to_remove,
                            f"Backup directories to clean (keeping {backup_retain_limit} most recent)"
                        )

                        for idx in selected_indices:
                            backup_to_remove = backups_to_remove[idx]
                            try:
                                if auto_approve or Confirm.ask(f"Delete backup directory: {backup_to_remove.name}?"):
                                    shutil.rmtree(backup_to_remove)
                                    console.print(f"[green]Removed backup directory: {backup_to_remove.name}[/green]")
                            except Exception as e:
                                console.print(f"[red]Failed to remove {backup_to_remove.name}: {str(e)}[/red]")
                else:
                    # When retain_limit is 0, all backups can be selected for deletion
                    console.print("\n[yellow]All backup directories available for cleanup:[/yellow]")
                    selected_indices = get_selected_indices(
                        backup_dirs,
                        "Backup directories to clean (no retention limit)"
                    )

                    for idx in selected_indices:
                        backup_to_remove = backup_dirs[idx]
                        try:
                            if auto_approve or Confirm.ask(f"Delete backup directory: {backup_to_remove.name}?"):
                                shutil.rmtree(backup_to_remove)
                                console.print(f"[green]Removed backup directory: {backup_to_remove.name}[/green]")
                        except Exception as e:
                            console.print(f"[red]Failed to remove {backup_to_remove.name}: {str(e)}[/red]")
        else:
            console.print("\n[blue]No backup directory exists - already clean[/blue]")

        # Cleanup release directories
        current_release = self.bench_path.resolve()
        release_dirs = [d for d in self.path.iterdir()
                        if d.is_dir() and d.name.startswith(RELEASE_DIR_NAME)]

        if not release_dirs:
            console.print("\n[blue]No release directories found - already clean[/blue]")
        else:
            release_dirs.sort(key=lambda x: self.extract_timestamp(x.name), reverse=True)

            # Handle releases based on retain limit
            if release_retain_limit > 0:
                # Keep specific number of releases
                kept_releases = release_dirs[:release_retain_limit]
                releases_to_remove = release_dirs[release_retain_limit:]
                releases_to_remove = [d for d in releases_to_remove if d != current_release]  # Protect current release

                console.print(f"\n[green]Currently keeping {len(kept_releases)} releases:[/green]")
                for release in kept_releases:
                    suffix = " (current)" if release == current_release else ""
                    console.print(f"[green]  • {release.name}{suffix}[/green]")

                if not releases_to_remove:
                    console.print(f"[blue]No release directories to clean - already at {release_retain_limit} limit[/blue]")
                else:
                    console.print("\n[yellow]Release directories that exceed retain limit:[/yellow]")
                    selected_indices = get_selected_indices(
                        releases_to_remove,
                        f"Release directories to clean (keeping {release_retain_limit} most recent)"
                    )

                    if auto_approve:
                        self.config.releases_retain_limit = release_retain_limit
                        self.cleanup_releases()
                    else:
                        for idx in selected_indices:
                            release_to_remove = releases_to_remove[idx]
                            try:
                                if release_to_remove != current_release and Confirm.ask(f"Delete release directory: {release_to_remove.name}?"):
                                    shutil.rmtree(release_to_remove)
                                    console.print(f"[green]Removed release directory: {release_to_remove.name}[/green]")
                            except Exception as e:
                                console.print(f"[red]Failed to remove release {release_to_remove.name}: {str(e)}[/red]")
            else:
                # When retain_limit is 0, show all releases except current
                available_releases = [d for d in release_dirs if d != current_release]
                if not available_releases:
                    console.print("\n[blue]No release directories available for cleanup (excluding current release)[/blue]")
                else:
                    console.print("\n[yellow]All release directories available for cleanup:[/yellow]")
                    selected_indices = get_selected_indices(
                        available_releases,
                        "Release directories to clean (no retention limit)"
                    )

                    for idx in selected_indices:
                        release_to_remove = available_releases[idx]
                        try:
                            if auto_approve or Confirm.ask(f"Delete release directory: {release_to_remove.name}?"):
                                shutil.rmtree(release_to_remove)
                                console.print(f"[green]Removed release directory: {release_to_remove.name}[/green]")
                        except Exception as e:
                            console.print(f"[red]Failed to remove release {release_to_remove.name}: {str(e)}[/red]")


    def get_mariadb_bench_client(self):
        compose_file: ComposeFile = ComposeFile(self.path.parent / "docker-compose.yml")
        compose_project: ComposeProject = ComposeProject(
            compose_file_manager=compose_file
        )

        services_manager: MigrationServicesManager = MigrationServicesManager(
            services_path=CLI_DIR / "services"
        )

        server_db_info: DatabaseServerServiceInfo = (
            DatabaseServerServiceInfo.import_from_compose_file(
                "global-db", services_manager.compose_project
            )
        )
        mariadb_client = MariaDBManager(
            database_server_info=server_db_info,
            compose_project=compose_project,
            run_on_compose_service="frappe",
        )

        return mariadb_client

    def bench_backup(self, site_name: str, file_name: Optional[str] = None, using_bench_backup: bool = True, compress: bool = True, sql_delete_after_compress: bool = True) -> Optional[Path]:
        """Return backup host path"""

        self.printer.change_head(f"Exporting {site_name} db")

        file_name = f"{site_name if file_name is None else file_name}.sql.gz"

        host_backup_config_path = self.backup.path / 'site_config.json'

        host_backup_db_path = self.backup.path / file_name

        backup_config_path = str(host_backup_config_path.absolute())
        backup_db_path = str(host_backup_db_path.absolute())


        if self.mode == 'fm':
            backup_db_path = (
                f"/workspace/{'/'.join(self.backup.path.parts[-2:])}/{file_name}"
            )
            backup_config_path = (
                f"/workspace/{'/'.join(self.backup.path.parts[-2:])}/site_config.json"
            )


        if using_bench_backup:
            db_export_command = [self.bench_cli,'backup','--backup-path-conf', backup_config_path, '--backup-path-db', backup_db_path ]

            output = self.host_run(
                db_export_command,
                self.current,
                #stream=True,
                container=self.mode == "fm",
                capture_output=True)

            return host_backup_db_path

        backup_bench = MigrationBench(name=site_name, path=self.path.parent)
        backup_bench_db_info = backup_bench.get_db_connection_info()

        bench_db_name = backup_bench_db_info.get("name")
        mariadb_client = self.get_mariadb_bench_client()

        host_backup_db_path = host_backup_db_path.parent / host_backup_db_path.name.rstrip('.gz')

        self.backup.path.mkdir(exist_ok=True,parents=True)

        backup_db_path = backup_db_path.rstrip('.gz')

        output = mariadb_client.db_export(bench_db_name, export_file_path=backup_db_path)

        self.printer.print(f"Exported {site_name} db")

        if compress:
            self.printer.change_head(f"Compress {site_name} db")
            with open(host_backup_db_path, 'rb') as f_in:
                import gzip
                with gzip.open(str(host_backup_db_path) + '.gz', 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            if sql_delete_after_compress:
                if host_backup_db_path.exists():
                    host_backup_db_path.unlink()

            self.printer.print(f"DB has been compressed.")

        return host_backup_db_path


    def bench_restore(self, db_file_path: Path):

        if self.mode == 'host':
            self.printer.warning("db restore is not implemented in host mode")
            return

        # Check if the input file is a .gz file
        if db_file_path.suffix == '.gz':
            self.printer.change_head(f"Decompressing {db_file_path}")
            with gzip.open(db_file_path, 'rb') as f_in:
                decompressed_path = db_file_path.with_suffix('')  # Remove .gz suffix
                with open(decompressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            db_file_path = decompressed_path  # Update db_file_path to the decompressed file

        backup_bench = MigrationBench(name=self.site_name, path=self.path.parent)

        self.printer.change_head(
            f"Restoring {self.site_name} with db from {db_file_path}"
        )

        backup_bench_db_info = backup_bench.get_db_connection_info()

        bench_db_name = backup_bench_db_info.get("name")

        mariadb_client = self.get_mariadb_bench_client()

        mariadb_client.db_import(
            db_name=bench_db_name, host_db_file_path=db_file_path
        )
        self.printer.print(f"Restored {self.site_name} with db from {db_file_path}")

    def sync_db_encryption_key_from_site(self, from_bench_name: str, from_site_name: str):
        self.printer.change_head(f"Copying db_encryption_key from {from_bench_name}")

        site_config_path = (
            self.path.parent
            / from_bench_name
            / "workspace"
            / "frappe-bench"
            / "sites"
            / from_site_name
            / "site_config.json"
        )
        site_config_data = get_json(site_config_path)
        encryption_key = site_config_data.get('encryption_key', None)

        if encryption_key:
            current_site_config_path = self.current.sites / self.site_name / 'site_config.json'
            update_json_keys_in_file_path(current_site_config_path,{"backup_encryption_key": encryption_key})
            self.printer.print(f"Copyied ncryption_key from {from_bench_name}")


    def sync_configs_with_files(self, site_name: str):
        self.printer.change_head("Updating common_site_config.json, site_config.json")
        common_site_config_path = self.current.sites / "common_site_config.json"

        site_config_path = (
            self.current.sites
            / site_name
            / "site_config.json"
        )

        if self.config.common_site_config:
            update_json_keys_in_file_path(common_site_config_path, self.config.common_site_config)

        if self.config.site_config:
            update_json_keys_in_file_path(site_config_path, self.config.site_config)

        self.printer.print("Updated common_site_config.json, site_config.json")

    def bench_clear_cache(self, bench_directory: BenchDirectory, website_cache: bool = False):
        clear_cache_command = [self.bench_cli, 'clear-cache']
        clear_website_cache_command = [self.bench_cli, 'clear-website-cache']

        self.printer.change_head(f"Clearing cache{' and website cache' if website_cache else ''}")
        for command in [clear_cache_command,clear_website_cache_command]:
            self.host_run(
                command,
                bench_directory,
                #stream=True,
                container=self.mode == "fm",
                capture_output=False,
            )
            self.printer.print(f"{' '.join(command)} done")

    def get_script_env(self) -> dict[str, str]:
        """Get environment variables for scripts with config values"""
        env = {}

        # Add computed properties first
        computed_props = {
            "SITE_NAME": self.site_name,
            "BENCH_PATH": str(self.bench_path),
            "MODE": self.mode,
            "DEPLOY_PATH": str(self.config.deploy_dir_path),
            "APPS": ",".join(d.name for d in self.current.apps.iterdir() if d.is_dir())
        }
        env.update(computed_props)

        # Get all fields from Config class
        config_fields = self.config.__class__.model_fields

        # Add environment variables for each config field
        for field_name, field in config_fields.items():
            value = getattr(self.config, field_name, None)
            if value is not None:  # Skip None values
                env_key = field_name.upper()
                
                # Handle different types of values
                if isinstance(value, list) and value and isinstance(value[0], BaseModel):
                    # Handle list of Pydantic models
                    import json
                    env[env_key] = json.dumps([item.model_dump() for item in value])
                elif isinstance(value, dict):
                    import json
                    env[env_key] = json.dumps(value)
                elif isinstance(value, Path):
                    env[env_key] = str(value)
                elif isinstance(value, bool):
                    env[env_key] = str(value).lower()
                elif isinstance(value, (BaseModel, AppConfig, FMConfig, HostConfig)):
                    # Handle single Pydantic model
                    import json
                    env[env_key] = json.dumps(value.model_dump())
                else:
                    env[env_key] = str(value)

        return env

    def _run_script(self, script_content: str, bench_directory: BenchDirectory, 
                   script_type: str, container: bool = False) -> None:
        """Execute a shell script with proper setup and cleanup."""
        self.printer.change_head(f"Running {script_type}")
        
        # Create deployment_tmp directory in bench directory
        script_dir = self.current.path.parent / "deployment_tmp"
        script_dir.mkdir(parents=True, exist_ok=True)
        
        # Create unique script name
        script_name = f"temp_script_{int(time.time())}.sh"
        script_path = script_dir / script_name
        
        try:
            # Write script content
            with open(script_path, 'w') as script_file:
                script_file.write("set -e\n")  # Remove shebang, just keep error handling
                script_file.write(script_content)
            
            script_path.chmod(0o755)
            
            # Adjust script path for container execution
            if container:
                container_script_path = f"/workspace/deployment_tmp/{script_name}"
                workdir = f"/workspace/deployment_tmp"
            else:
                container_script_path = str(script_path)
                workdir = str(script_dir)
            
            # Get script environment variables
            script_env = self.get_script_env()
            
            # Execute script using bash explicitly
            output = self.host_run(
                ["bash", container_script_path],
                bench_directory,
                container=container,
                capture_output=True,
                workdir=workdir,
                env=script_env
            )
            
            # Print output
            if output and output.combined:
                for line in output.combined:
                    if line.strip():
                        self.printer.print(line.strip())
            self.printer.print(f"{script_type} done")

        finally:
            # Cleanup
            try:
                if script_path.exists():
                    script_path.unlink()
                    if not any(script_dir.iterdir()):  # If directory is empty
                        script_dir.rmdir()  # Remove the deployment_tmp directory
            except Exception as e:
                self.printer.warning(f"Failed to cleanup temporary script: {e}")

    def _run_bench_migrate(self, bench_directory: BenchDirectory) -> None:
        """Run bench migrate command if configured."""
        if not self.config.run_bench_migrate:
            self.printer.print("Skipped. Bench migrate")
            return

        self.printer.change_head("Running bench migrate")
        self.host_run(
            [self.bench_cli, "migrate"],
            bench_directory,
            container=self.mode == "fm",
            capture_output=False,
        )
        self.printer.print("Bench migrate done")

    def _install_app(self, app_path: Path, bench_directory: BenchDirectory) -> None:
        """Install a single app if not already installed."""
        app_python_module_name = bench_directory.get_app_python_module_name(app_path)
        
        if self.is_app_installed_in_site(self.site_name, app_python_module_name):
            self.printer.print(f"App {app_python_module_name} is already installed.")
            return

        self.printer.change_head(f"Installing app {app_python_module_name} in {self.site_name}")
        install_command = [
            self.bench_cli, "--site", self.site_name, "install-app", app_python_module_name
        ]
        
        output = self.host_run(
            install_command,
            bench_directory,
            container=self.mode == "fm",
            capture_output=True,
        )

        if f"App {app_python_module_name} already installed" in output.combined:
            self.printer.print(f"App {app_python_module_name} is already installed.")
        else:
            self.printer.print(f"Installed app {app_python_module_name} in {self.site_name}")

    def bench_install_and_migrate(self, bench_directory: BenchDirectory) -> None:
        """Main function to handle installation and migration process."""

        # Run pre-scripts
        if self.config.host_pre_script:
            self._run_script(self.config.host_pre_script, bench_directory, "host pre-script")
        
        if self.mode == "fm" and self.config.fm_pre_script:
            self._run_script(self.config.fm_pre_script, bench_directory, "FM pre-script", container=True)

        # Run bench migrate
        self._run_bench_migrate(bench_directory)

        # Run post-scripts
        if self.mode == "fm" and self.config.fm_post_script:
            self._run_script(self.config.fm_post_script, bench_directory, "FM post-script", container=True)
        
        if self.config.host_post_script:
            self._run_script(self.config.host_post_script, bench_directory, "host post-script")

        # Install apps
        apps = [d for d in bench_directory.apps.iterdir() if d.is_dir()]
        for app in apps:
            self._install_app(bench_directory.apps / app.name, bench_directory)

    def host_run(
        self,
        command: list[str],
        bench_directory: BenchDirectory,
        container: bool = False,
        container_service: str = "frappe",
        container_user: str = "frappe",
        capture_output: bool = True,
        workdir: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
    ) -> Union[Iterable[Tuple[str, bytes]], SubprocessOutput]:
        if self.verbose:
            start_time = time.time()

        # Prepare environment variables
        import os
        base_env = os.environ.copy()
        if env:
            base_env.update(env)

        # Convert env dict to proper format for container
        formatted_env = None
        if env and container:
            formatted_env = [f"{key}={value}" for key, value in env.items()]

        if not container:
            if capture_output:
                output = run_command_with_exit_code(
                    command,
                    stream=not capture_output,
                    capture_output=capture_output,
                    cwd=str(bench_directory.path.absolute()),
                    env=base_env  # Pass merged environment for host execution
                )

                if self.verbose:
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    self.printer.print(
                        f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",
                        emoji_code=":robot_face:"
                    )
                return output

            else:
                output = run_command_with_exit_code(
                    command,
                    stream=not capture_output,
                    capture_output=capture_output,
                    cwd=str(bench_directory.path.absolute()),
                )

                self.printer.live_lines(output,lines=10)

                if self.verbose:
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    self.printer.print(
                        f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",
                        emoji_code=":robot_face:"
                    )
                return None

        docker_command = " ".join(command)

        workdir = workdir or f"/workspace/{bench_directory.path.name}"

        compose_file: ComposeFile = ComposeFile(self.path.parent / "docker-compose.yml")
        compose_project: ComposeProject = ComposeProject(
            compose_file_manager=compose_file
        )

        if capture_output:
            output: SubprocessOutput = compose_project.docker.compose.exec(
                service=container_service,
                command=docker_command,
                user=container_user,
                workdir=workdir,
                stream=not capture_output,
                env=formatted_env  # Pass formatted list for docker execution
            )

            if self.verbose:
                end_time = time.time()
                elapsed_time = end_time - start_time
                self.printer.print(
                    f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",
                    emoji_code=":robot_face:",
                )

            return output

        else:
            output: Iterable[Tuple[str, bytes]] = compose_project.docker.compose.exec(
                service=container_service,
                command=docker_command,
                user=container_user,
                workdir=workdir,
                stream=not capture_output,
                env=formatted_env  # Pass formatted list for docker execution
            )
            self.printer.live_lines(output)

            if self.verbose:
                end_time = time.time()
                elapsed_time = end_time - start_time
                self.printer.print(
                    f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",
                    emoji_code=":robot_face:",
                )

    def configure_uv(self, bench_directory: BenchDirectory):
        if self.config.uv:
            try:
                # First check if uv is already installed
                check_uv = None
                try:
                    check_uv = self.host_run(
                        ["which", "uv"],
                        bench_directory,
                        container=self.mode == "fm",
                        capture_output=True,

                    )
                except DockerException:
                    pass

                # If which command returns nothing, uv is not installed
                if not check_uv or not check_uv.combined:
                    output = self.host_run(
                        ["pip", "install", "uv"],
                        bench_directory,
                        container=self.mode == "fm",
                        capture_output=True,
                    )
            except DockerException:
                shutil.rmtree(bench_directory.env)
                self.python_env_create(bench_directory)

    def python_env_create(
            self, bench_directory: BenchDirectory, venv_path: str = 'env', python_version: Optional[str] = None
    ):
        python_version = self.config.python_version if self.config.python_version else "3"

        venv_create_command = [f"python{python_version}", "-m", "venv", venv_path]

        self.printer.change_head(
            f"Creating python venv {'using uv' if self.config.uv else ''}"
        )

        if self.config.uv:
            # First check if uv is already installed
            check_uv = None
            try:
                check_uv = self.host_run(
                    ["which", "uv"],
                    bench_directory,
                    container=self.mode == "fm",
                    capture_output=True,

                )
            except DockerException:
                pass

            # If which command returns nothing, uv is not installed
            if not check_uv or not check_uv.combined:
                output = self.host_run(
                    ["pip", "install", "uv"],
                    bench_directory,
                    container=self.mode == "fm",
                    capture_output=True,
                )

            venv_create_command = [
                "uv",
                "venv",
                "--python",
                f"python{python_version}",
                venv_path,
            ]

        output = self.host_run(
            venv_create_command,
            bench_directory,
            #stream=False,
            container=self.mode == "fm",
            capture_output=True,
        )

        pkg_install = [f"{venv_path}/bin/python", "-m", "pip", "install", "wheel"]

        if self.config.uv:
            pkg_install = [
                "uv",
                "pip",
                "install",
                "--python",
                f"{venv_path}/bin/python",
                "-U",
                "pip",
            ]

        output = self.host_run(
            pkg_install,
            bench_directory,
            #stream=False,
            container=self.mode == "fm",
            capture_output=True,
        )
        output = self.host_run(
            [f"{venv_path}/bin/python", "--version"],
            bench_directory,
            #stream=False,
            container=self.mode == "fm",
            capture_output=True,
        )
        self.printer.print(
            f"Created {output.combined[-1]} env {'using uv' if self.config.uv else ''}"
        )

    def bench_install_all_apps_in_python_env(self, bench_directory: BenchDirectory):
        self.printer.change_head(
            f"Installing all apps in python env {'using uv' if self.config.uv else ''}"
        )

        install_cmd = [self.bench_cli, "setup", "requirements", "--python"]

        if self.config.uv:
            install_cmd = [
                "uv",
                "pip",
                "install",
                "--python",
                "env/bin/python",
                "-U",
                "-e",
            ]
            apps = [d for d in bench_directory.apps.iterdir() if d.is_dir()]
            for app in apps:
                self.host_run(
                    install_cmd + [f"apps/{app.name}"],
                    bench_directory,
                    #stream=False,
                    container=self.mode == "fm",
                    capture_output=False,
                )
        else:
            self.host_run(
                install_cmd,
                bench_directory,
                #stream=False,
                container=self.mode == "fm",
                capture_output=False,
            )

        self.printer.print("Installed apps in python env")

    def bench_setup_requiments(self, bench_directory: BenchDirectory):
        node_cmd = [self.bench_cli, "setup", "requirements", "--node"]

        self.printer.change_head("Installing all apps node packages")

        output = self.host_run(
            node_cmd,
            bench_directory,
            #stream=True,
            container=self.mode == "fm",
            capture_output=False,
        )

        self.printer.print("Installed all apps node packages")

        start_time = time.time()

        self.bench_install_all_apps_in_python_env(bench_directory)

        end_time = time.time()
        elapsed_time = end_time - start_time
        self.printer.print(f"Apps python env install time: {elapsed_time:.2f} seconds")

        self.printer.change_head("Configuring apps.txt")
        # Get all directory names in bench_directory.apps
        apps_dir = bench_directory.apps
        app_names = [d.name for d in apps_dir.iterdir() if d.is_dir()]

        # Save the list to bench_directory.sites / 'apps.txt'
        apps_txt_path = bench_directory.sites / "apps.txt"
        apps_txt_path.parent.mkdir(
            parents=True, exist_ok=True
        )  # Ensure the directory exists

        with apps_txt_path.open("w") as f:
            for app_name in app_names:
                app_name = bench_directory.get_app_python_module_name(
                    bench_directory.apps / app_name
                )
                f.write(f"{app_name}\n")
        self.printer.print("Configured apps.txt")

    def bench_build(self, bench_directory: BenchDirectory):
        #apps: list[Union[AppConfig, Path]] = self.apps

        apps = [d for d in bench_directory.apps.iterdir() if d.is_dir()]

        for app in apps:
            self.printer.change_head(f"Building app {app.name}")
            
            # Find corresponding AppConfig for the app to check for pre/post build commands
            app_config = None
            for config in self.apps:
                app_name = bench_directory.get_app_python_module_name(bench_directory.apps / config.dir_name)
                if app_name == app.name:
                    app_config = config
                    break
            
            # Run pre-build command if configured and in FM mode
            if self.mode == "fm" and app_config and app_config.fm_pre_build:
                self.printer.print(f"Running pre-build command for {app.name}")
                self._run_script(
                    app_config.fm_pre_build,
                    bench_directory,
                    f"pre-build script for {app.name}",
                    container=True
                )
            
            # Run the regular build command
            build_cmd = [self.bench_cli, "build", "--app", app.name]
            self.host_run(
                build_cmd,
                bench_directory,
                #stream=False,
                container=self.mode == "fm",
                capture_output=False,
            )
            
            # Run post-build command if configured and in FM mode
            if self.mode == "fm" and app_config and app_config.fm_post_build:
                self.printer.print(f"Running post-build command for {app.name}")
                self._run_script(
                    app_config.fm_post_build,
                    bench_directory,
                    f"post-build script for {app.name}",
                    container=True
                )
            
            self.printer.print(f"Built app {app.name}")
        
        self.printer.print("Built all apps")

    def search_and_replace_in_database(
        self,
        search: str,
        replace: str,
        dry_run: bool = False,
        verbose: bool = False
    ) -> None:
        """
        Search and replace text across all text fields in the database.
        
        Args:
            search: Text to search for
            replace: Text to replace with
            dry_run: If True, only show what would be changed
            verbose: If True, show detailed output
        """
        try:
            # Copy search_replace.py to bench sites directory
            search_replace_script = Path(__file__).parent / 'search_replace.py'
            if not search_replace_script.exists():
                self.printer.exit(f"Search/replace script not found at {search_replace_script}")
                
            bench_script_path = self.current.sites / 'search_replace.py'
            shutil.copy2(search_replace_script, bench_script_path)
            
            try:
                # Build command for search/replace operation
                python_path = "../env/bin/python"
                search_replace_cmd = [
                    python_path,
                    "search_replace.py",
                    self.site_name,
                    search,
                    replace
                ]
                if dry_run:
                    search_replace_cmd.append('--dry-run')
                if verbose or self.config.verbose:
                    search_replace_cmd.append('--verbose')
                    
                # Run the command using host_run and capture output
                result = self.host_run(
                    search_replace_cmd,
                    self.current,
                    container=self.mode == "fm",
                    capture_output=True,
                    workdir=f"/workspace/{self.current.path.name}/sites" if self.mode == "fm" else str(self.current.sites.absolute())
                )
                
                # Print the output with proper formatting
                if result.combined:
                    for line in result.combined:
                        if line.strip():
                            self.printer.print(line.strip())
                
            finally:
                # Cleanup - remove the copied script
                if bench_script_path.exists():
                    bench_script_path.unlink()
                    
        except Exception as e:
            self.printer.warning(f"Failed to perform search and replace: {str(e)}")

    def bench_symlink_and_restart(self, bench_directory: BenchDirectory):
        self.printer.change_head("Symlinking and restarting")

        if self.bench_path.exists():
            self.bench_path.unlink()

        self.bench_path.symlink_to(
            get_relative_path(self.bench_path, bench_directory.path), True
        )


        start_time = time.time()

        if self.mode == "fm":
            restart_cmd = [self.fm_helper_cli, "restart"]
            self.host_run(
                restart_cmd,
                bench_directory,
                container=True,
                capture_output=False,
            )
        else:
            services_to_restart = ['workers', 'web']
            for service in services_to_restart:
                command = ["sudo", "supervisorctl", "restart", f"frappe-bench-{service}:"]
                self.host_run(
                    command,
                    bench_directory,
                    #stream=False,
                    container=False,
                    capture_output=False,
                )

        if self.config.verbose:
            end_time = time.time()
            elapsed_time = end_time - start_time
            self.printer.print(f"Frappe Services Restart Time Taken: {human_readable_time(elapsed_time)}", emoji_code = ":robot_face:")

        self.printer.start("Working")
        self.printer.print("Symlinked and restarted")

    def get_site_installed_apps(self, bench_directory: BenchDirectory):
        command = [self.bench_cli, "list-apps", "-f", "json"]
        try:
            output = self.host_run(
                command,
                bench_directory,
                #stream=False,
                container=self.mode == "fm",
                capture_output=True,
            )
        except DockerException as e:
            self.printer.warning(
                f"Not able to get current list of apps installed in {self.site_name}"
            )
            return {self.site_name: []}
        return json.loads("".join(output.combined))

    def is_app_installed_in_site(self, site_name: str, app_name: str) -> bool:
        site_apps = self.site_installed_apps.get(site_name)

        if not site_apps:
            return False

        if app_name in site_apps:
            return True

        return False

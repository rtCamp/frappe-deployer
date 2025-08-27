import socket
import subprocess
import json
import shutil
from frappe_manager.docker_wrapper.DockerException import DockerException
import requests
import re
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from frappe_deployer.helpers import get_relative_path
from frappe_deployer.ssh import ssh_run


if TYPE_CHECKING:
    from frappe_deployer.deployment_manager import DeploymentManager
import frappe_manager
from frappe_manager.docker_wrapper.DockerClient import shlex
from frappe_manager.logger.log import richprint

from .fmbench import FMServicesManager, FMBench


def get_current_ip() -> str:
    """Get the current public IP address of the server.
    
    Returns:
        str: Public IP address of the server
    """
    response = requests.get('https://api.ipify.org')
    return response.text

def find_available_port(start_port: int = 11000) -> Optional[int]:
    """Find first available port not used by any bench's redis-queue service.

    Checks all benches in the FM sites directory and finds the first available port
    after 11000 that isn't assigned to any redis-queue service.

    Args:
        start_port: Starting port number to check from (default: 11000)

    Returns:
        Optional[int]: First available port, or None if no ports are available
    """
    from pathlib import Path
    import frappe_manager
    from frappe_manager.compose_manager.ComposeFile import ComposeFile

    used_ports = set()

    # Check all benches in FM directory
    benches_dir = frappe_manager.CLI_BENCHES_DIRECTORY
    if benches_dir.exists():
        for bench_dir in benches_dir.iterdir():
            if not bench_dir.is_dir():
                continue

            compose_file_path = bench_dir / "docker-compose.yml"
            if not compose_file_path.exists():
                continue

            try:
                compose_file = ComposeFile(compose_file_path)
                services = compose_file.yml.get("services", {})
                redis_queue = services.get("redis-queue", {})

                # Check for port mapping in redis-queue service
                ports = redis_queue.get("ports", [])
                for port_mapping in ports:
                    if isinstance(port_mapping, str):
                        # Handle all possible Docker port mapping formats:
                        # - "ip:host_port:container_port"
                        # - "host_port:container_port"
                        # - "host_port"
                        parts = port_mapping.split(":")
                        if len(parts) == 3:  # ip:host:container format
                            host_port = parts[1]
                        elif len(parts) == 2:  # host:container format
                            host_port = parts[0]
                        else:  # just host format
                            host_port = parts[0]

                        # Remove any IP prefix if present
                        if host_port.startswith("0.0.0.0:"):
                            host_port = host_port[8:]  # Remove "0.0.0.0:" prefix
                        try:
                            port = int(host_port)
                            used_ports.add(port)
                        except ValueError:
                            continue
            except Exception:
                continue

    # Find first available port
    current_port = start_port
    while current_port < 65535:
        if current_port not in used_ports:
            # Double check with socket binding
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(("", current_port))
                sock.close()
                return current_port
            except OSError:
                current_port += 1
            finally:
                sock.close()
        else:
            current_port += 1

    return None


def is_remote_worker_enabled(site_name: str) -> bool:
    """Check if remote worker is already enabled for a site."""
    import frappe_manager
    from .fmbench import FMServicesManager, FMBench

    # Check global-db configuration
    services_manager = FMServicesManager()
    global_db_config = services_manager.compose_project.compose_file_manager.yml.get("services", {}).get("global-db", {})
    if not global_db_config.get("ports"):
        return False

    db_port_exposed = any("3306:3306" in port for port in global_db_config["ports"])
    if not db_port_exposed:
        return False

    # Check redis-queue configuration for the site
    bench_path = frappe_manager.CLI_BENCHES_DIRECTORY / site_name
    if not bench_path.exists():
        return False

    bench = FMBench(name=site_name, path=bench_path)
    redis_queue_config = bench.compose_project.compose_file_manager.yml.get("services", {}).get("redis-queue", {})
    if not redis_queue_config.get("ports"):
        return False

    return True


def enable_remote_worker(site_name: str) -> None:
    """Enable remote worker for a site by configuring ports"""
    # Find available port for redis-queue
    queue_port = find_available_port()

    if not queue_port:
        richprint.exit("No available ports found")

    # configure site compose to do this

    bench_path = frappe_manager.CLI_BENCHES_DIRECTORY / site_name
    bench = FMBench(name=site_name, path=bench_path)
    services_manager = FMServicesManager()

    # open global-db
    services_manager.compose_project.compose_file_manager.yml["services"]["global-db"]["ports"] = ["0.0.0.0:3306:3306"]
    try:
        del services_manager.compose_project.compose_file_manager.yml["services"]["global-db"]["expose"]
    except KeyError:
        pass
    services_manager.compose_project.compose_file_manager.write_to_file()
    services_manager.compose_project.start_service(services=["global-db"])

    # open redis-queue port
    bench.compose_project.compose_file_manager.yml["services"]["redis-queue"]["ports"] = [f"0.0.0.0:{queue_port}:6379"]
    try:
        del bench.compose_project.compose_file_manager.yml["services"]["redis-queue"]["expose"]
    except KeyError:
        pass
    bench.compose_project.compose_file_manager.write_to_file()
    bench.compose_project.start_service(services=["redis-queue"])



def get_redis_queue_remote_url(site_name: str) -> str:
    """Get Redis queue URL with the exposed port from docker-compose configuration

    Args:
        site_name: Name of the site/bench

    Returns:
        str: Redis URL in format redis://host:port
    """
    bench_path = frappe_manager.CLI_BENCHES_DIRECTORY / site_name
    bench = FMBench(name=site_name, path=bench_path)

    # Get redis-queue service configuration
    redis_config = bench.compose_project.compose_file_manager.yml["services"]["redis-queue"]

    port_mapping = redis_config["ports"][0]
    exposed_port = port_mapping.split(":")[1]

    return f"redis://{get_current_ip()}:{exposed_port}"


def create_worker_site_config(deployment_manager: "DeploymentManager", force: bool = False) -> None:
    """Create a worker-specific common site config with remote Redis queue URL.

    This creates a copy of common_site_config.json in the deployment data directory
    with the Redis queue URL updated to point to the remote Redis instance.

    Args:
        deployment_manager: The deployment manager instance
        force: If True, overwrite existing config files. If False, skip if files exist.
    """
    deployment_manager.printer.change_head("Creating worker site config")

    # Source config files
    source_common = deployment_manager.data.sites / "common_site_config.json"
    target_common = deployment_manager.data.sites / "common_site_config.workers.json"
    
    source_site = deployment_manager.data.sites / deployment_manager.config.site_name / "site_config.json"
    target_site = deployment_manager.data.sites / deployment_manager.config.site_name / "site_config.workers.json"

    # Check if files already exist and force flag is not set
    if not force and target_common.exists() and target_site.exists():
        deployment_manager.printer.print("Worker configs already exist. Skipping creation.")
        return

    try:
        # Copy existing configs
        shutil.copy2(source_common, target_common)
        shutil.copy2(source_site, target_site)

        # Update common config with Redis queue URL
        with open(target_common) as f:
            common_config = json.load(f)

        redis_url = get_redis_queue_remote_url(deployment_manager.config.site_name)
        common_config.update({"redis_queue": redis_url})

        with open(target_common, "w") as f:
            json.dump(common_config, f, indent=4)

        # Update site config with db_host
        with open(target_site) as f:
            site_config = json.load(f)

        site_config.update({"db_host": get_current_ip()})

        with open(target_site, "w") as f:
            json.dump(site_config, f, indent=4)

        deployment_manager.printer.print(f"Created worker configs with Redis queue URL: {redis_url}")

    except Exception as e:
        deployment_manager.printer.warning(f"Failed to create worker config: {str(e)}")
        if target_common.exists():
            target_common.unlink()
        if target_site.exists():
            target_site.unlink()
        raise

def stop_all_compose_services(deployment_manager: "DeploymentManager") -> None:
    remote_bench_path = (
        Path(deployment_manager.config.remote_worker.fm_benches_path) / deployment_manager.config.site_name
    )
    richprint.change_head("Stop all remote-worker services")

    # Stop regular compose services
    ssh_run(
        deployment_manager,
        ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.workers.yml", "down", "--timeout" , "10"],
        workdir=str(remote_bench_path),
        capture_output=True,
    )

    richprint.print("Stoped all remote-worker services")

def only_start_workers_compose_services(deployment_manager: "DeploymentManager") -> None:
    """Switch Docker Compose configuration on remote worker to use worker-specific compose file.

    This stops the regular docker-compose.yml services and starts docker-compose.workers.yml

    Args:
        deployment_manager: The deployment manager instance
    """

    richprint.change_head("Stopping all services other than workers")

    remote_bench_path = (
        Path(deployment_manager.config.remote_worker.fm_benches_path) / deployment_manager.config.site_name
    )

    # Stop regular compose services
    ssh_run(
        deployment_manager,
        ["docker", "compose", "-f", "docker-compose.yml", "down"],
        workdir=str(remote_bench_path),
        capture_output=True,
    )

    ssh_run(
        deployment_manager,
        ["docker", "compose", "-f", "docker-compose.yml", "up", "-d", "schedule"],
        workdir=str(remote_bench_path),
        capture_output=True,
    )

    richprint.change_head("Starting if not started remote-worker services")

    # Start worker compose services
    ssh_run(
        deployment_manager,
        ["docker", "compose","-f", "docker-compose.workers.yml", "up", "-d"],
        workdir=str(remote_bench_path),
        capture_output=True,
    )
    richprint.print("Strated if not started remote-worker services")


    richprint.change_head("Restarting remote-worker services")

    # Start worker compose services
    ssh_run(
        deployment_manager,
        ["docker", "compose", "-f", "docker-compose.workers.yml", "restart"],
        workdir=str(remote_bench_path),
        capture_output=True,
    )


def handle_frappe_bench_symlink(deployment_manager: "DeploymentManager", remote_base_path: Path, remote_bench_path: Path) -> str:
    """Handle the frappe-bench symlink creation and target directory management.
    
    Args:
        deployment_manager: The deployment manager instance
        remote_base_path: Base path on remote server
        remote_bench_path: Path to frappe-bench directory
        
    Returns:
        str: Name of the new target directory
    """
    try:
        readlink_cmd = ["readlink", str(remote_bench_path)]
        result = ssh_run(deployment_manager, readlink_cmd, capture_output=True)
        current_target = result.combined[-1].strip()
        is_symlink = True
    except Exception:
        current_target = None
        is_symlink = False

    new_target = deployment_manager.current.path.readlink().name

    if is_symlink:
        # Unlink existing symlink 
        ssh_run(deployment_manager, ["unlink", str(remote_bench_path)], capture_output=True)
        
        # Move target directory if different
        if current_target != new_target:
            ssh_run(
                deployment_manager, 
                ["mv", current_target, new_target],
                workdir=str(remote_base_path),
                capture_output=True
            )
    else:
        # Move existing directory to new name
        ssh_run(
            deployment_manager,
            ["mv", "frappe-bench", new_target],
            workdir=str(remote_base_path),
            capture_output=True
        )

    # Create new symlink
    ssh_run(
        deployment_manager,
        ["ln", "-sfn", new_target, "frappe-bench"],
        workdir=str(remote_base_path),
        capture_output=True
    )
    deployment_manager.printer.print(f"Linked frappe-bench to {new_target}")
    return new_target

def create_required_directories(deployment_manager: "DeploymentManager", remote_base_path: Path) -> None:
    """Create required directories on the remote server.
    
    Args:
        deployment_manager: The deployment manager instance
        remote_base_path: Base path on remote server
    """
    dirs_which_should_always_be_there = [
        f'deployment-data/sites/{deployment_manager.config.site_name}/private/files',
        f'deployment-data/sites/{deployment_manager.config.site_name}/public/files',
        'frappe-bench/config/pids'
    ]

    for dir_path in dirs_which_should_always_be_there:
        ssh_run(
            deployment_manager,
            ["mkdir", "-p", dir_path],
            workdir=str(remote_base_path),
            capture_output=True
        )
        deployment_manager.printer.print(f"Created directory: {dir_path}")

def create_config_symlink(
    deployment_manager: "DeploymentManager",
    remote_bench_path: Path,
    source_path: Path,
    target_path: Path,
    remote_path: Path,
    config_type: str
) -> None:
    """Create a symlink for a config file.
    
    Args:
        deployment_manager: The deployment manager instance
        remote_bench_path: Path to frappe-bench directory
        source_path: Source config file path
        target_path: Target config file path
        remote_path: Remote config file path
        config_type: Type of config file for logging
    """
    relative_path = get_relative_path(target_path, source_path)
    link_command = [
        "ln",
        "-sf",
        str(relative_path),
        str(remote_path),
    ]
    ssh_run(deployment_manager, link_command, workdir=str(remote_bench_path), capture_output=True)
    deployment_manager.printer.print(f"Linked {config_type} to {str(relative_path)}")

def link_worker_configs(deployment_manager: "DeploymentManager") -> None:
    """Link worker-specific config files to the bench directory on remote worker.

    This creates symbolic links from the worker config files in the data directory
    to the actual bench sites directory on the remote worker, and handles frappe-bench linking.

    Args:
        deployment_manager: The deployment manager instance
    """
    remote_base_path = (
        Path(deployment_manager.config.remote_worker.fm_benches_path)
        / deployment_manager.config.site_name
        / "workspace"
    )
    remote_bench_path = remote_base_path / "frappe-bench"

    # Handle frappe-bench symlink
    handle_frappe_bench_symlink(deployment_manager, remote_base_path, remote_bench_path)

    # Create required directories
    create_required_directories(deployment_manager, remote_base_path)

    try:
        # Link common site config
        deployment_manager.printer.change_head("Linking common_site_config.json")
        create_config_symlink(
            deployment_manager,
            remote_bench_path,
            deployment_manager.data.sites / "common_site_config.workers.json",
            deployment_manager.current.sites / "common_site_config.json",
            remote_bench_path / "sites" / "common_site_config.json",
            "common_site_config.json"
        )

        # Link site config
        deployment_manager.printer.change_head("Linking site_config.json")
        create_config_symlink(
            deployment_manager,
            remote_bench_path,
            deployment_manager.data.sites / deployment_manager.config.site_name / "site_config.workers.json",
            deployment_manager.current.sites / deployment_manager.config.site_name / "site_config.json",
            remote_bench_path / "sites" / deployment_manager.config.site_name / "site_config.json",
            "site_config.json"
        )

        deployment_manager.printer.print("[green]Successfully linked worker config files[/green]")
    except Exception as e:
        deployment_manager.printer.warning(f"Failed to link worker configs: {str(e)}")
        raise


def parse_included_paths(deployment_manager: "DeploymentManager") -> list[dict]:
    """Parse include_dirs and include_files from RemoteWorkerConfig into rsync format
    
    Args:
        deployment_manager: The deployment manager instance
    
    Returns:
        list[dict]: List of directory/file configurations for rsync
    """
    result = []
    
    # Process include_dirs
    for dir_path in deployment_manager.config.remote_worker.include_dirs:
        result.append({
            "src": deployment_manager.current.path.parent / dir_path,
            "dest": dir_path,
            "exclude": ["--mkpath"],
            "type": "d"
        })
    
    # Process include_files
    for file_path in deployment_manager.config.remote_worker.include_files:
        result.append({
            "src": deployment_manager.current.path.parent / file_path,
            "dest": file_path,
            "exclude": [],
            "type": "f"
        })
    
    return result

def get_rsync_patterns() -> list[str]:
    """Get the default rsync exclude patterns.
    
    Returns:
        list[str]: List of rsync exclude patterns
    """
    return [
        # Exclude specific problematic directories
        "--exclude=**/.git/***",
        "--exclude=**/node_modules/***",
        "--exclude=**/__pycache__/***",
        "--exclude=**/.pytest_cache/***",
        "--exclude=**/.cache/***",
        # Exclude common problematic files
        "--exclude=*.pyc",
        "--exclude=*.pyo",
        "--exclude=*.pyd",
        "--exclude=.DS_Store",
        "--exclude=*.log",
        "--exclude=*.swp",
        "--exclude=*.swo",
        "--exclude=*.sql",
    ]

def get_base_rsync_dirs(deployment_manager: "DeploymentManager") -> list[dict]:
    """Get the base rsync directory configurations.
    
    Args:
        deployment_manager: The deployment manager instance
    
    Returns:
        list[dict]: List of base directory configurations
    """
    site_name = deployment_manager.config.site_name
    return [
        {"src": deployment_manager.current.path, "exclude": [], "type": "d"},
        {
            "src": deployment_manager.data.path,
            "type": 'd',
            "exclude": [
                f"--exclude=sites/{site_name}/public/files/***",
                f"--exclude=sites/{site_name}/private/***",
            ],
        },
    ]

def build_rsync_command(
    src_dir: str, 
    target_path: str, 
    dest_dir: str, 
    rsync_patterns: list[str], 
    dir_excludes: list[str]
) -> list[str]:
    """Build the rsync command with all necessary options.
    
    Args:
        src_dir: Source directory path
        target_path: Remote target path
        dest_dir: Destination directory name
        rsync_patterns: Global exclude patterns
        dir_excludes: Directory-specific excludes
    
    Returns:
        list[str]: Complete rsync command as list
    """
    return [
        "rsync",
        "-avz",  # archive mode and compress
        "--delete",  # delete extraneous files from destination
        "--checksum",  # skip based on checksum, not mod-time & size
        *rsync_patterns,  # Global patterns
        *dir_excludes,  # Directory-specific excludes
        f"{src_dir}",  # Source directory with trailing slash
        f"{target_path}/{dest_dir}",  # Target directory with trailing slash
    ]

def rsync_workspace(deployment_manager: "DeploymentManager") -> None:
    """Sync workspace to remote worker server using fastest rsync options.

    Args:
        deployment_manager: Deployment manager instance with config
    """
    site_name = deployment_manager.config.site_name
    server = deployment_manager.config.remote_worker.server_ip
    ssh_user = deployment_manager.config.remote_worker.ssh_user

    source_path = frappe_manager.CLI_BENCHES_DIRECTORY / site_name / "workspace"
    target_path = f"{ssh_user}@{server}:{deployment_manager.config.remote_worker.fm_benches_path}/{site_name}/workspace"

    # Get base directories and include paths from config
    rsync_dirs = get_base_rsync_dirs(deployment_manager)
    rsync_dirs.extend(parse_included_paths(deployment_manager))

    # Get global rsync patterns
    rsync_patterns = get_rsync_patterns()

    deployment_manager.printer.print(f"Starting rsync files")

    # Process each directory configuration
    for dir_config in rsync_dirs:
        src_dir = dir_config['src']

        if not src_dir.exists():
            deployment_manager.printer.print(f"[yellow]Skipping: {src_dir.absolute()} (directory not found)[/yellow]")
            continue

        # Prepare source and destination paths
        src_dir_str = str(src_dir)
        dest_dir = str(dir_config['src'].name if dir_config.get('dest', None) is None else dir_config['dest'])

        if dir_config['type'] == 'd':
            src_dir_str += '/'
            dest_dir += '/'

        # Build and execute rsync command
        rsync_cmd = build_rsync_command(
            src_dir_str,
            target_path,
            dest_dir,
            rsync_patterns,
            dir_config["exclude"]
        )
        richprint.change_head(f"Syncing: {dest_dir}")
        deployment_manager.host_run(
            rsync_cmd,
            deployment_manager.current,
            container=False,
            capture_output=False,
        )
        richprint.print(f"Synced {dest_dir}", emoji_code='[green]✓[/green]')

    deployment_manager.printer.print("[green]Remote sync completed successfully[/green]")

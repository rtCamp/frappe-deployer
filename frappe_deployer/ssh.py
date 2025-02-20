import os
import time
from typing import Iterable, Optional, Tuple, Union, TYPE_CHECKING
from pathlib import Path

import json
from frappe_manager.utils.docker import SubprocessOutput, run_command_with_exit_code
from frappe_deployer.release_directory import BenchDirectory

if TYPE_CHECKING:
    from frappe_deployer.deployment_manager import DeploymentManager

def ssh_run(
    deployment_manager: 'DeploymentManager',
    command: list[str],
    capture_output: bool = True,
    workdir: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
) -> Union[Iterable[Tuple[str, bytes]], SubprocessOutput, None]:
    """
    Run commands on remote server via SSH using configuration from deployment manager.
    
    Args:
        deployment_manager: DeploymentManager instance containing configuration
        command: List of command parts to execute
        capture_output: Whether to capture command output
        workdir: Working directory for command execution
        env: Environment variables to pass to command
        
    Returns:
        Command output if capture_output is True, None otherwise
    """
    if deployment_manager.verbose:
        start_time = time.time()

    if not deployment_manager.config.remote_worker:
        raise ValueError("Remote worker configuration is required for SSH execution")

    # Prepare environment variables
    base_env = os.environ.copy()
    if env:
        base_env.update(env)

    # Construct SSH command
    remote_config = deployment_manager.config.remote_worker
    ssh_command = [
        "ssh",
        "-p", str(remote_config.ssh_port),
        f"{remote_config.ssh_user}@{remote_config.server}"
    ]

    # Add working directory if specified
    working_dir = workdir
    command_str = ""

    if workdir:
        command_str = f"cd {working_dir} && "

    command_str += f"{' '.join(command)}"

    # Add environment variables to command
    if env:
        env_str = " ".join(f"{k}={v}" for k, v in env.items())
        command_str = f"export {env_str} && {command_str}"

    # Complete SSH command
    ssh_command.append(command_str)

    if capture_output:
        output = run_command_with_exit_code(
            ssh_command,
            stream=not capture_output,
            capture_output=capture_output,
            env=base_env
        )

        if deployment_manager.verbose:
            end_time = time.time()
            elapsed_time = end_time - start_time
            deployment_manager.printer.print(
                f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",
                emoji_code=":robot_face:"
            )
        return output

    else:
        output = run_command_with_exit_code(
            ssh_command,
            stream=not capture_output,
            capture_output=capture_output,
            env=base_env
        )

        deployment_manager.printer.live_lines(output, lines=10)

        if deployment_manager.verbose:
            end_time = time.time()
            elapsed_time = end_time - start_time
            deployment_manager.printer.print(
                f"Time Taken: {elapsed_time:.2f} sec, Command: '{' '.join(command)}'",
                emoji_code=":robot_face:"
            )
        return None


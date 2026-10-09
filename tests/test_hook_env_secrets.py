"""Hook env must not put credentials on the docker command line, and failed docker
commands must not echo them back in their error message."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from frappe_manager.docker.docker_exceptions import DockerException
from frappe_manager.docker.subprocess_output import SubprocessOutput

from fmd.config.config import Config
from fmd.redact import redact, redact_command, scrub_secrets
from fmd.release_directory import BenchDirectory
from fmd.runner.docker import DockerRunner
from fmd.services.bench import BenchService

# Built at runtime so these fixtures do not trip gitleaks
TOKEN = "gho_" + "Ab1" * 12
FC_KEY = "fc-key-" + "1" * 8
FC_SECRET = "fc-secret-" + "2" * 8
SITE = "site.localhost"
REPO = "org/private-app"


class Printer:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


@pytest.fixture
def config():
    return Config(
        site_name=SITE,
        github_token=TOKEN,
        apps=[
            {
                "repo": REPO,
                "ref": "main",
                "repo_url": f"https://{TOKEN}@github.com/{REPO}",
                "exists": True,
                "before_bench_build": "npm ci",
            }
        ],
        fc={"api_key": FC_KEY, "api_secret": FC_SECRET, "site_name": "fc.site", "team_name": "team"},
    )


@pytest.fixture
def bench(tmp_path):
    bench = BenchDirectory(tmp_path / "release_20260101_000000")
    (bench.apps / "private-app").mkdir(parents=True)
    return bench


def service_for(config, mode="exec"):
    runner = DockerRunner(mode, config, verbose=False, printer=Printer())
    # Skips tagging the runner image in image mode
    runner._resolved_image = "frappe-runner-image"
    return BenchService(runner, None, config, Printer())


def failing_docker(calls):
    """Stands in for frappe_manager's run_command_with_exit_code when the command exits non-zero."""

    def run_command_with_exit_code(full_cmd, *args, **kwargs):
        calls.append(full_cmd)
        stdout = [f"Cloning into 'x'... https://{TOKEN}@github.com/{REPO}"]
        stderr = [f"fatal: token {TOKEN} rejected"]
        raise DockerException(full_cmd, SubprocessOutput(stdout, stderr, stdout + stderr, 1))

    return run_command_with_exit_code


# -- hook env construction ------------------------------------------------------


def test_container_hook_env_has_no_secrets(config, bench):
    env = service_for(config).get_script_env(bench.path, bench, SITE, "private-app")

    assert "GITHUB_TOKEN" not in env
    for key, value in env.items():
        assert TOKEN not in value, key
        assert FC_KEY not in value and FC_SECRET not in value, key

    apps = json.loads(env["APPS"])
    assert apps[0]["repo_url"] == f"https://github.com/{REPO}"
    assert apps[0]["repo"] == REPO
    assert apps[0]["before_bench_build"] == "npm ci"

    assert json.loads(env["FC"]) == {"site_name": "fc.site", "team_name": "team"}

    # everything else hooks may rely on is still there
    assert env["SITE_NAME"] == SITE
    assert env["BENCH_NAME"] == SITE
    assert env["APP_NAME"] == "private-app"
    assert env["BENCH_PATH"] == str(bench.path)
    assert env["VERBOSE"] == "false"
    assert "RELEASE" in env and "SWITCH" in env


def test_host_hook_env_keeps_secrets(config, bench):
    # host hooks get env through the subprocess environment, not argv
    env = service_for(config).get_script_env(bench.path, bench, SITE, "private-app", include_secrets=True)

    assert env["GITHUB_TOKEN"] == TOKEN
    assert json.loads(env["APPS"])[0]["repo_url"] == f"https://{TOKEN}@github.com/{REPO}"


def test_run_script_scrubs_only_container_hooks(config, bench, monkeypatch):
    service = service_for(config)
    seen = {}
    monkeypatch.setattr(service.runner, "run", lambda *args, **kwargs: seen.update(container=kwargs["env"]))

    def host_run(*args, **kwargs):
        seen["host"] = kwargs["env"]

    for container in (True, False):
        service._run_script("true", bench, bench, bench.path, SITE, host_run, "hook", container, "private-app")

    assert "GITHUB_TOKEN" not in seen["container"]
    assert seen["host"]["GITHUB_TOKEN"] == TOKEN


def test_scrub_secrets_strips_url_credentials_and_secret_keys():
    data = {
        "repo_url": f"https://{TOKEN}@github.com/{REPO}",
        "fmd_source": f"git+https://x-access-token:{TOKEN}@github.com/{REPO}",
        "ssh_url": "ssh://git@github.com/org/app.git",
        "scp_url": "git@github.com:org/app.git",
        "site_config": {"db_password": "hunter2", "host_name": "https://site.localhost"},
        "hook": f"npm config set //npm.pkg.github.com/:_authToken={TOKEN}",
    }

    assert scrub_secrets(data) == {
        "repo_url": f"https://github.com/{REPO}",
        "fmd_source": f"git+https://github.com/{REPO}",
        "ssh_url": "ssh://git@github.com/org/app.git",
        "scp_url": "git@github.com:org/app.git",
        "site_config": {"host_name": "https://site.localhost"},
        "hook": "npm config set //npm.pkg.github.com/:_authToken=*****",
    }


# -- redaction of echoed commands and errors --------------------------------------


def test_redact_command_masks_env_args_and_embedded_urls():
    apps = json.dumps([{"repo": REPO, "repo_url": f"https://{TOKEN}@github.com/{REPO}", "api_secret": FC_SECRET}])
    command = ["docker", "compose", "exec", "--env", f"GITHUB_TOKEN={TOKEN}", "--env", f"APPS={apps}"]
    command += ["--env", f"SITE_NAME={SITE}", "frappe", "bash", "/workspace/frappe-bench/.fmd_tmp/s.sh"]

    redacted = redact_command(command)

    assert TOKEN not in " ".join(redacted) and FC_SECRET not in " ".join(redacted)
    assert redacted[4] == "GITHUB_TOKEN=*****"
    assert f"https://*****@github.com/{REPO}" in redacted[6]
    assert redacted[7:] == command[7:]


def test_redact_masks_bare_github_tokens():
    assert redact(f"remote: Invalid token {TOKEN}.") == "remote: Invalid token *****."
    assert redact("bench build --app private-app") == "bench build --app private-app"


@pytest.mark.parametrize(
    "mode, docker_module",
    [("exec", "frappe_manager.docker.docker_compose"), ("image", "frappe_manager.docker.docker_client")],
)
def test_failed_container_hook_does_not_leak_token(config, bench, monkeypatch, mode, docker_module):
    calls = []
    monkeypatch.setattr(f"{docker_module}.run_command_with_exit_code", failing_docker(calls))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GIT_TOKEN", raising=False)
    service = service_for(config, mode)

    with pytest.raises(DockerException) as excinfo:
        service._run_script("exit 1", bench, bench, bench.path, SITE, None, "before_bench_build", True, "private-app")

    argv = " ".join(calls[0])
    assert TOKEN not in argv
    assert f"SITE_NAME={SITE}" in argv
    assert f"https://github.com/{REPO}" in argv

    error = excinfo.value
    assert TOKEN not in str(error)
    assert TOKEN not in " ".join(error.output.combined)
    # the unredacted original must not be reachable through the exception chain
    assert error.__context__ is None and error.__cause__ is None


def test_docker_exception_from_forwarded_env_token_is_redacted(config, bench, monkeypatch):
    # image mode forwards GITHUB_TOKEN from fmd's own environment as --env, so it is on argv
    calls = []
    monkeypatch.setattr("frappe_manager.docker.docker_client.run_command_with_exit_code", failing_docker(calls))
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    runner = service_for(config, "image").runner

    with pytest.raises(DockerException) as excinfo:
        runner.run(["bench", "build"], bench)

    assert f"GITHUB_TOKEN={TOKEN}" in calls[0]
    assert TOKEN not in str(excinfo.value)
    assert "GITHUB_TOKEN=*****" in excinfo.value.docker_command

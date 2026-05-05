import os
import re
import subprocess
import time
import uuid
from typing import Optional

from fmd.logger import get_logger


def _get_run_id() -> str:
    run_id = os.environ.get("GITHUB_RUN_ID")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    job_id = os.environ.get("GITHUB_JOB")

    if run_id and run_attempt:
        suffix = f"-{job_id}" if job_id else f"-{uuid.uuid4().hex[:6]}"
        return f"{run_id}-{run_attempt}{suffix}"

    return str(uuid.uuid4())[:8]


def _get_docker_client():
    import importlib

    _dc = importlib.import_module("frappe_manager.docker.docker_client")
    return getattr(_dc, "DockerClient")


def _parse_image_ref(image: str) -> tuple[str, str, Optional[str]]:
    if "@sha256:" in image:
        parts = image.split("@sha256:")
        return parts[0], "", parts[1] if len(parts) > 1 else None

    if ":" in image:
        parts = image.rsplit(":", 1)
        return parts[0], parts[1], None

    return image, "latest", None


def tag_image_for_run(image: str, run_id: Optional[str] = None) -> tuple[str, str]:
    if run_id is None:
        run_id = _get_run_id()

    repo, tag, digest = _parse_image_ref(image)

    timestamp = int(time.time())

    if digest:
        run_tag = f"{repo}:fmd-{timestamp}-{run_id}-sha256"
    else:
        run_tag = f"{repo}:fmd-{timestamp}-{run_id}-{tag}"

    try:
        DockerClient = _get_docker_client()
        DockerClient().tag(source_image=image, target_image=run_tag, stream=False)
        get_logger().debug(f"Tagged {image} as {run_tag}")

        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.Id}}", image],
            capture_output=True,
            text=True,
            timeout=5,
        )
        image_id = result.stdout.strip() if result.returncode == 0 else None

        return run_tag, image_id or ""
    except Exception as e:
        get_logger().warning(f"Failed to tag image {image} as {run_tag}: {e}")
        return run_tag, ""


def cleanup_run_tag(image: str, run_tag: str, image_id: str) -> None:
    try:
        DockerClient = _get_docker_client()
        client = DockerClient()

        in_use_images = set()
        in_use_ids = set()
        try:
            ps_result = subprocess.run(
                ["docker", "ps", "--format", "{{.Image}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if ps_result.returncode == 0:
                in_use_images = {img for img in ps_result.stdout.strip().split("\n") if img}

            ps_id_result = subprocess.run(
                ["docker", "ps", "--format", "{{.ImageID}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if ps_id_result.returncode == 0:
                in_use_ids = {img_id for img_id in ps_id_result.stdout.strip().split("\n") if img_id}
        except Exception as e:
            get_logger().warning(f"Failed to list running containers: {e}")

        if run_tag in in_use_images or (image_id and image_id in in_use_ids):
            get_logger().debug(f"Skipping cleanup of {run_tag} — in use by container")
            return

        try:
            client.rmi(image=run_tag, force=False, stream=False)
            get_logger().debug(f"Removed run tag {run_tag}")
        except Exception as e:
            get_logger().debug(f"Could not remove run tag {run_tag}: {e}")

        _cleanup_old_fmd_tags(client)

        if not image_id:
            return

        all_images = client.images(format="json")

        repo, _, _ = _parse_image_ref(image)
        fmd_pattern = re.compile(rf"^{re.escape(repo)}:fmd-")

        # Normalize image_id: strip sha256: prefix for comparison with short ID from docker images
        normalized_image_id = image_id.replace("sha256:", "")[:12]

        fmd_tagged_images = [
            img
            for img in all_images
            if img.get("ID") == normalized_image_id
            and img.get("Repository") == repo
            and img.get("Tag", "").startswith("fmd-")
        ]

        if not fmd_tagged_images:
            if image_id in in_use_ids or image in in_use_images:
                get_logger().debug(f"Skipping prune of {image} — in use")
                return

            try:
                client.rmi(image=image, force=False, stream=False)
                get_logger().debug(f"Pruned base image {image} — no fmd tags remain")
            except Exception as e:
                get_logger().debug(f"Could not prune base image {image}: {e}")

    except Exception as e:
        get_logger().warning(f"Cleanup failed for {run_tag}: {e}")


def _extract_tag_timestamp(tag: str) -> Optional[int]:
    match = re.search(r":fmd-(\d{10})-", tag)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def _cleanup_old_fmd_tags(client, max_age_hours: int = 24) -> None:
    try:
        all_images = client.images(format="json")
        now = time.time()
        cutoff = now - (max_age_hours * 3600)

        for img in all_images:
            repo = img.get("Repository", "")
            tag = img.get("Tag", "")

            if not repo or not tag or ":fmd-" not in f"{repo}:{tag}":
                continue

            full_tag = f"{repo}:{tag}"
            tag_timestamp = _extract_tag_timestamp(full_tag)

            if tag_timestamp is None:
                continue

            if tag_timestamp < cutoff:
                try:
                    client.rmi(image=full_tag, force=False, stream=False)
                    get_logger().debug(f"Pruned stale fmd tag: {full_tag} (age: {(now - tag_timestamp) / 3600:.1f}h)")
                except Exception:
                    pass
    except Exception as e:
        get_logger().debug(f"Old tag cleanup failed: {e}")

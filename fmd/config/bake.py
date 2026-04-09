import os
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

try:
    from jinja2 import Environment, FileSystemLoader
except Exception:

    class Environment:
        def __init__(self, *args, **kwargs):
            pass

        def get_template(self, name):
            class _Template:
                def render(self, data):
                    raise RuntimeError("jinja2 is required to render templates")

            return _Template()

    class FileSystemLoader:
        def __init__(self, *args, **kwargs):
            pass


class PythonConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "3.12"
    canonical: str = "3.12.12"
    image: str = "3.12.12-slim"


class NodeJSConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "22"
    canonical: str = "22.20.0"


class ImageBuildConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    tag: str = "latest"
    base_name: str
    base_tag: str
    platforms: list[str] = ["linux/amd64"]
    user: str = "frappe"
    dockerfile: Path
    labels: Optional[list[str]] = None
    push: bool = False
    additional_packages: Optional[list[str]] = Field(
        default=None, description="Additional APT packages to install in the builder stage"
    )

    @computed_field
    @property
    def image(self) -> str:
        return f"{self.name}:{self.tag}"

    @computed_field
    @property
    def base_image_name(self) -> str:
        return f"{self.base_name}:{self.base_tag}"

    def render_dockerfile(
        self, output_path: Path, site_name: str, bench_name: str, template_path: Optional[Path] = None
    ) -> None:
        template_to_use = template_path or self.dockerfile
        env = Environment(loader=FileSystemLoader(template_to_use.parent))
        template = env.get_template(template_to_use.name)
        data = self.model_dump()
        data["site_name"] = site_name
        data["bench_name"] = bench_name
        rendered_content = template.render(data)
        output_path.write_text(rendered_content)


_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "frappe_deployer" / "template"


class BakeNginxConfig(ImageBuildConfig):
    name: str = "frappe-nginx"
    tag: str = "latest"
    base_name: str = "nginx"
    base_tag: str = "latest"
    dockerfile: Path = _TEMPLATE_DIR / "nginx.Dockerfile"


class Observability(str, Enum):
    NEWRELIC = "newrelic"
    OPENTELEMETRY = "opentelemetry"


class BakeConfig(ImageBuildConfig):
    name: str = "frappe-gunicorn"
    tag: str = "latest"
    dockerfile: Path = _TEMPLATE_DIR / "frappe.Dockerfile"
    base_name: str = "python"
    base_tag: str = "3.12.12-slim"

    python: PythonConfig = Field(default_factory=PythonConfig)
    nodejs: NodeJSConfig = Field(default_factory=NodeJSConfig)
    distro: str = "slim"
    build_args: list[str] = Field(default_factory=list)
    observability: Observability = Observability.OPENTELEMETRY

    @computed_field
    @property
    def builder_image_name(self) -> str:
        return f"builder-{self.name}:python-{self.python.version}-nodejs-{self.nodejs.version}-{self.distro}"

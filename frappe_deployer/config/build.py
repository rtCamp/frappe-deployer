from enum import Enum
from pathlib import Path
import os
from typing import Optional
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel,  model_validator, computed_field

class PythonConfig(BaseModel):
    """A Pydantic model representing Python configuration."""
    version: str = "3.12"
    canonical: str = "3.12.12"
    image: str = "3.12.12-slim"

class NodeJSConfig(BaseModel):
    """A Pydantic model representing NodeJS configuration."""
    version: str = "22"
    canonical: str = "22.20.0"

class ImageBuildConfig(BaseModel):
    """A base model for image build configurations."""
    name: str
    base_name: str
    base_tag: str
    platforms: list[str] = ["linux/amd64"]
    user: str = "frappe"
    dockerfile: Path

    @computed_field
    @property
    def image(self) -> str:
        return f"{self.name}:{self.tag}"

    @computed_field
    @property
    def base_image_name(self) -> str:
        return f"{self.base_name}:{self.base_tag}"

    def render_dockerfile(self, output_path: Path, site_name: str, bench_name: str, template_path: Optional[Path] = None):
        """
        Renders a Jinja2 Dockerfile template with the given build configuration.

        Args:
            output_path: The path where the final Dockerfile will be saved.
            template_path: Optional path to a custom Jinja2 Dockerfile template.
                           If not provided, the default from the config is used.
        """
        template_to_use = template_path or self.dockerfile
        env = Environment(loader=FileSystemLoader(template_to_use.parent))
        template = env.get_template(template_to_use.name)
        data = self.model_dump()
        data['site_name'] = site_name
        data['bench_name'] = bench_name
        rendered_content = template.render(data)
        output_path.write_text(rendered_content)


class BuildNginxConfig(ImageBuildConfig):
    """A Pydantic model representing the build configuration for an Nginx image."""
    name: str = "frappe-nginx"
    tag: str = "latest"
    base_name: str = "nginx"
    base_tag: str = "latest"
    dockerfile: Path = Path(__file__).parent.parent / "template" / "nginx.Dockerfile"

class Observability(str, Enum):
    """Enum for observability options."""
    NEWRELIC = "newrelic"
    OPENTELEMETRY = "opentelemetry"


class BuildFrappeConfig(ImageBuildConfig):
    """
    A Pydantic model representing the build configuration for a Frappe image.
    """
    # Override name and dockerfile from base
    name: str = "frappe-gunicorn"
    dockerfile: Path = Path(__file__).parent.parent / "template" / "frappe.Dockerfile"

    base_name: str = "python"
    base_tag: str = "3.12.12-slim"

    # Frappe-specific fields
    bench_path: Path
    python: PythonConfig = PythonConfig()
    nodejs: NodeJSConfig = NodeJSConfig()
    distro: str = "slim"

    observability: Observability = Observability.OPENTELEMETRY

    build_args: list[str] = [""]

    # Override tag with a computed field
    @computed_field
    @property
    def tag(self) -> str:
        return f"python-{self.python.version}-nodejs-{self.nodejs.version}-{self.distro}"

    @computed_field
    @property
    def builder_image_name(self) -> str:
        return f"builder-{self.name}:{self.tag}"


    # @model_validator(mode='before')
    # def check_bench_path_exists(cls, values):
    #     """
    #     Validates that the specified bench_path exists on the filesystem.
    #     """
    #     bench_path = values.get('bench_path')

    #     if (bench_path and not Path(bench_path).exists()) or not bench_path:
    #         raise ValueError(f"The bench_path '{bench_path}' does not exist.")

    #     values['bench_path'] = Path(bench_path)
    #     return values

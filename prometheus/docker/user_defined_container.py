import uuid
from pathlib import Path
from typing import Optional, Sequence

from prometheus.docker.base_container import BaseContainer


class UserDefinedContainer(BaseContainer):
    def __init__(
        self,
        project_path: Path,
        workdir: Optional[str] = None,
        dockerfile_content: Optional[str] = None,
        image_name: Optional[str] = None,
        build_commands: Optional[Sequence[str]] = None,
        test_commands: Optional[Sequence[str]] = None,
    ):
        super().__init__(project_path, workdir, build_commands, test_commands)

        assert bool(dockerfile_content) != bool(image_name), (
            "Exactly one of dockerfile_content or image_name must be provided"
        )

        self.tag_name = f"prometheus_user_defined_container_{uuid.uuid4().hex[:10]}"
        self.dockerfile_content = dockerfile_content
        self.image_name = image_name

    def get_dockerfile_content(self) -> str:
        return self.dockerfile_content

    def build_docker_image(self):
        if self.dockerfile_content:
            super().build_docker_image()
        else:
            self._logger.info(f"Pulling docker image: {self.image_name}")
            pulled_image = self.client.images.pull(self.image_name)
            self._logger.info(f"Tagging pulled image as: {self.tag_name}")
            pulled_image.tag(repository=self.tag_name)

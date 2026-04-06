from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.models.project_model import ProjectModel, CameraModel
from app.storage.project_repository import ProjectRepository


class ProjectManager:
    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository
        self.current_project = ProjectModel()
        self.current_path: str | None = None

    def new_project(self) -> ProjectModel:
        self.current_project = ProjectModel()
        self.current_path = None
        return self.current_project

    def load_project(self, path: str) -> ProjectModel:
        return self.repository.load(path)

    def set_current_project(self, project: ProjectModel, path: str | None) -> ProjectModel:
        self.current_project = project
        self.current_path = path
        return self.current_project

    def open_project(self, path: str) -> ProjectModel:
        project = self.load_project(path)
        return self.set_current_project(project, path)

    def save_project(self, path: str | None = None) -> str:
        target = path or self.current_path
        if not target:
            raise ValueError("No save path specified")
        self.repository.save(self.current_project, target)
        self.current_path = target
        return target

    def add_camera(self, name: str, source: int | str) -> CameraModel:
        camera = CameraModel(id=f"cam_{uuid4().hex[:8]}", name=name, source=source)
        self.current_project.cameras.append(camera)
        return camera

    def remove_camera(self, camera_id: str) -> CameraModel | None:
        for index, camera in enumerate(self.current_project.cameras):
            if camera.id == camera_id:
                return self.current_project.cameras.pop(index)
        return None

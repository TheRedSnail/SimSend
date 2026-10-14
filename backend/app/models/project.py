"""
Project Context Management
Used for server-side persistent project state, avoiding the need for the frontend
to pass large amounts of data between API calls
"""

import os
import json
import uuid
import shutil
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field
from ..config import Config
from ..utils.atomic_io import atomic_write_json, atomic_write_text

_UNSET = object()


class ProjectStatus(str, Enum):
    """Project Status"""
    CREATED = "created"              # Just created, files uploaded
    ONTOLOGY_GENERATED = "ontology_generated"  # Ontology generated
    GRAPH_BUILDING = "graph_building"    # Graph building in progress
    GRAPH_COMPLETED = "graph_completed"  # Graph build complete
    FAILED = "failed"                # Failed


@dataclass
class Project:
    """Project Data Model"""
    project_id: str
    name: str
    status: ProjectStatus
    created_at: str
    updated_at: str

    # File information
    files: List[Dict[str, str]] = field(default_factory=list)  # [{filename, path, size}]
    total_text_length: int = 0

    # Ontology information (populated after step 1 generation)
    ontology: Optional[Dict[str, Any]] = None
    analysis_summary: Optional[str] = None

    # Graph information (populated after step 2 completion)
    graph_id: Optional[str] = None
    graph_build_task_id: Optional[str] = None

    # Configuration
    simulation_requirement: Optional[str] = None
    chunk_size: int = 500
    chunk_overlap: int = 50

    # Error information
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "status": self.status.value if isinstance(self.status, ProjectStatus) else self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "files": self.files,
            "total_text_length": self.total_text_length,
            "ontology": self.ontology,
            "analysis_summary": self.analysis_summary,
            "graph_id": self.graph_id,
            "graph_build_task_id": self.graph_build_task_id,
            "simulation_requirement": self.simulation_requirement,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "error": self.error
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create from dictionary"""
        status = data.get('status', 'created')
        if isinstance(status, str):
            status = ProjectStatus(status)

        return cls(
            project_id=data['project_id'],
            name=data.get('name', 'Unnamed Project'),
            status=status,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            files=data.get('files', []),
            total_text_length=data.get('total_text_length', 0),
            ontology=data.get('ontology'),
            analysis_summary=data.get('analysis_summary'),
            graph_id=data.get('graph_id'),
            graph_build_task_id=data.get('graph_build_task_id'),
            simulation_requirement=data.get('simulation_requirement'),
            chunk_size=data.get('chunk_size', 500),
            chunk_overlap=data.get('chunk_overlap', 50),
            error=data.get('error')
        )


class ProjectManager:
    """Project Manager - Handles persistent storage and retrieval of projects"""

    # Project storage root directory
    PROJECTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'projects')

    # Serializes read-modify-write cycles on project.json (request threads and
    # background jobs both update projects).
    _write_lock = threading.RLock()

    @classmethod
    @contextmanager
    def locked(cls):
        """Hold the project write lock for an atomic check-and-set."""
        with cls._write_lock:
            yield

    @classmethod
    def _ensure_projects_dir(cls):
        """Ensure the projects directory exists"""
        os.makedirs(cls.PROJECTS_DIR, exist_ok=True)

    @classmethod
    def _get_project_dir(cls, project_id: str) -> str:
        """Get the project directory path"""
        return os.path.join(cls.PROJECTS_DIR, project_id)

    @classmethod
    def _get_project_meta_path(cls, project_id: str) -> str:
        """Get the project metadata file path"""
        return os.path.join(cls._get_project_dir(project_id), 'project.json')

    @classmethod
    def _get_project_files_dir(cls, project_id: str) -> str:
        """Get the project file storage directory"""
        return os.path.join(cls._get_project_dir(project_id), 'files')

    @classmethod
    def _get_project_text_path(cls, project_id: str) -> str:
        """Get the path for the project's extracted text"""
        return os.path.join(cls._get_project_dir(project_id), 'extracted_text.txt')

    @classmethod
    def create_project(cls, name: str = "Unnamed Project") -> Project:
        """
        Create a new project

        Args:
            name: Project name

        Returns:
            Newly created Project object
        """
        cls._ensure_projects_dir()

        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        project = Project(
            project_id=project_id,
            name=name,
            status=ProjectStatus.CREATED,
            created_at=now,
            updated_at=now
        )

        # Create project directory structure
        project_dir = cls._get_project_dir(project_id)
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(files_dir, exist_ok=True)

        # Save project metadata
        cls.save_project(project)

        return project

    @classmethod
    def save_project(cls, project: Project) -> None:
        """Save project metadata.

        Raises ``FileNotFoundError`` if the project directory no longer exists:
        a stale writer (e.g. a background job for a project deleted meanwhile)
        must not resurrect it.
        """
        project.updated_at = datetime.now().isoformat()
        meta_path = cls._get_project_meta_path(project.project_id)

        # Atomic write so a concurrent get_project() never reads a torn file.
        with cls._write_lock:
            atomic_write_json(meta_path, project.to_dict(), create_dirs=False)

    @classmethod
    def update_project(cls, project_id: str, mutate, *, expected_build_task_id=_UNSET) -> Optional[Project]:
        """Reload a project, apply ``mutate(project)`` and save it, atomically.

        Returns ``None`` (without saving) when the project was deleted, or when
        ``expected_build_task_id`` is given and no longer matches — i.e. this
        caller's graph build has been superseded by a reset or a newer build.
        """
        with cls._write_lock:
            project = cls.get_project(project_id)
            if project is None:
                return None
            if (expected_build_task_id is not _UNSET
                    and project.graph_build_task_id != expected_build_task_id):
                return None
            mutate(project)
            try:
                cls.save_project(project)
            except FileNotFoundError:
                return None
            return project

    @classmethod
    def get_project(cls, project_id: str) -> Optional[Project]:
        """
        Get a project

        Args:
            project_id: Project ID

        Returns:
            Project object, or None if not found
        """
        meta_path = cls._get_project_meta_path(project_id)

        if not os.path.exists(meta_path):
            return None

        with open(meta_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return Project.from_dict(data)

    @classmethod
    def list_projects(cls, limit: int = 50) -> List[Project]:
        """
        List all projects

        Args:
            limit: Maximum number of results to return

        Returns:
            List of projects, sorted by creation time descending
        """
        cls._ensure_projects_dir()

        projects = []
        for project_id in os.listdir(cls.PROJECTS_DIR):
            try:
                project = cls.get_project(project_id)
            except (OSError, ValueError, KeyError):
                # One unreadable project must not break the whole listing.
                continue
            if project:
                projects.append(project)

        # Sort by creation time descending
        projects.sort(key=lambda p: p.created_at, reverse=True)

        return projects[:limit]

    @classmethod
    def recover_interrupted_builds(cls) -> int:
        """Mark projects left in GRAPH_BUILDING by a previous process as failed.

        Graph builds run in-process, so after a restart nothing is building
        anymore; without this the project stays "building" forever and every
        rebuild request is rejected. FAILED is a retryable state.
        """
        recovered = 0
        if not os.path.isdir(cls.PROJECTS_DIR):
            return 0
        for project_id in os.listdir(cls.PROJECTS_DIR):
            def mark_failed(project):
                project.status = ProjectStatus.FAILED
                project.error = "Graph build was interrupted by a server restart. Please rebuild the graph."
            try:
                project = cls.get_project(project_id)
                if project and project.status == ProjectStatus.GRAPH_BUILDING:
                    if cls.update_project(project_id, mark_failed):
                        recovered += 1
            except (OSError, ValueError, KeyError):
                continue
        return recovered

    @classmethod
    def delete_project(cls, project_id: str) -> bool:
        """
        Delete a project and all its files

        Args:
            project_id: Project ID

        Returns:
            Whether the deletion was successful
        """
        project_dir = cls._get_project_dir(project_id)

        with cls._write_lock:
            if not os.path.exists(project_dir):
                return False
            shutil.rmtree(project_dir)
        return True

    @classmethod
    def save_file_to_project(cls, project_id: str, file_storage, original_filename: str) -> Dict[str, str]:
        """
        Save an uploaded file to the project directory

        Args:
            project_id: Project ID
            file_storage: Flask FileStorage object
            original_filename: Original filename

        Returns:
            File info dictionary {filename, path, size}
        """
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(files_dir, exist_ok=True)

        # Generate a safe filename
        ext = os.path.splitext(original_filename)[1].lower()
        safe_filename = f"{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(files_dir, safe_filename)

        # Save the file
        file_storage.save(file_path)

        # Get file size
        file_size = os.path.getsize(file_path)

        return {
            "original_filename": original_filename,
            "saved_filename": safe_filename,
            "path": file_path,
            "size": file_size
        }

    @classmethod
    def save_extracted_text(cls, project_id: str, text: str) -> None:
        """Save extracted text"""
        text_path = cls._get_project_text_path(project_id)
        atomic_write_text(text_path, text, create_dirs=False)

    @classmethod
    def get_extracted_text(cls, project_id: str) -> Optional[str]:
        """Get extracted text"""
        text_path = cls._get_project_text_path(project_id)

        if not os.path.exists(text_path):
            return None

        with open(text_path, 'r', encoding='utf-8') as f:
            return f.read()

    @classmethod
    def get_project_files(cls, project_id: str) -> List[str]:
        """Get all file paths for a project"""
        files_dir = cls._get_project_files_dir(project_id)

        if not os.path.exists(files_dir):
            return []

        return [
            os.path.join(files_dir, f)
            for f in os.listdir(files_dir)
            if os.path.isfile(os.path.join(files_dir, f))
        ]

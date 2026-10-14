"""
Shared pytest fixtures for the backend API tests.

Every test gets a fresh Flask app whose on-disk state (projects, simulations,
reports, tasks) lives in a temporary directory. No test touches the network:
endpoints that would reach Zep/LLMs are only exercised up to their input
validation, or with the service patched out.
"""

import os
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Keep test runs from requiring real credentials.
os.environ.setdefault('LLM_API_KEY', 'test-key')
os.environ.setdefault('ZEP_API_KEY', 'test-key')

CLIENT_HEADERS = {'X-SimSend-Client': '1'}


@pytest.fixture
def data_dirs(tmp_path, monkeypatch):
    """Point every storage location at a temp dir."""
    from app.config import Config
    from app.models.project import ProjectManager
    from app.models.task import TaskManager
    from app.services.simulation_manager import SimulationManager
    from app.services.simulation_runner import SimulationRunner
    from app.services.report_agent import ReportManager

    uploads = tmp_path / 'uploads'
    sims = uploads / 'simulations'
    reports = uploads / 'reports'
    tasks = uploads / 'tasks'
    projects = uploads / 'projects'
    for d in (sims, reports, tasks, projects):
        d.mkdir(parents=True)

    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', str(uploads))
    monkeypatch.setattr(Config, 'OASIS_SIMULATION_DATA_DIR', str(sims))
    monkeypatch.setattr(Config, 'REPORTS_DIR', str(reports))
    monkeypatch.setattr(Config, 'TASKS_DIR', str(tasks))
    monkeypatch.setattr(Config, 'SIGNUPS_FILE', str(uploads / 'signups.json'))
    monkeypatch.setattr(ProjectManager, 'PROJECTS_DIR', str(projects))
    monkeypatch.setattr(SimulationManager, 'SIMULATION_DATA_DIR', str(sims))
    monkeypatch.setattr(SimulationRunner, 'RUN_STATE_DIR', str(sims))
    monkeypatch.setattr(ReportManager, 'REPORTS_DIR', str(reports))
    monkeypatch.setattr(ReportManager, '_sim_report_index', {})
    # Fresh TaskManager singleton bound to the temp tasks dir.
    monkeypatch.setattr(TaskManager, '_instance', None)

    return {'uploads': uploads, 'simulations': sims, 'reports': reports,
            'tasks': tasks, 'projects': projects}


@pytest.fixture
def make_app(data_dirs, monkeypatch):
    """Factory: build an app, optionally overriding Config attributes first."""
    from app import create_app
    from app.config import Config
    from app.services.simulation_runner import SimulationRunner

    # Don't install process-wide atexit/signal handlers from tests.
    monkeypatch.setattr(SimulationRunner, 'register_cleanup', classmethod(lambda cls: None))

    def factory(**overrides):
        for key, value in overrides.items():
            monkeypatch.setattr(Config, key, value)
        app = create_app()
        app.config['TESTING'] = True
        return app

    return factory


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def client(app):
    return app.test_client()

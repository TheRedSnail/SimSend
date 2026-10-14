"""
Graph-related API Routes
Uses project context mechanism with server-side persistent state
"""

import os
from flask import request, jsonify

from . import graph_bp
from .errors import error_response, public_task_error
from ..config import Config
from ..services.ontology_generator import OntologyGenerator
from ..services.graph_builder import GraphBuilderService
from ..services.text_processor import TextProcessor
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..utils.jobs import submit_job
from ..utils.validation import InputError, parse_bool, parse_int, query_int
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager, ProjectStatus

# Get logger
logger = get_logger('mirofish.api')


def allowed_file(filename: str) -> bool:
    """Check if the file extension is allowed"""
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


# ============== Project Management API ==============

@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """
    Get project details
    """
    project = ProjectManager.get_project(project_id)

    if not project:
        return jsonify({
            "success": False,
            "error": f"Project not found: {project_id}"
        }), 404

    return jsonify({
        "success": True,
        "data": project.to_dict()
    })


@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    """
    List all projects
    """
    try:
        limit = query_int('limit', default=50, minimum=1, maximum=500)
    except InputError as e:
        return error_response(e, "Invalid parameters")
    projects = ProjectManager.list_projects(limit=limit)

    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in projects],
        "count": len(projects)
    })


@graph_bp.route('/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """
    Delete project
    """
    success = ProjectManager.delete_project(project_id)

    if not success:
        return jsonify({
            "success": False,
            "error": f"Project not found or deletion failed: {project_id}"
        }), 404

    return jsonify({
        "success": True,
        "message": f"Project deleted: {project_id}"
    })


@graph_bp.route('/project/<project_id>/reset', methods=['POST'])
def reset_project(project_id: str):
    """
    Reset project status (for rebuilding graph)
    """
    def reset(project):
        # Reset to ontology-generated state. Clearing graph_build_task_id also
        # tells an in-flight build worker that it has been superseded.
        project.status = ProjectStatus.ONTOLOGY_GENERATED if project.ontology else ProjectStatus.CREATED
        project.graph_id = None
        project.graph_build_task_id = None
        project.error = None

    project = ProjectManager.update_project(project_id, reset)

    if not project:
        return jsonify({
            "success": False,
            "error": f"Project not found: {project_id}"
        }), 404

    return jsonify({
        "success": True,
        "message": f"Project reset: {project_id}",
        "data": project.to_dict()
    })


# ============== API 1: Upload Files and Generate Ontology ==============

@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """
    API 1: Upload files and analyze to generate ontology definitions

    Request format: multipart/form-data

    Parameters:
        files: Uploaded files (PDF/MD/TXT), multiple allowed
        simulation_requirement: Simulation requirement description (required)
        project_name: Project name (optional)
        additional_context: Additional notes (optional)

    Returns:
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "ontology": {
                    "entity_types": [...],
                    "edge_types": [...],
                    "analysis_summary": "..."
                },
                "files": [...],
                "total_text_length": 12345
            }
        }
    """
    try:
        logger.info("=== Starting ontology generation ===")

        # Get parameters
        simulation_requirement = request.form.get('simulation_requirement', '')
        project_name = request.form.get('project_name', 'Unnamed Project')
        additional_context = request.form.get('additional_context', '')

        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_requirement"
            }), 400
        if len(simulation_requirement) > 20000 or len(additional_context) > 50000:
            raise InputError("simulation_requirement/additional_context is too long")
        project_name = project_name.strip()[:200] or 'Unnamed Project'

        # Get uploaded files
        uploaded_files = request.files.getlist('files')
        if not uploaded_files or all(not f.filename for f in uploaded_files):
            return jsonify({
                "success": False,
                "error": "Please upload at least one document file"
            }), 400

        # Create project
        project = ProjectManager.create_project(name=project_name)
        project.simulation_requirement = simulation_requirement
        logger.info(f"Created project: {project.project_id}")

        # Save files and extract text
        document_texts = []
        all_text = ""
        skipped_files = []

        try:
            for file in uploaded_files:
                if not (file and file.filename):
                    continue
                if not allowed_file(file.filename):
                    skipped_files.append({
                        "filename": file.filename,
                        "reason": "Unsupported file type (allowed: "
                                  + ", ".join(sorted(Config.ALLOWED_EXTENSIONS)) + ")"
                    })
                    continue

                # Save file to project directory
                file_info = ProjectManager.save_file_to_project(
                    project.project_id,
                    file,
                    file.filename
                )

                # Extract text
                try:
                    text = FileParser.extract_text(file_info["path"])
                except Exception as e:
                    logger.warning(f"Text extraction failed for {file.filename}: {e}")
                    skipped_files.append({
                        "filename": file.filename,
                        "reason": "Could not extract text (file may be corrupt or encrypted)"
                    })
                    continue

                project.files.append({
                    "filename": file_info["original_filename"],
                    "size": file_info["size"]
                })
                text = TextProcessor.preprocess_text(text)
                document_texts.append(text)
                all_text += f"\n\n=== {file_info['original_filename']} ===\n{text}"

            if not document_texts:
                ProjectManager.delete_project(project.project_id)
                return jsonify({
                    "success": False,
                    "error": "No documents were processed successfully, please check file formats",
                    "skipped_files": skipped_files
                }), 400

            # Save extracted text
            project.total_text_length = len(all_text)
            ProjectManager.save_extracted_text(project.project_id, all_text)
            ProjectManager.save_project(project)
        except Exception:
            # Never leave a half-created project behind.
            ProjectManager.delete_project(project.project_id)
            raise
        logger.info(f"Text extraction complete, {len(all_text)} characters total")

        # The LLM ontology generation can take minutes, so run it in the shared
        # background job pool instead of blocking this request thread (which
        # previously tied up a worker and invited thread-pool exhaustion). The
        # client polls GET /api/graph/task/<task_id> for completion.
        project_id = project.project_id
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            "ontology_generate", metadata={"project_id": project_id}
        )

        def ontology_task():
            onto_logger = get_logger('mirofish.ontology')
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=10,
                    message="Calling LLM to generate ontology definitions..."
                )
                generator = OntologyGenerator()
                ontology = generator.generate(
                    document_texts=document_texts,
                    simulation_requirement=simulation_requirement,
                    additional_context=additional_context if additional_context else None
                )

                entity_count = len(ontology.get("entity_types", []))
                edge_count = len(ontology.get("edge_types", []))
                onto_logger.info(
                    f"[{task_id}] Ontology complete: {entity_count} entity types, {edge_count} relationship types"
                )

                def apply_ontology(proj):
                    proj.ontology = {
                        "entity_types": ontology.get("entity_types", []),
                        "edge_types": ontology.get("edge_types", [])
                    }
                    proj.analysis_summary = ontology.get("analysis_summary", "")
                    proj.status = ProjectStatus.ONTOLOGY_GENERATED

                # Re-read the project under the lock so concurrent updates
                # aren't clobbered and a deleted project isn't resurrected.
                proj = ProjectManager.update_project(project_id, apply_ontology)
                if proj is None:
                    task_manager.fail_task(task_id, "Project was deleted during ontology generation")
                    return

                task_manager.complete_task(task_id, {
                    "project_id": proj.project_id,
                    "project_name": proj.name,
                    "ontology": proj.ontology,
                    "analysis_summary": proj.analysis_summary,
                    "total_text_length": proj.total_text_length,
                })
            except Exception as e:
                task_manager.fail_task(task_id, public_task_error(e, "Ontology generation failed"))

        submit_job(ontology_task)

        # 202 Accepted: work continues in the background.
        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "project_name": project.name,
                "task_id": task_id,
                "files": project.files,
                "skipped_files": skipped_files,
                "total_text_length": project.total_text_length,
                "async": True
            }
        }), 202

    except Exception as e:
        return error_response(e, "Ontology generation request failed")


# ============== API 2: Build Graph ==============

@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """
    API 2: Build graph based on project_id

    Request (JSON):
        {
            "project_id": "proj_xxxx",  // Required, from API 1
            "graph_name": "Graph name",  // Optional
            "chunk_size": 500,          // Optional, default 500
            "chunk_overlap": 50,        // Optional, default 50
            "force": false              // Optional, rebuild even if a build is running
        }

    Returns:
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "task_id": "task_xxxx",
                "message": "Graph build task started"
            }
        }
    """
    try:
        logger.info("=== Starting graph build ===")

        if not Config.ZEP_API_KEY:
            logger.error("Configuration error: ZEP_API_KEY not configured")
            return jsonify({
                "success": False,
                "error": "Configuration error: ZEP_API_KEY not configured"
            }), 500

        # Parse request
        data = request.get_json() or {}
        project_id = data.get('project_id')
        logger.debug(f"Request parameters: project_id={project_id}")

        if not project_id:
            return jsonify({
                "success": False,
                "error": "Please provide project_id"
            }), 400

        force = parse_bool(data.get('force'), 'force')
        task_manager = TaskManager()

        # Check-and-set the project's build state atomically so two concurrent
        # requests can't both start a Zep build for the same project.
        with ProjectManager.locked():
            project = ProjectManager.get_project(project_id)
            if not project:
                return jsonify({
                    "success": False,
                    "error": f"Project not found: {project_id}"
                }), 404

            if project.status == ProjectStatus.CREATED:
                return jsonify({
                    "success": False,
                    "error": "Ontology not yet generated for this project, please call /ontology/generate first"
                }), 400

            if project.status == ProjectStatus.GRAPH_BUILDING and not force:
                return jsonify({
                    "success": False,
                    "error": "Graph is currently being built, please do not resubmit. To force rebuild, add force: true",
                    "task_id": project.graph_build_task_id
                }), 409

            graph_name = data.get('graph_name') or project.name or 'MiroFish Graph'
            if not isinstance(graph_name, str) or len(graph_name) > 200:
                raise InputError("graph_name must be a string of at most 200 characters")

            # Validate chunk parameters to prevent pathological chunking
            # (chunk_overlap >= chunk_size would loop forever and exhaust memory).
            chunk_size = parse_int(
                data.get('chunk_size', project.chunk_size or Config.DEFAULT_CHUNK_SIZE),
                'chunk_size', minimum=50, maximum=10000
            )
            chunk_overlap = parse_int(
                data.get('chunk_overlap', project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP),
                'chunk_overlap', minimum=0
            )
            if chunk_overlap >= chunk_size:
                raise InputError("chunk_overlap must be >= 0 and less than chunk_size")

            text = ProjectManager.get_extracted_text(project_id)
            if not text:
                return jsonify({
                    "success": False,
                    "error": "Extracted text content not found"
                }), 400

            ontology = project.ontology
            if not ontology:
                return jsonify({
                    "success": False,
                    "error": "Ontology definition not found"
                }), 400

            task_id = task_manager.create_task(
                "graph_build",
                metadata={"description": f"Build graph: {graph_name}", "project_id": project_id}
            )
            logger.info(f"Created graph build task: task_id={task_id}, project_id={project_id}")

            # A new task id supersedes any build still running for this project
            # (force rebuild); that worker notices and stops writing.
            project.status = ProjectStatus.GRAPH_BUILDING
            project.graph_id = None
            project.error = None
            project.graph_build_task_id = task_id
            project.chunk_size = chunk_size
            project.chunk_overlap = chunk_overlap
            ProjectManager.save_project(project)

        def update_if_current(mutate):
            """Apply ``mutate`` to the project only while this build is still
            the project's current build. Returns False when superseded/deleted."""
            return ProjectManager.update_project(
                project_id, mutate, expected_build_task_id=task_id
            ) is not None

        # Start background task
        def build_task():
            build_logger = get_logger('mirofish.build')
            graph_id = None
            builder = None

            def abandon(reason):
                build_logger.info(f"[{task_id}] {reason}; stopping")
                task_manager.fail_task(task_id, reason)
                # Best effort: don't leave an orphaned Zep graph behind.
                if builder and graph_id:
                    try:
                        builder.delete_graph(graph_id)
                    except Exception as e:
                        build_logger.warning(f"[{task_id}] Failed to delete orphaned graph {graph_id}: {e}")

            superseded = "Build superseded by a newer build or reset, or the project was deleted"

            try:
                build_logger.info(f"[{task_id}] Starting graph build...")
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    message="Initializing graph build service..."
                )

                builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)

                task_manager.update_task(task_id, message="Chunking text...", progress=5)
                chunks = TextProcessor.split_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
                total_chunks = len(chunks)

                task_manager.update_task(task_id, message="Creating Zep graph...", progress=10)
                graph_id = builder.create_graph(name=graph_name)

                def set_graph_id(p):
                    p.graph_id = graph_id
                if not update_if_current(set_graph_id):
                    abandon(superseded)
                    return

                task_manager.update_task(task_id, message="Setting ontology definitions...", progress=15)
                builder.set_ontology(graph_id, ontology)

                # Add text (progress_callback signature is (msg, progress_ratio))
                def add_progress_callback(msg, progress_ratio):
                    progress = 15 + int(progress_ratio * 40)  # 15% - 55%
                    task_manager.update_task(task_id, message=msg, progress=progress)

                task_manager.update_task(
                    task_id,
                    message=f"Starting to add {total_chunks} text chunks...",
                    progress=15
                )
                episode_uuids = builder.add_text_batches(
                    graph_id,
                    chunks,
                    batch_size=3,
                    progress_callback=add_progress_callback
                )

                # Wait for Zep processing (query processed status of each episode)
                task_manager.update_task(task_id, message="Waiting for Zep to process data...", progress=55)

                def wait_progress_callback(msg, progress_ratio):
                    progress = 55 + int(progress_ratio * 35)  # 55% - 90%
                    task_manager.update_task(task_id, message=msg, progress=progress)

                fully_processed = builder.wait_for_episodes(episode_uuids, wait_progress_callback)

                task_manager.update_task(task_id, message="Retrieving graph data...", progress=95)
                graph_data = builder.get_graph_data(graph_id)

                def mark_completed(p):
                    p.status = ProjectStatus.GRAPH_COMPLETED
                if not update_if_current(mark_completed):
                    abandon(superseded)
                    return

                node_count = graph_data.get("node_count", 0)
                edge_count = graph_data.get("edge_count", 0)
                build_logger.info(
                    f"[{task_id}] Graph build complete: graph_id={graph_id}, nodes={node_count}, "
                    f"edges={edge_count}, fully_processed={fully_processed}"
                )

                if fully_processed:
                    message = "Graph build complete"
                else:
                    # Zep was still processing some chunks when the wait timed
                    # out: the graph is usable but partial. Say so explicitly.
                    message = ("Graph build finished with a PARTIAL graph: Zep had not processed "
                               "every text chunk before the timeout. Rebuild for a complete graph.")

                task_manager.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    message=message,
                    progress=100,
                    result={
                        "project_id": project_id,
                        "graph_id": graph_id,
                        "node_count": node_count,
                        "edge_count": edge_count,
                        "chunk_count": total_chunks,
                        "partial": not fully_processed,
                    }
                )

            except Exception as e:
                error = public_task_error(e, "Graph build failed")

                def mark_failed(p):
                    p.status = ProjectStatus.FAILED
                    p.error = error
                update_if_current(mark_failed)

                task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    message="Build failed",
                    error=error
                )

        # Submit to the shared bounded job pool
        submit_job(build_task)

        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "task_id": task_id,
                "message": "Graph build task started, query progress via /task/{task_id}"
            }
        })

    except Exception as e:
        return error_response(e, "Failed to start graph build")


# ============== Task Query API ==============

@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """
    Query task status
    """
    task = TaskManager().get_task(task_id)

    if not task:
        return jsonify({
            "success": False,
            "error": f"Task not found: {task_id}"
        }), 404

    return jsonify({
        "success": True,
        "data": task.to_dict()
    })


@graph_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """
    List all tasks
    """
    # list_tasks() already returns a list of dicts (not Task objects).
    tasks = TaskManager().list_tasks()

    return jsonify({
        "success": True,
        "data": tasks,
        "count": len(tasks)
    })


# ============== Graph Data API ==============

@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    """
    Get graph data (nodes and edges)
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY not configured"
            }), 500

        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        graph_data = builder.get_graph_data(graph_id)

        return jsonify({
            "success": True,
            "data": graph_data
        })

    except Exception as e:
        return error_response(e, "Failed to get graph data")


@graph_bp.route('/delete/<graph_id>', methods=['DELETE'])
def delete_graph(graph_id: str):
    """
    Delete Zep graph
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEY not configured"
            }), 500

        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        builder.delete_graph(graph_id)

        return jsonify({
            "success": True,
            "message": f"Graph deleted: {graph_id}"
        })

    except Exception as e:
        return error_response(e, "Failed to delete graph")

"""Security behaviour of the API: CSRF header, CORS, admin gate, error leaks."""

from conftest import CLIENT_HEADERS


# ---------- CSRF: client header on mutating requests ----------

def test_mutating_request_without_client_header_is_rejected(client):
    resp = client.post('/api/graph/project/proj_abc/reset')
    assert resp.status_code == 403
    assert 'X-SimSend-Client' in resp.get_json()['error']


def test_mutating_request_with_client_header_passes_the_gate(client):
    resp = client.post('/api/graph/project/proj_abc/reset', headers=CLIENT_HEADERS)
    # Gets past the CSRF gate to the view, which reports the missing project.
    assert resp.status_code == 404


def test_delete_without_client_header_is_rejected(client):
    resp = client.delete('/api/graph/project/proj_abc')
    assert resp.status_code == 403


def test_get_requests_do_not_need_client_header(client):
    resp = client.get('/api/graph/project/proj_abc')
    assert resp.status_code == 404


def test_form_post_without_header_cannot_upload(client):
    # A cross-site HTML form can't set custom headers.
    resp = client.post('/api/graph/ontology/generate', data={'simulation_requirement': 'x'})
    assert resp.status_code == 403


# ---------- CORS ----------

def test_no_cors_headers_by_default(client):
    resp = client.get('/api/simulation/list', headers={'Origin': 'https://evil.example'})
    assert 'Access-Control-Allow-Origin' not in resp.headers


def test_cors_preflight_denied_for_unlisted_origin(make_app):
    app = make_app(CORS_ORIGINS=['https://app.example'])
    resp = app.test_client().options('/api/simulation/start', headers={
        'Origin': 'https://evil.example',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'X-SimSend-Client',
    })
    assert resp.headers.get('Access-Control-Allow-Origin') != 'https://evil.example'


def test_cors_allows_configured_origin(make_app):
    app = make_app(CORS_ORIGINS=['https://app.example'])
    resp = app.test_client().get('/api/simulation/list', headers={'Origin': 'https://app.example'})
    assert resp.headers.get('Access-Control-Allow-Origin') == 'https://app.example'


# ---------- Admin gate ----------

def test_admin_gate_inert_without_key(client):
    assert client.get('/api/graph/tasks').status_code == 200


def test_admin_gate_covers_enumeration_endpoints(make_app):
    client = make_app(ADMIN_API_KEY='s3cret').test_client()
    for path in ('/api/graph/tasks', '/api/simulation/history', '/api/simulation/list',
                 '/api/report/list', '/api/graph/project/list'):
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers={'X-Admin-Key': 's3cret'}).status_code == 200, path


def test_admin_gate_covers_mutations(make_app):
    client = make_app(ADMIN_API_KEY='s3cret').test_client()
    resp = client.post('/api/graph/project/proj_abc/reset', headers=CLIENT_HEADERS)
    assert resp.status_code == 401
    resp = client.post('/api/graph/project/proj_abc/reset',
                       headers={**CLIENT_HEADERS, 'X-Admin-Key': 'wrong'})
    assert resp.status_code == 401
    resp = client.post('/api/graph/project/proj_abc/reset',
                       headers={**CLIENT_HEADERS, 'X-Admin-Key': 's3cret'})
    assert resp.status_code == 404


def test_admin_gate_leaves_single_resource_reads_open(make_app):
    client = make_app(ADMIN_API_KEY='s3cret').test_client()
    assert client.get('/api/graph/project/proj_abc').status_code == 404


# ---------- Error responses never leak internals ----------

def test_unexpected_error_returns_generic_message(client, monkeypatch):
    from app.services.simulation_manager import SimulationManager

    def boom(self, *args, **kwargs):
        raise RuntimeError("secret detail at C:\\internal\\path.py")

    monkeypatch.setattr(SimulationManager, 'list_simulations', boom)
    resp = client.get('/api/simulation/list')
    assert resp.status_code == 500
    body = resp.get_json()
    assert body['success'] is False
    assert 'secret detail' not in resp.get_data(as_text=True)
    assert 'Traceback' not in resp.get_data(as_text=True)
    assert 'traceback' not in body
    assert body.get('error_id')


def test_background_task_error_is_sanitized(client):
    from app.api.errors import public_task_error

    try:
        raise RuntimeError("password=hunter2 in /etc/secret")
    except RuntimeError as e:
        message = public_task_error(e, "Graph build failed")
    assert 'hunter2' not in message
    assert 'RuntimeError' in message
    assert 'error id' in message


def test_unknown_api_route_returns_json(client):
    resp = client.get('/api/does-not-exist')
    assert resp.status_code == 404
    assert resp.get_json()['success'] is False

"""Tests for the landing page's early-access sign-up API."""

import json

import pytest

from conftest import CLIENT_HEADERS

VALID = {
    'name': '  Jan   Jansen ',
    'email': 'Jan@Example.com',
    'company': 'Velora',
    'role': 'marketing',
    'use_case': 'Price change\nfor students',
    'updates': True,
}


@pytest.fixture(autouse=True)
def _fresh_rate_limiter():
    from app.services.signup_store import rate_limiter
    rate_limiter.reset()
    yield
    rate_limiter.reset()


def _post(client, payload):
    return client.post('/api/signup', json=payload, headers=CLIENT_HEADERS)


def _stored(data_dirs):
    path = data_dirs['uploads'] / 'signups.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []


def test_signup_is_stored_cleaned(client, data_dirs):
    resp = _post(client, VALID)
    assert resp.status_code == 201
    assert resp.get_json() == {'success': True}

    [record] = _stored(data_dirs)
    assert record['name'] == 'Jan Jansen'
    assert record['email'] == 'jan@example.com'
    assert record['use_case'] == 'Price change\nfor students'
    assert record['updates'] is True
    assert record['created_at'] and record['updated_at']


def test_signing_up_again_updates_instead_of_duplicating(client, data_dirs):
    _post(client, VALID)
    resp = _post(client, {**VALID, 'email': 'JAN@example.com', 'company': 'Pedaalpas'})
    assert resp.status_code == 201

    [record] = _stored(data_dirs)
    assert record['company'] == 'Pedaalpas'


@pytest.mark.parametrize('change, message', [
    ({'name': '   '}, 'name is required'),
    ({'email': 'not-an-email'}, 'email is not a valid'),
    ({'email': None}, 'email is required'),
    ({'role': 'ceo'}, 'role is not one of'),
    ({'updates': 'yes'}, 'updates must be'),
    ({'company': 'x' * 161}, 'company is too long'),
    ({'name': ['list']}, 'name must be text'),
])
def test_invalid_signups_are_rejected(client, data_dirs, change, message):
    resp = _post(client, {**VALID, **change})
    assert resp.status_code == 400
    assert message in resp.get_json()['error']
    assert _stored(data_dirs) == []


def test_non_object_body_is_rejected(client):
    resp = client.post('/api/signup', data='[1, 2]', content_type='application/json',
                       headers=CLIENT_HEADERS)
    assert resp.status_code == 400


def test_signup_requires_client_header(client, data_dirs):
    resp = client.post('/api/signup', json=VALID)
    assert resp.status_code == 403
    assert _stored(data_dirs) == []


def test_honeypot_pretends_success_but_stores_nothing(client, data_dirs):
    resp = _post(client, {**VALID, 'website': 'http://spam.example'})
    assert resp.status_code == 201
    assert _stored(data_dirs) == []


def test_oversized_body_is_rejected(client):
    resp = _post(client, {**VALID, 'use_case': 'x' * 9000})
    assert resp.status_code == 413


def test_rate_limit(make_app):
    client = make_app(SIGNUP_RATE_LIMIT=2).test_client()
    assert _post(client, VALID).status_code == 201
    assert _post(client, {**VALID, 'email': 'b@example.com'}).status_code == 201
    assert _post(client, {**VALID, 'email': 'c@example.com'}).status_code == 429


def test_store_cap(make_app, data_dirs):
    client = make_app(MAX_SIGNUPS=1).test_client()
    assert _post(client, VALID).status_code == 201
    assert _post(client, {**VALID, 'email': 'b@example.com'}).status_code == 503
    # An existing address can still update its record.
    assert _post(client, {**VALID, 'company': 'New'}).status_code == 201
    assert len(_stored(data_dirs)) == 1


def test_signup_post_stays_public_when_admin_key_is_set(make_app):
    client = make_app(ADMIN_API_KEY='secret').test_client()
    assert _post(client, VALID).status_code == 201


def test_list_is_closed_without_admin_key(client):
    _post(client, VALID)
    resp = client.get('/api/signup/list')
    assert resp.status_code == 403
    assert 'ADMIN_API_KEY' in resp.get_json()['error']


def test_list_requires_matching_admin_key(make_app):
    client = make_app(ADMIN_API_KEY='secret').test_client()
    _post(client, VALID)
    assert client.get('/api/signup/list').status_code == 401
    assert client.get('/api/signup/list', headers={'X-Admin-Key': 'wrong'}).status_code == 401

    resp = client.get('/api/signup/list', headers={'X-Admin-Key': 'secret'})
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert data['count'] == 1
    assert data['signups'][0]['email'] == 'jan@example.com'


def test_list_as_csv_neutralises_formulas(make_app):
    client = make_app(ADMIN_API_KEY='secret').test_client()
    _post(client, {**VALID, 'company': '=HYPERLINK("http://evil")'})

    resp = client.get('/api/signup/list?format=csv', headers={'X-Admin-Key': 'secret'})
    assert resp.status_code == 200
    assert resp.mimetype == 'text/csv'
    body = resp.get_data(as_text=True)
    assert body.splitlines()[0].startswith('created_at,updated_at,name,email')
    assert "'=HYPERLINK" in body

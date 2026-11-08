"""Tests for the public site config the landing page reads (analytics settings)."""

import pytest

UMAMI = {
    'UMAMI_SCRIPT_URL': 'https://analytics.example.com/script.js',
    'UMAMI_WEBSITE_ID': '4f1c2a9e-0b6d-4c1e-9a55-2f3e8d7c6b10',
}


def test_no_umami_when_not_configured(make_app):
    client = make_app(UMAMI_SCRIPT_URL='', UMAMI_WEBSITE_ID='').test_client()
    resp = client.get('/api/site-config')
    assert resp.status_code == 200
    assert resp.get_json() == {'success': True, 'data': {'umami': None}}


def test_umami_settings_are_returned(make_app):
    client = make_app(**UMAMI).test_client()
    resp = client.get('/api/site-config')
    assert resp.status_code == 200
    assert resp.get_json()['data']['umami'] == {
        'scriptUrl': UMAMI['UMAMI_SCRIPT_URL'],
        'websiteId': UMAMI['UMAMI_WEBSITE_ID'],
    }


@pytest.mark.parametrize('overrides', [
    {'UMAMI_WEBSITE_ID': ''},
    {'UMAMI_SCRIPT_URL': ''},
    {'UMAMI_SCRIPT_URL': 'javascript:alert(1)'},
    {'UMAMI_SCRIPT_URL': '//analytics.example.com/script.js'},
])
def test_incomplete_or_unsafe_settings_turn_umami_off(make_app, overrides):
    client = make_app(**{**UMAMI, **overrides}).test_client()
    assert client.get('/api/site-config').get_json()['data']['umami'] is None


def test_site_config_stays_public_when_admin_key_is_set(make_app):
    client = make_app(ADMIN_API_KEY='secret', **UMAMI).test_client()
    assert client.get('/api/site-config').status_code == 200

"""Run inside the deployed app: routes, model/tool call, provider auth and storage.

The storage probe is synthetic text and is deleted. No images or notices are sent.
"""
import json
import uuid

import httpx
from censearch.config import Settings
from censearch.evidence import EvidenceStore
from censearch.facecheck import FaceCheckClient


def main():
    report = {}
    settings = Settings()
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=90, trust_env=False) as api:
        for path in ['/', '/app/', '/signup.html', '/contact/', '/legal/privacy-policy/']:
            response = api.get(path)
            assert response.status_code == 200, (path, response.status_code)
        health = api.get('/api/health').json()
        assert health['status'] == 'ok', health['status']
        assert health['face_models']['loaded']
        assert not health['external_delivery_enabled']
        report['routes_and_health'] = 'passed'
        response = api.post('/api/agent/probe', json={'hostname': 'example.org'})
        response.raise_for_status()
        probe = response.json()
        report['model_probe'] = {
            'status': probe['status'], 'tool_calls': len(probe['tool_calls']),
            'message': probe.get('message'),
        }
        assert probe['status'] == 'completed' and probe['tool_calls'], report['model_probe']
    with httpx.Client(timeout=30, trust_env=False) as http:
        info = FaceCheckClient(settings, http).info()
        report['facecheck'] = {
            'authenticated': True, 'online': info.get('is_online'),
            'remaining_credits': info.get('remaining_credits'), 'search_submitted': False,
        }
    storage = EvidenceStore(settings)
    assert storage.client is not None, 'Object Storage is not configured'
    person_id = 'deployment-probe-' + uuid.uuid4().hex
    payload = b'CenSearch deployment storage probe; synthetic text, no personal data.'
    stored = storage.put(person_id, 'probe.txt', payload)
    try:
        response = storage.client.get_object(Bucket=storage.bucket, Key=stored['object_key'])
        assert response['Body'].read() == payload
        report['object_storage'] = 'write and read verified'
    finally:
        storage.remove_files([stored])
        (settings.data_dir / 'people' / person_id).rmdir()
    report['object_storage_cleanup'] = 'deleted only generated probe'
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

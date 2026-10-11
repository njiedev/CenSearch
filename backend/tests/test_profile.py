"""Photo management and whitelist enforcement; all photos and delivery stay local."""

import pytest
from sqlalchemy import select

from censearch.case_records import Notice
from test_round2 import workflow_case as workflow_case
from test_round3 import isolated_workflow
from test_app_backend import prepare, put_domains, person_id


def photo_file(photo_folder, kind="reference"):
    path = sorted((photo_folder / kind).glob("*.jpg"))[0]
    return path.name, path.read_bytes(), "image/jpeg"


def version(client):
    with client.app.state.store.session() as session:
        return client.app.state.store.version(session)


def test_add_read_remove_photos_and_gallery_version(client, enrolled, photo_folder):
    pid = enrolled["id"]
    base = f"/api/people/{pid}"
    old_version = version(client)
    first_path = client.app.state.settings.data_dir / enrolled["references"][0]["path"]
    first_bytes = first_path.read_bytes()
    response = client.post(base + "/photos", data={"ownership": "Local fixture ownership"}, files=[
        ("references", photo_file(photo_folder)),
        ("originals", photo_file(photo_folder, "originals")),
    ])
    assert response.status_code == 201, response.text
    person = response.json()["person"]
    assert len(person["references"]) == len(person["originals"]) == 2
    assert first_path.read_bytes() == first_bytes
    assert version(client) != old_version
    added_version = version(client)
    for kind, rows in (("reference", person["references"]), ("original", person["originals"])):
        photo = rows[-1]
        path = client.app.state.settings.data_dir / photo["path"]
        url = f"{base}/photos/{kind}/{photo['id']}"
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/")
        assert response.headers["cache-control"] == "no-store"
        assert response.content == path.read_bytes()
        assert client.get(url.replace(pid, "someone-else")).status_code == 404
        assert client.delete(url.replace(pid, "someone-else")).status_code == 404
        assert path.exists()
        assert client.delete(url).status_code == 200
        assert client.get(url).status_code == 404
        assert not path.exists()
    assert version(client) != added_version
    saved = client.get(base).json()
    assert saved["references"] == enrolled["references"]
    assert saved["originals"] == enrolled["originals"]
    assert "embedding" not in str(saved)


def test_last_face_cannot_be_removed(client, enrolled):
    photo = enrolled["references"][0]
    response = client.delete(f"/api/people/{enrolled['id']}/photos/reference/{photo['id']}")
    assert response.status_code == 422
    assert "at least one" in response.json()["error"]["message"]
    assert (client.app.state.settings.data_dir / photo["path"]).is_file()


def test_upload_validation_is_atomic(client, enrolled, photo_folder):
    base = f"/api/people/{enrolled['id']}"
    before = set(client.app.state.settings.data_dir.rglob("*.jpg"))
    response = client.post(base + "/photos", files=[
        ("references", photo_file(photo_folder)),
        ("references", ("broken.jpg", b"not an image", "image/jpeg")),
    ])
    assert response.status_code == 422
    assert "broken.jpg" in response.json()["error"]["message"]
    assert client.get(base).json() == enrolled
    assert set(client.app.state.settings.data_dir.rglob("*.jpg")) == before
    assert client.post(base + "/photos").status_code == 422
    assert client.post(base + "/photos", files=[("originals", photo_file(photo_folder, "originals"))]).status_code == 422
    assert client.post("/api/people/missing/photos", files=[("references", photo_file(photo_folder))]).status_code == 404
    assert client.get(base + "/photos/invalid/1").status_code == 404


def test_upload_storage_failure_preserves_existing_photos(client, enrolled, photo_folder, monkeypatch):
    enrollment = client.app.state.enrollment
    original_put = enrollment.evidence.put
    calls = []

    def fail_second(*args):
        if calls:
            raise RuntimeError("Storage unavailable")
        result = original_put(*args)
        calls.append(result)
        return result

    monkeypatch.setattr(enrollment.evidence, "put", fail_second)
    with pytest.raises(RuntimeError, match="Storage unavailable"):
        enrollment.add_photos(enrolled["id"], [photo_file(photo_folder)[:2]] * 2, [], "")
    assert enrollment.get(enrolled["id"]) == enrolled
    assert not (enrollment.evidence.root / calls[0]["path"]).exists()
    assert all((enrollment.evidence.root / row["path"]).exists() for row in enrolled["references"])


def test_photo_mutations_respect_busy_gate(client, enrolled, photo_folder):
    client.app.state.busy = True
    try:
        base = f"/api/people/{enrolled['id']}/photos"
        assert client.post(base, files=[("references", photo_file(photo_folder))]).status_code == 409
        assert client.delete(f"{base}/reference/{enrolled['references'][0]['id']}").status_code == 409
    finally:
        client.app.state.busy = False


def test_delete_original_removes_linked_requests(workflow_case, monkeypatch):
    client, cid = workflow_case
    isolated_workflow(client, monkeypatch)
    batch = prepare(client, [cid])
    pid = person_id(client, cid)
    person = client.get(f"/api/people/{pid}").json()
    photo = person["originals"][0]
    assert client.delete(f"/api/people/{pid}/photos/original/{photo['id']}").status_code == 200
    assert client.get(f"/api/cases/{cid}").status_code == 404
    assert client.get(f"/api/batches/{batch['id']}").status_code == 404
    assert not (client.app.state.settings.data_dir / photo["path"]).exists()


def test_whitelist_blocks_individual_draft_and_send_then_can_be_removed(workflow_case, monkeypatch):
    client, cid = workflow_case
    sent = isolated_workflow(client, monkeypatch)
    prepare(client, [cid])
    pid = person_id(client, cid)
    notice = client.get(f"/api/cases/{cid}").json()["drafted_request"]
    put_domains(client, pid, ["localhost"])
    response = client.post(f"/api/cases/{cid}/draft", json={"recipient_id": notice["recipient"]["id"], "rung": "site"})
    assert response.status_code == 422
    assert "whitelist" in response.json()["error"]["message"]
    assert client.post(f"/api/cases/{cid}/approve", json={"notice_id": notice["id"], "sha256": notice["sha256"], "approved_by": "Local tester"}).status_code == 200
    response = client.post(f"/api/cases/{cid}/send")
    assert response.status_code == 422
    assert "whitelist" in response.json()["error"]["message"]
    assert not sent
    with client.app.state.store.session() as session:
        assert len(list(session.scalars(select(Notice)))) == 1
    assert put_domains(client, pid, []).status_code == 200
    assert client.post(f"/api/cases/{cid}/send").status_code == 200
    assert len(sent) == 1


@pytest.mark.parametrize("entry", ["ftp://example.com", "javascript://example.com", "file://example.com"])
def test_whitelist_rejects_non_web_schemes(client, enrolled, entry):
    base = f"/api/people/{enrolled['id']}/whitelist"
    assert client.put(base, json={"domains": ["good.example"]}).status_code == 200
    assert client.put(base, json={"domains": [entry]}).status_code == 422
    assert client.get(base).json() == {"domains": ["good.example"]}

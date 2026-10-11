"""Production static routing, isolation from API routes and missing-build errors."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from censearch.frontend import install_frontend


def test_frontend_routes_and_assets(settings, tmp_path):
    settings.frontend_dir = tmp_path / "frontend"
    settings.console_dir = tmp_path / "console"
    for root, pages in [(settings.frontend_dir, ["index.html", "signup.html", "app/index.html", "assets/app.js", "legal/privacy-policy/index.html"]), (settings.console_dir, ["index.html", "assets/console.js"])]:
        for name in pages:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)
    app = FastAPI()
    @app.get("/api/example")
    def example():
        return {"real": True}
    install_frontend(app, settings)
    with TestClient(app) as client:
        for url in ["/", "/app/", "/signup.html", "/legal/privacy-policy/", "/console/"]:
            response = client.get(url)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
        assert client.get('/app', follow_redirects=False).status_code == 307
        assert client.get('/assets/app.js').text == 'assets/app.js'
        assert client.get('/console/assets/console.js').text == 'assets/console.js'
        assert client.get('/api/example').json() == {"real": True}
        for url in ['/api/missing', '/assets/missing.js', '/.env', '/%2e%2e/secret']:
            assert client.get(url).status_code == 404


def test_frontend_missing_build(settings, tmp_path):
    settings.frontend_dir = tmp_path / 'missing'
    settings.console_dir = tmp_path / 'missing-console'
    app = FastAPI()
    install_frontend(app, settings)
    with TestClient(app) as client:
        for url in ['/', '/app/']:
            response = client.get(url)
            assert response.status_code == 503
            assert response.json()['error']['code'] == 'frontend_not_built'

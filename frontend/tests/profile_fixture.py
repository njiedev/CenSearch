"""Disposable backend with face-free images for profile UI checks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
import tempfile
import socket
import threading
import time
from contextlib import contextmanager
import numpy as np
from PIL import Image, ImageDraw
import uvicorn
from censearch.config import Settings
from censearch.db import Store, Person, Reference, Original, CrawlRun, Scan, Case
from censearch.api import create_app
from censearch.evidence import EvidenceStore

@contextmanager
def profile_fixture():
    with tempfile.TemporaryDirectory(prefix='censearch-profile-check-') as directory:
        folder = Path(directory)
        settings = Settings(_env_file=None, LIKENESS_DATA_DIR=folder, openai_api_key='', obj_endpoint='', obj_bucket='', obj_access_key='', obj_secret_key='', facecheck_api_token='', CENSEARCH_EMAIL_ENABLED=False, resend_api_key='')
        store = Store(folder)
        evidence = EvidenceStore(settings)
        photo = Image.new('RGB', (480, 360), '#24222c')
        draw = ImageDraw.Draw(photo)
        draw.rectangle((64, 64, 416, 296), outline='#8b6fc5', width=4)
        draw.text((175, 172), 'TEST IMAGE - NO FACE', fill='white')
        photo.save(folder / 'test.png')
        with store.session.begin() as session:
            session.add(Person(id='profile-test', name='Profile test', consent='Synthetic local UI test. No person or face in these images.', development_fixture=True))
            session.flush()
            for i in range(2):
                saved = evidence.put('profile-test', f'references/test-{i}.png', (folder / 'test.png').read_bytes())
                session.add(Reference(person_id='profile-test', filename=f'test-face-placeholder-{i}.png', path=saved['path'], sha256=saved['sha256'], quality={}, embedding=np.ones(128, dtype=np.float32).tobytes()))
            saved = evidence.put('profile-test', 'originals/test.png', (folder / 'test.png').read_bytes())
            original = Original(person_id='profile-test', filename='test-original.png', path=saved['path'], sha256=saved['sha256'], ownership_statement='Synthetic test')
            session.add(original)
            run = CrawlRun(config={}, identity_version='test', status='completed', metrics={})
            session.add(run)
            session.flush()
            for url in ('https://news.example.com/page', 'https://notexample.com/page'):
                scan = Scan(run_id=run.id, page_url=url, image_url=url+'.png', identity_version='test', status='matched')
                session.add(scan)
                session.flush()
                session.add(Case(person_id='profile-test', scan_id=scan.id, original_id=original.id, page_url=url, image_url=scan.image_url, match_type='both', band='match', score=.8, face_band='match', face_score=.8, copy_relation='exact', photo_relation='same_photo', evidence={'image': saved}))
        store.engine.dispose()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(create_app(settings), host='127.0.0.1', port=port, log_level='error'))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 30
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError('Profile test server did not start')
                time.sleep(.1)
            yield f'http://127.0.0.1:{port}', folder / 'test.png'
        finally:
            server.should_exit = True
            thread.join(timeout=15)
            if thread.is_alive():
                raise RuntimeError('Profile test server did not stop')

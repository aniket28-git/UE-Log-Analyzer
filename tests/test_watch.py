from pathlib import Path
import sys
import time
import threading

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.watcher import poll_until_changed


class TestPollUntilChanged:
    def test_returns_when_file_modified(self, tmp_path):
        f = tmp_path / "test.log"
        f.write_text("initial")

        def modify():
            time.sleep(0.15)
            f.write_text("modified")

        t = threading.Thread(target=modify, daemon=True)
        t.start()
        poll_until_changed(f, interval=0.05)
        t.join(timeout=2.0)
        assert f.read_text() == "modified"

    def test_returns_when_file_created(self, tmp_path):
        f = tmp_path / "new.log"

        def create():
            time.sleep(0.15)
            f.write_text("created")

        t = threading.Thread(target=create, daemon=True)
        t.start()
        # File doesn't exist yet — last mtime starts at 0.0, creation triggers return
        poll_until_changed(f, interval=0.05)
        t.join(timeout=2.0)
        assert f.exists()

    def test_does_not_return_prematurely(self, tmp_path):
        f = tmp_path / "stable.log"
        f.write_text("stable")
        returned = threading.Event()

        def poll():
            poll_until_changed(f, interval=0.05)
            returned.set()

        t = threading.Thread(target=poll, daemon=True)
        t.start()
        # Wait a short time — should NOT have returned yet (file unchanged)
        time.sleep(0.12)
        assert not returned.is_set()
        # Now modify to let it return
        f.write_text("changed")
        returned.wait(timeout=1.0)
        assert returned.is_set()

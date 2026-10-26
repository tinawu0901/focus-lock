"""Verify the packaged stdio protocol in an isolated local data directory."""
import io
import json
import os
import subprocess
import tempfile
import sys
import time
from pathlib import Path
from focus_lock.native_host import read_message, write_message


def main():
    project = Path(__file__).parent
    release = project / (sys.argv[1] if len(sys.argv) > 1 else "dist/checkbox-picker")
    with tempfile.TemporaryDirectory(dir=project) as root:
        environment = os.environ.copy(); environment["LOCALAPPDATA"] = root
        data_root = Path(root) / "FocusLock"; data_root.mkdir()
        (data_root / "browser-tabs-request.json").write_text(json.dumps({"browser": "edge", "expires_at": time.time() + 60}))
        frame = io.BytesIO(); write_message(frame, {"browser": "edge", "revision": "test", "applied": True, "protocol": 3,
            "tabs": [{"title": "測試分頁", "url": "https://example.com/"}]})
        result = subprocess.run([str(release / "FocusLockBrowserHost.exe")],
                                input=frame.getvalue(), capture_output=True, env=environment, timeout=30)
        assert result.returncode == 0, result.stderr
        policy = read_message(io.BytesIO(result.stdout))
        assert policy["active"] is False
        status = json.loads((Path(root) / "FocusLock/browser-edge.json").read_text())
        assert status["revision"] == "test" and status["applied"] is True
        assert status["protocol"] == 3 and status["tabs"][0]["title"] == "測試分頁"
        print("Packaged native host: framed JSON, on-demand tab snapshot, isolated storage, clean exit verified.")


if __name__ == "__main__": main()

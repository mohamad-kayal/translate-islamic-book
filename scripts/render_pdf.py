"""Render a book's HTML to PDF via headless Chrome.

The print styles in out/convert.py set an A5 `@page` size and a ~14pt body, so the
finished PDF reads large on a phone. Chrome honours the CSS page size, so no paper
flags are passed here.

Headless Chrome sometimes writes the PDF but never exits, so we don't wait on the
process: we poll for the output file to appear and stop growing, then kill Chrome.

    python -m scripts.render_pdf <book.html> <book.pdf>
"""
import os
import signal
import subprocess
import sys
import tempfile
import time
from shutil import which

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome-stable",
    "chromium",
    "chrome",
]

TIMEOUT_S = 180      # hard cap; big books render in ~30s
STABLE_S = 2.5       # PDF is done once its size holds this long


def _chrome():
    for c in CHROME_CANDIDATES:
        if os.path.sep in c:
            if os.path.exists(c):
                return c
        elif which(c):
            return c
    raise RuntimeError("No Chrome/Chromium found (looked in %s)" % ", ".join(CHROME_CANDIDATES))


def render(html_path, pdf_path):
    html_path = os.path.abspath(html_path)
    pdf_path = os.path.abspath(pdf_path)
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
    with tempfile.TemporaryDirectory() as profile:
        proc = subprocess.Popen(
            [_chrome(), "--headless=new", "--disable-gpu", "--no-sandbox",
             "--no-first-run", "--no-default-browser-check", "--disable-crash-reporter",
             "--user-data-dir=" + profile, "--no-pdf-header-footer",
             "--virtual-time-budget=20000", "--run-all-compositor-stages-before-draw",
             "--print-to-pdf=" + pdf_path, "file://" + html_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.time() + TIMEOUT_S
        last, stable_at = -1, None
        try:
            while time.time() < deadline:
                if proc.poll() is not None:
                    break                                   # Chrome exited on its own
                sz = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0
                if sz > 1000 and sz == last:
                    if stable_at is None:
                        stable_at = time.time()
                    elif time.time() - stable_at >= STABLE_S:
                        break                               # PDF written and stable
                else:
                    stable_at = None
                last = sz
                time.sleep(0.5)
        finally:
            if proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
    if not (os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1000):
        raise RuntimeError("render produced no PDF: %s" % pdf_path)
    return pdf_path


if __name__ == "__main__":
    print(render(sys.argv[1], sys.argv[2]))

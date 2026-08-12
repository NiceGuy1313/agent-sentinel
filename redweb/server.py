import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ACCESS_LOG = Path(os.environ.get("REDWEB_ACCESS_LOG", "/tmp/redweb_access.log"))


class LoggedRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format, *args):
        message = f"{self.command} {self.path} | {format % args}\n"
        with ACCESS_LOG.open("a", encoding="utf-8") as log_file:
            log_file.write(message)
        super().log_message(format, *args)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8282), LoggedRequestHandler).serve_forever()

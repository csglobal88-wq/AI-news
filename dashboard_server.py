"""
대시보드 로컬 서버
- dashboard.html을 웹서버로 제공
- /api/refresh 호출 시 뉴스 수집/요약 실행
- http://localhost:8080 에서 접속
"""

import json
import os
import subprocess
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PORT = 8080
PROJECT_DIR = Path(__file__).parent


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/dashboard.html'

        if self.path == '/api/refresh':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            def run_summary():
                subprocess.run(
                    [str(PROJECT_DIR / 'venv' / 'bin' / 'python'), str(PROJECT_DIR / 'news_summary.py')],
                    cwd=str(PROJECT_DIR),
                )

            thread = threading.Thread(target=run_summary)
            thread.start()

            self.wfile.write(json.dumps({"status": "started"}).encode())
            return

        if self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            data_file = PROJECT_DIR / 'news_data.json'
            if data_file.exists():
                data = json.loads(data_file.read_text(encoding='utf-8'))
                self.wfile.write(json.dumps({"updated_at": data.get("updated_at", "")}).encode())
            else:
                self.wfile.write(json.dumps({"updated_at": ""}).encode())
            return

        return super().do_GET()

    def log_message(self, format, *args):
        pass


def main():
    os.chdir(str(PROJECT_DIR))
    server = HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    print(f"Dashboard 서버 시작: http://localhost:{PORT}")
    print("Tailscale 접속: http://<Tailscale IP>:8080")
    print("종료하려면 Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버 종료")
        server.server_close()


if __name__ == '__main__':
    main()

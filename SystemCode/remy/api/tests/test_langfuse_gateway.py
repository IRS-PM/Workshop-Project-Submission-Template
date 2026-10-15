import http.client
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import httpx

from api.core import langfuse_gateway


class GatewayTest(unittest.TestCase):
    def test_passwordless_proxy_and_local_security_boundary(self):
        received = []
        real_client = httpx.Client

        def upstream(request):
            received.append(request)
            body = json.dumps({"path": request.url.path, "cookie": request.headers.get("cookie", "")}).encode()
            return httpx.Response(200, stream=httpx.ByteStream(body),
                                  headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"})

        def proxy_client(**kwargs):
            return real_client(transport=httpx.MockTransport(upstream), **kwargs)

        server = ThreadingHTTPServer(("127.0.0.1", 0), langfuse_gateway.Gateway)
        base = "http://127.0.0.1:" + str(server.server_port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(os.environ, {"LANGFUSE_DASHBOARD_URL": base}), \
                 patch.object(langfuse_gateway, "session_cookie", return_value="next-auth.session-token=operator") as login, \
                 patch.object(langfuse_gateway.httpx, "Client", side_effect=proxy_client), \
                 real_client(base_url=base, timeout=5, trust_env=False) as client:
                response = client.get("/api/auth/session", headers={"cookie": "pref=1; next-auth.session-token=invalid"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["cookie"], "pref=1; next-auth.session-token=operator")
                self.assertEqual(response.headers["X-Frame-Options"], "DENY")
                self.assertNotIn("Access-Control-Allow-Origin", response.headers)
                self.assertEqual(login.call_count, 1)
                public = client.get("/api/public/traces/fixture", headers={"Authorization": "Basic fixture"})
                self.assertEqual(public.status_code, 200)
                self.assertEqual(public.json()["cookie"], "")
                self.assertEqual(received[-1].headers["Authorization"], "Basic fixture")
                self.assertEqual(login.call_count, 1)
                for headers in [{"Host": "evil.test"}, {"Origin": "http://evil.test"},
                                {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors"}]:
                    self.assertEqual(client.get("/api/auth/session", headers=headers).status_code, 403)
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
                connection.request("GET", "http://evil.test/path")
                self.assertEqual(connection.getresponse().status, 400)
                connection.close()
                self.assertEqual(client.post("/api/trpc/test", headers={"Transfer-Encoding": "chunked"}).status_code, 411)
                self.assertEqual(client.get("/health", headers={"Host": "localhost:3030"}).json()["path"], "/api/public/health")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()

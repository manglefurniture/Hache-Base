import json
import os
import socket
import tempfile
import threading
import unittest

from runner_socket import RunnerServer


class RunnerSocketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "runner.sock")
        self.operations = []
        def perform(operation, nonce):
            self.operations.append((operation, nonce))
            if operation.get("operation") == "drop":
                raise PermissionError("No arbitrary DDL")
            return 1
        self.server = RunnerServer(self.path, perform, allowed_uid=os.getuid())
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def send(self, message, path=None):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(path or self.path)
            client.sendall(message)
            result = b""
            while not result.endswith(b"\n"):
                part = client.recv(4096)
                if not part:
                    break
                result += part
            return json.loads(result)

    def test_peer_uid_must_match(self):
        alt = os.path.join(self.tmp.name, "blocked.sock")
        other = RunnerServer(alt, lambda *_: 100,
                             allowed_uid=os.getuid() + 1)
        thread = threading.Thread(target=other.serve_forever,
                                  kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        try:
            answer = self.send(b'{"operation":{},"nonce":null}\\n', alt)
            self.assertEqual(answer, {"ok": False, "error": "Operation rejected"})
        finally:
            other.shutdown()
            other.server_close()
            thread.join(timeout=2)

    def test_valid_structured_request(self):
        operation = {"database": "sandbox", "operation": "update"}
        payload = json.dumps({"operation": operation, "nonce": None}).encode()+b"\n"
        self.assertEqual(self.send(payload), {"ok": True, "affected_rows": 1})
        self.assertEqual(self.operations, [(operation, None)])

    def test_arbitrary_sql_command_rejected(self):
        result = self.send(b'{"sql":"DROP DATABASE sandbox"}\n')
        self.assertFalse(result["ok"])
        self.assertEqual(self.operations, [])

    def test_executor_error_redacted(self):
        result = self.send(b'{"operation":{"operation":"drop"},"nonce":null}\n')
        self.assertEqual(result, {"ok": False, "error": "Operation rejected"})

    def test_oversized_request_rejected(self):
        result = self.send(b"{" + b"x"*9000 + b"}\n")
        self.assertFalse(result["ok"])
        self.assertEqual(self.operations, [])

    def test_missing_newline_rejected(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(self.path)
            client.sendall(b'{"operation":{},"nonce":null}')
            client.shutdown(socket.SHUT_WR)
            self.assertFalse(json.loads(client.recv(4096))["ok"])


if __name__ == "__main__":
    unittest.main()

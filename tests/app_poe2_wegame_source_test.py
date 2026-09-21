import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from uuid import uuid4

from server.app.poe2.imports.sources.wegame import collect_wegame
from server.app.poe2.imports.urls import parse_character_url


class WeGameSourceTest(unittest.TestCase):
    def test_ipc_contract_and_owner_binding(self):
        ref = parse_character_url('https://www.wegame.com.cn/helper/poe2/#/share/example', 'wegame')
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'collector.sock')
            server = socket.socket(socket.AF_UNIX)
            server.bind(path)
            server.listen(1)
            received = []
            def serve():
                connection, _ = server.accept()
                with connection:
                    received.append(json.loads(connection.makefile('rb').readline()))
                    connection.sendall(b'{"ok":true,"snapshot":{"schema_version":1,"jewels":{"status":"missing"}}}\n')
            thread = threading.Thread(target=serve)
            thread.start()
            owner = uuid4()
            result = collect_wegame(ref, owner_id=owner, socket_path=path)
            thread.join(2)
            server.close()
            self.assertEqual(result['jewels']['status'], 'missing')
            self.assertEqual(set(received[0]), {'version','canonical_url','owner_key'})
            self.assertNotEqual(received[0]['owner_key'], str(owner))
            self.assertEqual(len(received[0]['owner_key']), 64)

    def test_unavailable_socket_is_retryable_connection_error(self):
        ref = parse_character_url('https://www.wegame.com.cn/helper/poe2/#/share/example', 'wegame')
        with self.assertRaises(ConnectionError):
            collect_wegame(ref, owner_id=uuid4(), socket_path='/tmp/poe2-nonexistent-collector.sock')


if __name__ == '__main__':
    unittest.main()

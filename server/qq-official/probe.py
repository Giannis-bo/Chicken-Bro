"""Read-only QQ gateway probe. Never sends a group message or invokes AI."""
import argparse
import json
from pathlib import Path
import time

from server.app.channels.qq_official.client import OfficialClient
from server.app.channels.qq_official.gateway import GatewaySession, connect_gateway, poll_gateway


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--credentials', required=True)
    parser.add_argument('--seconds', type=int, default=45)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.credentials).read_text())
    client = OfficialClient(data['appId'], data['appSecret'])
    session = GatewaySession()
    events = []
    def dispatch(packet):
        d = packet.get('d')
        if isinstance(d, dict):
            events.append({'type': packet.get('t'), 'groupOpenId': d.get('group_openid'),
                           'groupNumber': d.get('group_id'), 'fields': sorted(d)})
    deadline = time.monotonic() + min(300, max(1, args.seconds))
    try:
        with connect_gateway(client.gateway_url()) as socket:
            while time.monotonic() < deadline:
                poll_gateway(socket, session, dispatch, client.access_token())
                if events: break
        result = {'gatewayReady': session.ready, 'events': events}
        target = Path(args.output)
        target.write_text(json.dumps(result))
        target.chmod(0o600)
        print(json.dumps(result))
    finally:
        client.close()


if __name__ == '__main__': main()

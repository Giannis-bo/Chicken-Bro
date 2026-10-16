"""QQ gateway session: heartbeat, resume and durable dispatch ordering."""
import json
import time


class Reconnect(RuntimeError):
    pass


class GatewaySession:
    def __init__(self):
        self.session_id = self.seq = None
        self.interval = None
        self.next_heartbeat = 0
        self.awaiting_ack = False
        self.ready = False

    def handle(self, packet, send, dispatch, token, *, now=None):
        now = time.monotonic() if now is None else now
        if not isinstance(packet, dict):
            raise Reconnect('invalid gateway payload')
        op = packet.get('op')
        if op == 10:
            d = packet.get('d')
            interval = d.get('heartbeat_interval') if isinstance(d, dict) else None
            if type(interval) is not int or not 1000 <= interval <= 120000:
                raise Reconnect('invalid heartbeat interval')
            self.interval, self.next_heartbeat = interval / 1000, now + interval / 1000
            self.awaiting_ack, self.ready = False, False
            data = {'token': 'QQBot ' + token}
            if self.session_id is not None and self.seq is not None:
                send({'op': 6, 'd': {**data, 'session_id': self.session_id, 'seq': self.seq}})
            else:
                send({'op': 2, 'd': {**data, 'intents': 1 << 25, 'shard': [0, 1]}})
        elif op == 11:
            self.awaiting_ack = False
        elif op == 1:
            send({'op': 1, 'd': self.seq})
            self.awaiting_ack = True
            self.next_heartbeat = now + (self.interval or 45)
        elif op in (7, 9):
            if op == 9:
                self.session_id = self.seq = None
            self.ready = False
            raise Reconnect('gateway requested reconnect')
        elif op == 0:
            if packet.get('t') == 'READY':
                sid = packet.get('d', {}).get('session_id')
                if not isinstance(sid, str) or not sid:
                    raise Reconnect('missing gateway session')
                self.session_id, self.ready = sid, True
            elif packet.get('t') == 'RESUMED':
                self.ready = True
            else:
                dispatch(packet)
            # Advance only after the callback persisted the event.
            if type(packet.get('s')) is int:
                self.seq = packet['s']

    def heartbeat(self, send, *, now=None):
        now = time.monotonic() if now is None else now
        if self.interval is not None and now >= self.next_heartbeat:
            if self.awaiting_ack:
                self.ready = False
                raise Reconnect('gateway heartbeat timed out')
            send({'op': 1, 'd': self.seq})
            self.awaiting_ack = True
            self.next_heartbeat = now + self.interval


def connect_gateway(url):
    # Installed only in the dedicated official QQ environment.
    from websockets.sync.client import connect
    return connect(url, legacy=True, proxy=None, open_timeout=10, close_timeout=5,
                   max_size=2 * 1024**2, max_queue=64, compression=None)


def poll_gateway(socket, session, dispatch, token, timeout=0.5):
    send = lambda packet: socket.send(json.dumps(packet))
    session.heartbeat(send)
    try:
        raw = socket.recv(timeout=timeout)
    except TimeoutError:
        return
    try:
        packet = json.loads(raw)
    except (ValueError, TypeError):
        raise Reconnect('invalid gateway JSON') from None
    session.handle(packet, send, dispatch, token)

"""Bounded OneBot WebSocket client for the fixed same-host NapCat endpoint.

No automatic action retries: losing a send receipt is an uncertain delivery.
"""
import base64
from collections import deque
import hashlib
import json
import os
import select
import socket
import struct
import time
from uuid import uuid4


class OneBotError(RuntimeError):
    pass


class OneBotRejected(OneBotError):
    """NapCat 4.18.28 websocket schema rejection before action execution (1400)."""
    pass


class OneBot:
    def __init__(self,token,*,port=13001):
        if not token or '\r' in token or '\n' in token:
            raise ValueError('invalid OneBot credential')
        self.events=deque()
        self.on_event=None
        self.sock=socket.create_connection(('127.0.0.1',port),timeout=10)
        try:
            key=base64.b64encode(os.urandom(16)).decode()
            lines=['GET / HTTP/1.1',f'Host: 127.0.0.1:{port}','Upgrade: websocket',
                   'Connection: Upgrade','Sec-WebSocket-Version: 13','Sec-WebSocket-Key: '+key,
                   'Authorization: Bearer '+token]
            self.sock.sendall(('\r\n'.join(lines)+'\r\n\r\n').encode())
            header=bytearray()
            while not header.endswith(b'\r\n\r\n') and len(header)<8192:
                header.extend(self._read(1))
            lines=header.decode('ascii').split('\r\n')
            headers={p.split(':',1)[0].lower():p.split(':',1)[1].strip() for p in lines[1:] if ':' in p}
            expected=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            if not header.endswith(b'\r\n\r\n') or lines[0].split()[1]!='101' or headers.get('sec-websocket-accept')!=expected:
                raise OneBotError('WebSocket handshake rejected')
        except BaseException:
            self.close();raise

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def close(self):self.sock.close()

    def _read(self,size):
        result=bytearray()
        while len(result)<size:
            chunk=self.sock.recv(size-len(result))
            if not chunk:raise OneBotError('WebSocket closed')
            result.extend(chunk)
        return bytes(result)

    def _send(self,body,opcode=1):
        mask=os.urandom(4);n=len(body)
        if n<126:header=bytes([128|opcode,128|n])
        elif n<65536:header=bytes([128|opcode,254])+struct.pack('!H',n)
        else:header=bytes([128|opcode,255])+struct.pack('!Q',n)
        self.sock.sendall(header+mask+bytes(b^mask[i%4] for i,b in enumerate(body)))

    def receive(self,timeout=1):
        if not select.select([self.sock],[],[],timeout)[0]:return None
        parts=bytearray();started=False
        deadline=time.monotonic()+10
        while True:
            if time.monotonic()>=deadline:raise OneBotError('WebSocket frame timeout')
            self.sock.settimeout(max(.1,deadline-time.monotonic()))
            first,second=self._read(2);n=second&127;opcode=first&15
            if n==126:n=struct.unpack('!H',self._read(2))[0]
            elif n==127:n=struct.unpack('!Q',self._read(8))[0]
            if first&112 or second&128 or len(parts)+n>2*1024**2:
                raise OneBotError('Invalid WebSocket frame')
            if opcode>=8 and (n>125 or not first&128):raise OneBotError('Invalid control frame')
            body=self._read(n)
            if opcode==8:raise OneBotError('WebSocket closed')
            if opcode==9:self._send(body,10);continue
            if opcode==10:continue
            if (opcode==1 and started) or (opcode==0 and not started) or opcode not in (0,1):
                raise OneBotError('Invalid text frame sequence')
            started=True;parts.extend(body)
            if first&128:
                try:result=json.loads(parts)
                except (ValueError,UnicodeError):raise OneBotError('Invalid JSON message') from None
                if not isinstance(result,dict):raise OneBotError('Invalid OneBot message')
                if result.get('retcode')==1403:raise OneBotError('OneBot authentication rejected')
                return result

    def _event(self,result):
        if result.get('post_type'):
            if self.on_event is not None:
                self.on_event(result)
                return
            if len(self.events)>=256:raise OneBotError('Event queue full')
            self.events.append(result)

    def call(self,action,params=None):
        echo=uuid4().hex
        self._send(json.dumps({'action':action,'params':params or {},'echo':echo}).encode())
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            result=self.receive(timeout=min(1,max(.01,deadline-time.monotonic())))
            if result is None:continue
            if result.get('echo')==echo:
                if result.get('status')!='ok' or result.get('retcode')!=0:
                    if result.get('retcode')==1400:raise OneBotRejected('OneBot request rejected before execution')
                    raise OneBotError('OneBot action failed retcode='+str(result.get('retcode') if type(result.get('retcode')) is int else 'unknown'))
                return result.get('data')
            self._event(result)
        raise OneBotError('OneBot receipt timeout')

    def poll(self,timeout=.5):
        result=self.receive(timeout)
        if result:self._event(result)

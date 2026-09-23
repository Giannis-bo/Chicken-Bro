import base64
import hashlib
import json
import socket
import struct
from threading import Thread
import unittest


def frame(value):
    data=json.dumps(value).encode()
    return bytes([0x81,len(data)])+data if len(data)<126 else b'\x81\x7e'+struct.pack('!H',len(data))+data


def request(sock):
    def exact(n):
        b=b''
        while len(b)<n:b+=sock.recv(n-len(b))
        return b
    first,second=exact(2);n=second&127
    if n==126:n=struct.unpack('!H',exact(2))[0]
    mask=exact(4);body=exact(n)
    return json.loads(bytes(b^mask[i%4] for i,b in enumerate(body)))


class OneBotTransportTest(unittest.TestCase):
    def server(self,handler):
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1)
        self.port=listener.getsockname()[1]
        def run():
            with listener:
                sock,_=listener.accept()
                with sock:
                    data=b''
                    while not data.endswith(b'\r\n\r\n'):data+=sock.recv(1)
                    headers=dict(line.split(': ',1) for line in data.decode().split('\r\n') if ': ' in line)
                    key=base64.b64encode(hashlib.sha1((headers['Sec-WebSocket-Key']+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
                    sock.sendall(('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+key+'\r\n\r\n').encode())
                    handler(sock,headers)
        self.thread=Thread(target=run,daemon=True);self.thread.start()

    def test_authorization_header_echo_and_interleaved_event(self):
        from server.app.channels.qq.onebot import OneBot
        seen=[]
        def handler(sock,headers):
            seen.append(headers['Authorization'])
            r=request(sock)
            sock.sendall(frame({'post_type':'message','message_id':77})+frame({'echo':r['echo'],'status':'ok','retcode':0,'data':{'user_id':12345}}))
        self.server(handler)
        with OneBot('token',port=self.port) as client:
            result=client.call('get_login_info')
            self.assertEqual(result['user_id'],12345)
            self.assertEqual(client.events.popleft()['message_id'],77)
        self.thread.join(2);self.assertEqual(seen,['Bearer token'])

    def test_101_followed_by_1403_is_rejected(self):
        from server.app.channels.qq.onebot import OneBot,OneBotError
        self.server(lambda s,h:s.sendall(frame({'retcode':1403,'status':'failed'})))
        with OneBot('bad',port=self.port) as client:
            with self.assertRaises(OneBotError):client.call('get_login_info')
        self.thread.join(2)

    def test_lost_send_receipt_is_reported_once_without_retry(self):
        from server.app.channels.qq.onebot import OneBot,OneBotError
        requests=[]
        def handler(sock,headers):requests.append(request(sock)['action'])
        self.server(handler)
        with OneBot('token',port=self.port) as client:
            with self.assertRaises((OneBotError,OSError)):client.call('send_group_msg',{'group_id':56789,'message':[]})
        self.thread.join(2);self.assertEqual(requests,['send_group_msg'])

    def test_received_events_are_delivered_before_receipt_loss(self):
        from server.app.channels.qq.onebot import OneBot,OneBotError
        seen=[]
        def handler(sock,headers):
            request(sock)
            sock.sendall(frame({'post_type':'message','message_id':88}))
        self.server(handler)
        with OneBot('token',port=self.port) as client:
            client.on_event=seen.append
            with self.assertRaises((OneBotError,OSError)):client.call('send_group_msg')
        self.thread.join(2)
        self.assertEqual([e['message_id'] for e in seen],[88])

if __name__=='__main__':unittest.main()

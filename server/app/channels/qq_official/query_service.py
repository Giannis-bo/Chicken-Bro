"""Bounded network reads leave the QQ websocket thread free for heartbeats."""
from concurrent.futures import ThreadPoolExecutor
import time
from .query_commands import QueryRequest, format_result


class QueryService:
    def __init__(self, repository, source, *, battle_source=None, battle_writer=None, guidance_writer=None):
        self.repository, self.source = repository, source
        self.battle_source = battle_source
        self.battle_writer = battle_writer
        self.guidance_writer = guidance_writer
        self.pool = ThreadPoolExecutor(max_workers=2,thread_name_prefix='qq-character-query')
        self.active = {}

    def advance(self):
        for future, job in list(self.active.items()):
            if not future.done(): continue
            packet = None
            try:
                packet = future.result()
                if job['request']['kind'] == 'guidance':
                    text = packet['text']; failed = False
                elif job['request']['kind'].startswith('battle_'):
                    from .battle_commands import format_battle
                    text = format_battle(packet, job['request']['kind'])
                    failed = packet.get('status') == 'unavailable'
                else:
                    text = format_result(packet); failed=False; packet=None
            except Exception:
                if job['request']['kind'] == 'guidance':
                    from .guidance import fallback_packet
                    packet = fallback_packet(); text = packet['text']; failed = False
                else:
                    text = '数据查询失败，请稍后重新发送查询命令。'; failed=True; packet=None
            self.repository.finish_query(job,text,failed=failed,packet=packet)
            del self.active[future]
        while len(self.active) < 2:
            job = self.repository.claim_query()
            if not job: break
            future = self.pool.submit(self._query,job)
            self.active[future] = job

    def _query(self,job):
        if job['request']['kind'] == 'guidance':
            from .guidance import fallback_packet
            return self.guidance_writer.reply(job['request']['message']) if self.guidance_writer is not None else fallback_packet()
        if job['request']['kind'].startswith('battle_'):
            from .battle_commands import BattleRequest
            from .battle_source import BattleSource
            source = self.battle_source or BattleSource()
            start=time.monotonic()
            packet=source.query(BattleRequest(**job['request']),context=job.get('battle_context'))
            if self.battle_writer is not None:
                packet=self.battle_writer.apply(packet,timeout_seconds=max(0,min(60,140-(time.monotonic()-start))))
            return packet
        return self.source.query(QueryRequest(**job['request']))

    def close(self):
        self.pool.shutdown(wait=False,cancel_futures=True)

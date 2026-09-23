"""Nonblocking social coordinator; it never owns the OneBot socket."""
from concurrent.futures import ThreadPoolExecutor
import logging
import time
from server.app.channels.qq.companion_domain import ReplyDraft
LOG=logging.getLogger(__name__)

def must_reply_draft(decision,fallback_text):
    return decision.draft if decision and decision.draft and (decision.draft.text or decision.draft.sticker_id) else ReplyDraft(fallback_text)

def should_discard_proactive(*,decision_seq,current_seq):return decision_seq!=current_seq

class CompanionService:
    def __init__(self,repository,observations,model,*,proactive=True,professional=None,memory=None,stickers=None):
        self.repository,self.observations,self.model=repository,observations,model
        self.proactive,self.professional,self.memory,self.stickers=proactive,professional,memory,stickers
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='qq-social')
        self.future=None;self.job=None;self.next_recover=0
    def close(self):self.pool.shutdown(wait=True,cancel_futures=True)
    def observe(self,event):
        self.observations.append(event)
        if event.mentioned:self.repository.ensure_response(event,kind='mention',context_seq=self.observations.latest_seq(event.bot,event.group))
    def _decide(self,job):
        e=job['event'];context=self.observations.context(e.bot,e.group,now=time.time())
        if not any(x.message_id==e.message_id for x in context):context.append(e)
        facts=self.memory.facts(e.bot,e.group,tuple({x.sender for x in context})) if self.memory else []
        media=bool(self.stickers and hasattr(self.stickers,'prepare'))
        labels,images=self.stickers.prepare(e.group) if media else (self.stickers.labels() if self.stickers else (),())
        arguments=dict(must_reply=job['kind']=='mention',facts=facts,stickers=labels,target=e.message_id,
            recent_replies=self.repository.recent_replies(e.group),images=images,meme_search_available=media)
        decision=self.model.decide(context,**arguments)
        if decision.meme_query and media:
            try:labels,images=self.stickers.search(e,decision.meme_query)
            except (ValueError,OSError,TimeoutError):labels,images=[],[]
            arguments.update(stickers=labels,images=images,meme_search_available=False)
            decision=self.model.decide(context,**arguments)
        # A model can only select a resource it was actually shown in this decision.
        if decision.draft and decision.draft.sticker_id not in (None,*(x['id'] for x in labels)):
            from dataclasses import replace
            decision=replace(decision,draft=ReplyDraft(decision.draft.text or '这个梗鸡哥接住了。',quote=decision.draft.quote))
        return decision,context
    def tick(self,now=None):
        now=time.time() if now is None else now
        if now>=self.next_recover:
            self.repository.reconcile_observations();self.repository.recover();self.next_recover=now+10
            for group in self.repository.groups:self.observations.prune(self.repository.bot,group)
        if self.future is not None:
            if not self.future.done():return
            job=self.job;e=job['event'];decision=None;context=[]
            try:decision,context=self.future.result()
            except Exception as error:LOG.warning('qq_social_failed kind=%s',type(error).__name__)
            self.future=None;self.job=None
            current=self.observations.latest_seq(e.bot,e.group)
            stale=job['kind']=='proactive' and (not self.proactive or now-e.timestamp>120 or
                should_discard_proactive(decision_seq=job['context_seq'],current_seq=current))
            if self.memory and decision and not stale:
                try:self.memory.apply_decisions(e.bot,e.group,decision.memories,context)
                except (TypeError,ValueError):LOG.warning('qq_memory_proposal_rejected')
            professional=False
            if not stale and decision and decision.action in ('wow_read','wow_sim') and self.professional:
                professional=self.professional(job,decision)
            if not professional:
                if job['kind']=='mention':
                    fallback='鸡哥刚刚脑子卡了一下，这句再聊一次？'
                    if decision and decision.action in ('wow_read','wow_sim'):
                        fallback='把你自己的角色链接和具体想比较的东西给鸡哥，咱再细看。'
                    draft=must_reply_draft(decision,fallback)
                    self.repository.complete_response(job['id'],job['lease_token'],draft)
                elif not stale and decision and decision.action=='reply' and decision.draft:
                    self.repository.complete_response(job['id'],job['lease_token'],decision.draft)
                else:self.repository.silence(job['id'],job['lease_token'])
            self.observations.consume(e.bot,e.group,job['context_seq'])
        job=self.repository.claim_response(lease_seconds=240,proactive_enabled=self.proactive)
        if job is None and self.proactive:
            for group,seq in self.observations.ready_groups(self.repository.bot,self.repository.groups):
                context=self.observations.context(self.repository.bot,group,now=now)
                if not context:self.observations.consume(self.repository.bot,group,seq);continue
                self.repository.ensure_response(context[-1],kind='proactive',context_seq=seq)
                # Already-responded anchors must not be reconsidered forever.
                self.observations.consume(self.repository.bot,group,seq)
                job=self.repository.claim_response(lease_seconds=240,proactive_enabled=self.proactive)
                if job:break
        if job:
            self.job=job;self.future=self.pool.submit(self._decide,job)

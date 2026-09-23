"""Trusted group envelopes and bounded model output values."""
from dataclasses import dataclass
from typing import Literal

Scope = Literal['social', 'wow_read', 'wow_sim']

@dataclass(frozen=True)
class GroupEvent:
    bot: str
    group: str
    sender: str
    message_id: str
    timestamp: float
    text: str
    display_name: str
    mentioned: bool
    reply_to: str | None = None
    attachment: bool = False

@dataclass(frozen=True)
class ReplyDraft:
    text: str
    sticker_id: str | None = None
    quote: bool = False

@dataclass(frozen=True)
class CompanionDecision:
    action: Literal['silent', 'reply', 'wow_read', 'wow_sim']
    draft: ReplyDraft | None = None
    target_message_id: str | None = None
    memories: tuple = ()
    meme_query: str | None = None

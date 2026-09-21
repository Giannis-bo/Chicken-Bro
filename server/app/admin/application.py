"""Read-only operational analytics and a single server-configured QQ administrator."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo
import re
from server.app.identity.domain import Principal
from server.app.identity.test_accounts import TEST_ACCOUNT_IDS
from server.app.platform.config import AppSettings

BEIJING = ZoneInfo('Asia/Shanghai')

class AdminError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)

@dataclass(frozen=True)
class DateWindow:
    start: datetime
    end: datetime
    start_date: str
    end_date: str

class AnalyticsRepository(Protocol):
    def is_qq_owner(self, user_id: UUID, appid: str) -> bool: ...
    def overview(self, window: DateWindow, appid: str, game: str = 'wow') -> dict: ...

def date_window(start: str | None, end: str | None, now: datetime | None = None) -> DateWindow:
    today = (now or datetime.now(timezone.utc)).astimezone(BEIJING).date()
    try:
        if any(v is not None and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', v) is None for v in (start, end)):
            raise ValueError()
        last = date.fromisoformat(end) if end else today
        first = date.fromisoformat(start) if start else last - timedelta(days=6)
        if first > last or last > today or (last-first).days >= 366:
            raise ValueError()
        return DateWindow(datetime.combine(first, time.min, BEIJING).astimezone(timezone.utc),
            datetime.combine(last+timedelta(days=1), time.min, BEIJING).astimezone(timezone.utc),
            first.isoformat(), last.isoformat())
    except (ValueError, OverflowError):
        raise AdminError('ADMIN_DATE_INVALID', '请选择有效日期，最多 366 天，结束日期不能晚于今天') from None

class AdminApplication:
    def __init__(self, *, repository: AnalyticsRepository, settings: AppSettings):
        self.repository, self.settings = repository, settings

    def allowed(self, principal: Principal) -> bool:
        return (bool(self.settings.admin_user_id) and principal.session_kind == 'web_cookie'
            and principal.user_id not in TEST_ACCOUNT_IDS.values()
            and str(principal.user_id) == self.settings.admin_user_id
            and bool(self.settings.qq_appid)
            and self.repository.is_qq_owner(principal.user_id, self.settings.qq_appid))

    def require(self, principal: Principal):
        if not self.allowed(principal):
            raise AdminError('ADMIN_FORBIDDEN', '此账号没有运营后台访问权限', 403)

    def overview(self, principal: Principal, start: str | None, end: str | None, game: str = 'wow') -> dict:
        self.require(principal)
        if game not in ('wow', 'poe2'):
            raise AdminError('ADMIN_GAME_INVALID', '请选择魔兽世界或 POE2')
        window = date_window(start, end)
        try:
            return self.repository.overview(window, self.settings.qq_appid, game)
        except Exception:
            raise AdminError('ADMIN_UNAVAILABLE', '统计服务暂不可用，请稍后重试', 503) from None

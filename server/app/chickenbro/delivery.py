"""Bounded subscription to server-owned generation; disconnect only unsubscribes."""
from collections import deque
from threading import BoundedSemaphore, Condition, Event, Thread
import logging

_LOG = logging.getLogger(__name__)


class DeliveryCapacity(Exception):
    pass


class BackgroundDelivery:
    def __init__(self, source, *, capacity: BoundedSemaphore, buffer_limit=64):
        self._source = iter(source)
        self._capacity = capacity
        self._condition = Condition()
        self._items = deque()
        self._bytes = 0
        self._limit = buffer_limit
        self._closed = False
        self._error = None
        self.finished = Event()
        if not capacity.acquire(blocking=False):
            raise DeliveryCapacity()
        try:
            first = next(self._source)  # Validate/persist admission on the request thread.
        except BaseException:
            capacity.release()
            raise
        self._run_id = getattr(first, 'run_id', '')
        self._first = first
        self._first_pending = True
        try:
            Thread(target=self._produce, name='chat-generation', daemon=True).start()
        except BaseException:
            try:
                close = getattr(self._source, 'close', None)
                if close:
                    close()
            finally:
                capacity.release()
            raise

    @staticmethod
    def _size(item):
        return len(getattr(item, 'text', '')) * 4 + 1024

    def _produce(self):
        try:
            for item in self._source:
                with self._condition:
                    if self._closed:
                        continue
                    size = self._size(item)
                    if len(self._items) >= self._limit or self._bytes + size > 262144:
                        self._detach('slow_subscriber')
                    else:
                        self._items.append(item)
                        self._bytes += size
                    self._condition.notify_all()
        except Exception as error:
            with self._condition:
                self._error = error
            _LOG.error('chat_generation_failed run_id=%s reason=producer_exception exception_type=%s',
                       self._run_id, type(error).__name__)
        finally:
            try:
                close = getattr(self._source, 'close', None)
                if close:
                    close()
            finally:
                self._capacity.release()
                with self._condition:
                    self.finished.set()
                    self._condition.notify_all()

    def __iter__(self):
        return self

    def __next__(self):
        with self._condition:
            if self._first_pending:
                self._first_pending = False
                return self._first
            while not self._items and not self._closed and not self.finished.is_set():
                self._condition.wait()
            if self._closed:
                raise StopIteration
            if self._items:
                item = self._items.popleft()
                self._bytes -= self._size(item)
                return item
            if self._error:
                raise self._error
            raise StopIteration

    def _detach(self, reason):
        if not self._closed:
            log = _LOG.debug if self.finished.is_set() else _LOG.warning
            log('chat_subscription_closed run_id=%s reason=%s generation_continues=%s',
                self._run_id, reason, not self.finished.is_set())
        self._closed = True
        self._items.clear()
        self._bytes = 0

    def close(self):
        with self._condition:
            self._detach('connection_closed')
            self._condition.notify_all()

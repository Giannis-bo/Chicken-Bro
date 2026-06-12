const {
  AUTH_TOKEN_STORAGE_KEY,
  analyticsClientId,
  analyticsHeaders,
  analyticsSessionId,
  apiUrl,
  isInsecureHttpUrl
} = require('./api-client')

const ANALYTICS_QUEUE_STORAGE_KEY = 'wow_analytics_event_queue'
const MAX_QUEUE_SIZE = 200
const MAX_BATCH_SIZE = 20

let flushing = false

function storageGet(key) {
  if (typeof wx === 'undefined' || typeof wx.getStorageSync !== 'function') return ''
  return wx.getStorageSync(key) || ''
}

function storageSet(key, value) {
  if (typeof wx !== 'undefined' && typeof wx.setStorageSync === 'function') {
    wx.setStorageSync(key, value)
  }
}

function parseQueue() {
  const stored = storageGet(ANALYTICS_QUEUE_STORAGE_KEY)
  if (!stored) return []
  if (Array.isArray(stored)) return stored
  try {
    const parsed = JSON.parse(stored)
    return Array.isArray(parsed) ? parsed : []
  } catch (error) {
    return []
  }
}

function saveQueue(queue) {
  storageSet(ANALYTICS_QUEUE_STORAGE_KEY, JSON.stringify(queue.slice(-MAX_QUEUE_SIZE)))
}

function randomEventId() {
  return `evt-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

function currentPageRoute() {
  if (typeof getCurrentPages !== 'function') return ''
  const pages = getCurrentPages()
  const page = pages && pages[pages.length - 1]
  return (page && page.route) || ''
}

function eventPayload(eventName, properties, options) {
  const eventOptions = options || {}
  return {
    eventId: eventOptions.eventId || randomEventId(),
    eventName,
    occurredAt: new Date().toISOString(),
    page: eventOptions.page || currentPageRoute(),
    properties: properties || {}
  }
}

function sendBatch(events) {
  return new Promise((resolve) => {
    if (typeof wx === 'undefined' || typeof wx.request !== 'function') {
      resolve(false)
      return
    }
    const url = apiUrl('/api/analytics/events')
    if (!url) {
      resolve(false)
      return
    }
    const header = {
      ...analyticsHeaders('miniprogram'),
      'Content-Type': 'application/json'
    }
    const token = storageGet(AUTH_TOKEN_STORAGE_KEY)
    if (token && !isInsecureHttpUrl(url)) {
      header.Authorization = `Bearer ${token}`
    }
    wx.request({
      url,
      method: 'POST',
      data: {
        clientId: analyticsClientId(),
        sessionId: analyticsSessionId(),
        platform: 'miniprogram',
        events
      },
      header,
      timeout: 5000,
      success: (res) => resolve(res.statusCode >= 200 && res.statusCode < 300),
      fail: () => resolve(false)
    })
  })
}

function flushAnalyticsEvents() {
  if (flushing) return Promise.resolve(false)
  const queue = parseQueue()
  if (!queue.length) return Promise.resolve(true)
  const batch = queue.slice(0, MAX_BATCH_SIZE)
  flushing = true
  return sendBatch(batch).then((ok) => {
    if (ok) {
      saveQueue(queue.slice(batch.length))
    } else {
      saveQueue(queue)
    }
    return ok
  }).finally(() => {
    flushing = false
  })
}

function trackEvent(eventName, properties, options) {
  if (!/^[a-z][a-z0-9_]{0,79}$/.test(eventName || '')) return Promise.resolve(false)
  const queue = parseQueue()
  queue.push(eventPayload(eventName, properties, options))
  saveQueue(queue)
  return flushAnalyticsEvents()
}

function trackPageView(page, properties) {
  return trackEvent('page_view', { ...(properties || {}), page }, { page })
}

function trackPageLeave(page, startedAt, properties) {
  const durationMs = startedAt ? Math.max(0, Date.now() - startedAt) : 0
  return trackEvent('page_leave', { ...(properties || {}), page, durationMs }, { page })
}

module.exports = {
  ANALYTICS_QUEUE_STORAGE_KEY,
  MAX_QUEUE_SIZE,
  currentPageRoute,
  flushAnalyticsEvents,
  trackEvent,
  trackPageLeave,
  trackPageView
}


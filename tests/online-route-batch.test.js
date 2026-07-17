'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const { maxOnlineRoutesPerRun, requireOnlineRouteBatch } = require('../scripts/online-route-batch')

test('online WeChat validators require explicit resumable two-route batches', () => {
  assert.equal(maxOnlineRoutesPerRun, 2)
  assert.deepEqual([...requireOnlineRouteBatch('news_home,news_detail', 'TEST_ROUTES', ['news_home', 'news_detail'])], ['news_home', 'news_detail'])
  assert.throws(() => requireOnlineRouteBatch('', 'TEST_ROUTES', ['news_home']), /is required/)
  assert.throws(() => requireOnlineRouteBatch('all', 'TEST_ROUTES', ['news_home']), /rejects "all"/)
  assert.throws(() => requireOnlineRouteBatch('news_home,news_detail,build_intel', 'TEST_ROUTES', ['news_home', 'news_detail', 'build_intel']), /limited to 2 routes/)
  assert.throws(() => requireOnlineRouteBatch('unknown', 'TEST_ROUTES', ['news_home']), /unknown TEST_ROUTES/)
})

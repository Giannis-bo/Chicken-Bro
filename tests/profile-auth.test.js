const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

test('profile page exposes WeChat avatar and nickname profile bindings', () => {
  const js = fs.readFileSync('pages/profile/profile.js', 'utf8')
  const wxml = fs.readFileSync('pages/profile/profile.wxml', 'utf8')

  assert.match(js, /saveProfile/)
  assert.match(js, /saveProfileDraft/)
  assert.match(js, /onChooseAvatar/)
  assert.match(js, /onNicknameInput/)
  assert.match(js, /onNicknameConfirm/)
  assert.match(wxml, /open-type="chooseAvatar"/)
  assert.match(wxml, /bindchooseavatar="onChooseAvatar"/)
  assert.match(wxml, /bindinput="onNicknameInput"/)
  assert.match(wxml, /bindconfirm="onNicknameConfirm"/)
  assert.match(wxml, /placeholder="点击填写微信昵称"/)
})

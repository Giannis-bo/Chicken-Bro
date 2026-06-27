const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

function read(path) {
  return fs.readFileSync(path, 'utf8')
}

test('mini program pages emit the first-pass analytics event surface', () => {
  const files = [
    'pages/news/news.js',
    'pages/news/list.js',
    'pages/news/detail.js',
    'pages/builds/builds.js',
    'pages/builds/detail.js',
    'pages/pve/pve.js',
    'pages/pve/detail.js',
    'pages/simulator/simulator.js',
    'pages/simulator/simc.js',
    'pages/simulator/wcl.js',
    'pages/simulator/tasks.js',
    'pages/simulator/task-detail.js',
    'pages/common/analytics-client.js'
  ].map(read).join('\n')

  ;[
    'page_view',
    'page_leave',
    'news_home_view',
    'news_article_open',
    'news_article_view',
    'news_list_view',
    'news_source_copy',
    'builds_home_view',
    'builds_query_open',
    'builds_detail_view',
    'builds_class_select',
    'builds_spec_select',
    'builds_talent_scenario_select',
    'builds_talent_node_toggle',
    'builds_gear_candidate_select',
    'builds_simc_entry_click',
    'pve_home_view',
    'pve_module_open',
    'pve_module_view',
    'simulator_home_view',
    'simulator_module_open',
    'simc_template_confirm',
    'simc_template_submit',
    'wcl_submit',
    'task_list_view',
    'task_detail_view'
  ].forEach((eventName) => {
    assert.match(files, new RegExp(eventName))
  })
})

test('websim emits browser analytics events without raw profile tracking', () => {
  const app = read('websim/app.js')
  ;[
    'websim_view',
    'websim_tab_switch',
    'websim_class_change',
    'websim_spec_change',
    'websim_talent_toggle',
    'websim_gear_add',
    'websim_gear_remove',
    'websim_profile_generate',
    'websim_simulate_submit',
    'websim_simulate_result'
  ].forEach((eventName) => {
    assert.match(app, new RegExp(eventName))
  })
  assert.doesNotMatch(app, /trackWebsimEvent\('websim_profile_generate'[\s\S]*profile:/)
})

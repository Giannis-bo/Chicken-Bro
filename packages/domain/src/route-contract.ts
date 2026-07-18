// Current 14-route API, navigation, and storage contract.

export const routePolicy = {
  "registeredRouteCount": 14,
  "tabRoots": [
    "pages/news/news",
    "pages/builds/builds",
    "pages/simulator/simulator",
    "pages/profile/profile"
  ],
  "unknownQueryKeys": "ignore_without_promoting_to_product_state"
} as const

export const transportRules = [
  "Preserve Result envelopes as payload/fromFallback/error instead of converting fallback data into success.",
  "Do not attach bearer tokens to insecure HTTP URLs.",
  "Only the explicitly listed guest-capable simulator calls may proceed over insecure development HTTP.",
  "Preserve X-Wow-Client-Id, X-Wow-Session-Id, and X-Wow-Platform headers on shared requestJson and analytics transports; news requests currently do not attach them.",
  "Fallback metrics, identity, readiness, source claims, and WoW object mappings must remain visibly untrusted or blocked."
] as const

export const routeContracts = [
  {
    "routeKey": "news_home",
    "targetPage": "pages/news/news",
    "navigation": "tab_root",
    "query": [],
    "endpoints": [
      "news.home"
    ],
    "storage": [
      "news.lastRefreshedAt",
      "news.homeFavorite",
      "news.savedArticleIds"
    ],
    "outgoing": [
      "news_list",
      "news_detail"
    ],
    "criticalParity": [
      "pull_or_manual_refresh",
      "freshness_state",
      "article_and_channel_navigation",
      "active_news_tab"
    ]
  },
  {
    "routeKey": "news_list",
    "targetPage": "pages/news/list",
    "navigation": "pushed",
    "query": [
      {
        "name": "type",
        "required": false,
        "default": "metric"
      },
      {
        "name": "key",
        "required": false,
        "default": "today"
      },
      {
        "name": "value",
        "required": false,
        "decode": "decodeURIComponent"
      }
    ],
    "endpoints": [
      "news.list"
    ],
    "storage": [],
    "outgoing": [
      "news_detail"
    ],
    "criticalParity": [
      "back_navigation",
      "query_title_and_filter",
      "empty_replaces_rows",
      "no_tabbar"
    ]
  },
  {
    "routeKey": "news_detail",
    "targetPage": "pages/news/detail",
    "navigation": "pushed",
    "query": [
      {
        "name": "id",
        "required": true
      }
    ],
    "endpoints": [
      "news.article"
    ],
    "storage": [],
    "outgoing": [],
    "criticalParity": [
      "missing_id_state",
      "not_found_state",
      "source_url_copy",
      "translated_body_fidelity",
      "no_tabbar"
    ]
  },
  {
    "routeKey": "specialization_home/builds_home",
    "targetPage": "pages/builds/builds",
    "navigation": "tab_root",
    "query": [],
    "endpoints": [
      "builds.home"
    ],
    "storage": [],
    "outgoing": [
      "build_intel",
      "current_spec_workbench",
      "talent_simulator",
      "gear_detail",
      "SimC_submit",
      "tasks_list"
    ],
    "criticalParity": [
      "four_first_version_actions",
      "build_intel_entry",
      "workbench_entry",
      "fallback_normalization",
      "active_builds_tab"
    ]
  },
  {
    "routeKey": "current_spec_workbench",
    "targetPage": "pages/builds/workbench",
    "navigation": "pushed",
    "query": [
      {
        "name": "spec",
        "required": false,
        "decode": "decodeURIComponent"
      },
      {
        "name": "from",
        "required": false,
        "compatibilityBehavior": "accepted_but_not_used_for_state"
      }
    ],
    "endpoints": [
      "builds.home",
      "templates.list",
      "websim.talents",
      "websim.gear"
    ],
    "storage": [
      "templates.local"
    ],
    "outgoing": [
      "talent_simulator",
      "gear_detail",
      "SimC_submit",
      "chickenbro_chat",
      "profile/templates"
    ],
    "criticalParity": [
      "selected_spec",
      "derived_readiness",
      "blockers",
      "four_module_actions",
      "evidence_rows"
    ]
  },
  {
    "routeKey": "build_intel",
    "targetPage": "pages/builds/intel",
    "navigation": "pushed",
    "query": [],
    "endpoints": [
      "builds.intel"
    ],
    "storage": [],
    "outgoing": [
      "talent_simulator"
    ],
    "criticalParity": [
      "real_route_retained",
      "source_and_window_state",
      "no_invented_rank_or_tier"
    ]
  },
  {
    "routeKey": "talent_simulator",
    "targetPage": "pages/builds/talent-simulator",
    "navigation": "pushed_editor",
    "query": [
      {
        "name": "spec",
        "required": false,
        "decode": "decodeURIComponent"
      }
    ],
    "endpoints": [
      "builds.home",
      "websim.bootstrap",
      "websim.talents",
      "websim.talentImport",
      "talents.validate",
      "talents.export",
      "templates.upsert"
    ],
    "storage": [
      "templates.local"
    ],
    "outgoing": [],
    "criticalParity": [
      "class_spec_hero_selection",
      "tree_point_rules",
      "community_import",
      "save_reset",
      "catalog_blockers"
    ]
  },
  {
    "routeKey": "gear_detail",
    "targetPage": "pages/builds/detail",
    "navigation": "pushed_editor",
    "query": [
      {
        "name": "query",
        "required": false,
        "default": "talents",
        "targetValue": "gear"
      },
      {
        "name": "spec",
        "required": false,
        "decode": "decodeURIComponent"
      }
    ],
    "redirects": [
      {
        "when": "query=talents",
        "to": "talent_simulator"
      }
    ],
    "endpoints": [
      "builds.home",
      "builds.detail",
      "websim.gear",
      "websim.gearResolve",
      "websim.gearCommunityImport",
      "websim.gearStatSnapshots",
      "websim.talentImport",
      "templates.upsert"
    ],
    "storage": [
      "templates.local",
      "simc.buildContext"
    ],
    "outgoing": [
      "SimC_submit"
    ],
    "criticalParity": [
      "slot_detail_loading",
      "legal_enhancements",
      "verified_stats",
      "template_save_apply",
      "simc_route_handoff_and_compatibility_storage_write"
    ]
  },
  {
    "routeKey": "simulator_home",
    "targetPage": "pages/simulator/simulator",
    "navigation": "tab_root_with_input_dock",
    "query": [],
    "endpoints": [
      "chickenbro.messages"
    ],
    "storage": [
      "simulator.guestId"
    ],
    "outgoing": [],
    "criticalParity": [
      "tab_chat_entry",
      "suggested_prompts",
      "bounded_evidence",
      "retry",
      "input_and_tabbar_do_not_overlap"
    ]
  },
  {
    "routeKey": "SimC_submit",
    "targetPage": "pages/simulator/simc",
    "navigation": "pushed_editor",
    "query": [
      {
        "name": "from",
        "required": false
      },
      {
        "name": "spec",
        "required": false,
        "decode": "decodeURIComponent"
      },
      {
        "name": "classKey",
        "required": false,
        "decode": "decodeURIComponent"
      },
      {
        "name": "specKey",
        "required": false,
        "decode": "decodeURIComponent"
      },
      {
        "name": "scenario",
        "required": false,
        "decode": "decodeURIComponent"
      }
    ],
    "endpoints": [
      "builds.home",
      "templates.list",
      "templates.upsert",
      "websim.gearStats",
      "simulator.tasks",
      "simulator.analyze"
    ],
    "storage": [
      "templates.local",
      "simulator.guestId"
    ],
    "outgoing": [],
    "criticalParity": [
      "workbench_context",
      "template_selectors",
      "active_task_gate",
      "confirm_before_submit",
      "no_fake_result_preview"
    ]
  },
  {
    "routeKey": "chickenbro_chat",
    "targetPage": "pages/simulator/chickenbro",
    "navigation": "pushed_with_input_dock",
    "query": [
      {
        "name": "from",
        "required": false,
        "decode": "decodeURIComponent"
      },
      {
        "name": "classKey",
        "required": false,
        "decode": "decodeURIComponent"
      },
      {
        "name": "specKey",
        "required": false,
        "decode": "decodeURIComponent"
      },
      {
        "name": "spec",
        "required": false,
        "decode": "decodeURIComponent"
      },
      {
        "name": "scenario",
        "required": false,
        "decode": "decodeURIComponent"
      }
    ],
    "endpoints": [
      "chickenbro.messages"
    ],
    "storage": [
      "simulator.guestId"
    ],
    "outgoing": [],
    "criticalParity": [
      "bounded_workbench_context",
      "new_topic",
      "message_limit",
      "fallback_is_labeled",
      "input_safe_area"
    ]
  },
  {
    "routeKey": "tasks_list",
    "targetPage": "pages/simulator/tasks",
    "navigation": "pushed",
    "query": [
      {
        "name": "from",
        "required": false,
        "default": "direct"
      }
    ],
    "endpoints": [
      "simulator.tasks"
    ],
    "storage": [
      "simulator.guestId"
    ],
    "outgoing": [
      "task_detail",
      "SimC_submit",
      "current_spec_workbench"
    ],
    "criticalParity": [
      "refresh_on_resume",
      "fallback_does_not_fake_tasks",
      "status_rows",
      "empty_state_actions"
    ]
  },
  {
    "routeKey": "task_detail",
    "targetPage": "pages/simulator/task-detail",
    "navigation": "pushed",
    "query": [
      {
        "name": "id",
        "required": true
      }
    ],
    "endpoints": [
      "simulator.task"
    ],
    "storage": [
      "simulator.guestId"
    ],
    "outgoing": [],
    "criticalParity": [
      "missing_id_state",
      "task_status",
      "backend_only_metrics",
      "preview_simc_suppresses_dps",
      "context_and_preparation_rows"
    ]
  },
  {
    "routeKey": "profile/templates",
    "targetPage": "pages/profile/profile",
    "navigation": "tab_root",
    "query": [],
    "endpoints": [
      "auth.wechatLogin",
      "profile.upsert",
      "templates.list",
      "templates.delete"
    ],
    "storage": [
      "auth.token",
      "auth.user",
      "auth.expiresAt",
      "profile.local",
      "templates.local"
    ],
    "outgoing": [],
    "criticalParity": [
      "local_first_profile_draft",
      "avatar_and_nickname",
      "template_counts",
      "template_delete",
      "active_profile_tab"
    ]
  }
] as const

export const endpointContracts = [
  {
    "id": "news.home",
    "method": "GET",
    "path": "/api/news/home",
    "auth": "none",
    "transport": "direct_request_without_analytics_headers",
    "fallback": "seed_with_explicit_fallback_state"
  },
  {
    "id": "news.list",
    "method": "GET",
    "path": "/api/news/list?type=&key=&value=",
    "auth": "none",
    "transport": "direct_request_without_analytics_headers",
    "fallback": "filtered_seed_with_explicit_fallback_state"
  },
  {
    "id": "news.article",
    "method": "GET",
    "path": "/api/news/article?id=",
    "auth": "none",
    "transport": "direct_request_without_analytics_headers",
    "fallback": "matching_seed_or_not_found"
  },
  {
    "id": "builds.home",
    "method": "GET",
    "path": "/api/builds/home",
    "auth": "none",
    "fallback": "local_snapshot_normalized_as_stale_without_remote_supplementation"
  },
  {
    "id": "builds.intel",
    "method": "GET",
    "path": "/api/builds/intel",
    "auth": "none",
    "fallback": "server_payload_builder"
  },
  {
    "id": "builds.detail",
    "method": "GET",
    "path": "/api/builds/detail?id=",
    "auth": "none",
    "fallback": "server_payload_builder"
  },
  {
    "id": "websim.bootstrap",
    "method": "GET",
    "path": "/api/websim/bootstrap",
    "auth": "none",
    "timeoutMs": 6000
  },
  {
    "id": "websim.talents",
    "method": "GET",
    "path": "/api/websim/talents?class=&spec=&hero=",
    "auth": "none",
    "timeoutMs": 6000
  },
  {
    "id": "websim.talentImport",
    "method": "GET",
    "path": "/api/websim/talents/import?class=&spec=&hero=",
    "auth": "none",
    "timeoutMs": 30000
  },
  {
    "id": "talents.validate",
    "method": "POST",
    "path": "/api/talents/validate",
    "auth": "none",
    "fallback": "blocked"
  },
  {
    "id": "talents.export",
    "method": "POST",
    "path": "/api/talents/export",
    "auth": "none",
    "fallback": "blocked"
  },
  {
    "id": "talents.import",
    "method": "POST",
    "path": "/api/talents/import",
    "auth": "none",
    "fallback": "blocked"
  },
  {
    "id": "websim.gear",
    "method": "GET",
    "path": "/api/websim/gear?class=&spec=&compact=&mode=&slot=",
    "auth": "none",
    "timeoutMs": 30000
  },
  {
    "id": "websim.gearStats",
    "method": "POST",
    "path": "/api/websim/gear/stats",
    "auth": "none",
    "timeoutMs": 60000
  },
  {
    "id": "websim.gearResolve",
    "method": "POST",
    "path": "/api/websim/gear/resolve",
    "auth": "none",
    "timeoutMs": 30000
  },
  {
    "id": "websim.gearCommunityImport",
    "method": "POST",
    "path": "/api/websim/gear/community-import",
    "auth": "none",
    "timeoutMs": 30000
  },
  {
    "id": "websim.gearStatSnapshots",
    "method": "POST",
    "path": "/api/websim/gear/stat-snapshots",
    "auth": "none",
    "timeoutMs": 30000
  },
  {
    "id": "simulator.analyze",
    "method": "POST",
    "path": "/api/simulator/analyze",
    "auth": "optional_by_call",
    "allowInsecureGuestRequest": true,
    "timeoutMs": 90000
  },
  {
    "id": "simulator.tasks",
    "method": "GET",
    "path": "/api/simulator/tasks?guestId=",
    "auth": "requested",
    "allowInsecureGuestRequest": true
  },
  {
    "id": "simulator.task",
    "method": "GET",
    "path": "/api/simulator/task?id=&guestId=",
    "auth": "requested",
    "allowInsecureGuestRequest": true
  },
  {
    "id": "chickenbro.messages",
    "method": "POST",
    "path": "/api/chickenbro/messages",
    "auth": "requested",
    "allowInsecureGuestRequest": true,
    "timeoutMs": 90000
  },
  {
    "id": "auth.wechatLogin",
    "method": "POST",
    "path": "/api/auth/wechat-login",
    "auth": "none",
    "requires": "wx.login code"
  },
  {
    "id": "profile.upsert",
    "method": "POST",
    "path": "/api/me/profile",
    "auth": "required_https"
  },
  {
    "id": "templates.list",
    "method": "GET",
    "path": "/api/me/build-templates?type=",
    "auth": "required_https",
    "fallback": "local_templates"
  },
  {
    "id": "templates.upsert",
    "method": "POST",
    "path": "/api/me/build-templates",
    "auth": "required_https",
    "fallback": "local_template"
  },
  {
    "id": "templates.delete",
    "method": "DELETE",
    "path": "/api/me/build-templates?id=",
    "auth": "required_https",
    "fallback": "local_delete"
  }
] as const

export const storageContracts = [
  {
    "id": "api.base",
    "key": "wow_backend_api_base_url"
  },
  {
    "id": "api.newsBaseCompat",
    "key": "wow_news_api_base_url"
  },
  {
    "id": "auth.token",
    "key": "wow_backend_auth_token"
  },
  {
    "id": "auth.user",
    "key": "wow_backend_auth_user"
  },
  {
    "id": "auth.expiresAt",
    "key": "wow_backend_auth_expires_at"
  },
  {
    "id": "profile.local",
    "key": "wow_backend_profile"
  },
  {
    "id": "analytics.clientId",
    "key": "wow_analytics_client_id"
  },
  {
    "id": "analytics.sessionId",
    "key": "wow_analytics_session_id"
  },
  {
    "id": "analytics.sessionStartedAt",
    "key": "wow_analytics_session_started_at"
  },
  {
    "id": "analytics.queue",
    "key": "wow_analytics_event_queue"
  },
  {
    "id": "news.lastRefreshedAt",
    "key": "wow_news_last_refreshed_at"
  },
  {
    "id": "news.homeFavorite",
    "key": "wow_news_home_favorite"
  },
  {
    "id": "news.savedArticleIds",
    "key": "wow_news_saved_article_ids"
  },
  {
    "id": "simulator.guestId",
    "key": "wow_simulator_guest_id"
  },
  {
    "id": "templates.local",
    "key": "wow_build_templates_v1"
  },
  {
    "id": "simc.buildContext",
    "key": "wow_simc_build_context",
    "compatibilityBehavior": "written_by_gear_detail_but_not_read_by_any_registered_route"
  }
] as const

export type RouteContract = (typeof routeContracts)[number]
export type RouteKey = RouteContract['routeKey']
export type RegisteredPagePath = RouteContract['targetPage']
export type EndpointContract = (typeof endpointContracts)[number]
export type EndpointId = EndpointContract['id']
export type StorageContract = (typeof storageContracts)[number]
export type StorageId = StorageContract['id']

export function routeContract(routeKey: RouteKey): RouteContract {
  const route = routeContracts.find((candidate) => candidate.routeKey === routeKey)
  if (!route) throw new Error(`Unknown route contract: ${routeKey}`)
  return route
}

export function endpointContract(endpointId: EndpointId): EndpointContract {
  const endpoint = endpointContracts.find((candidate) => candidate.id === endpointId)
  if (!endpoint) throw new Error(`Unknown endpoint contract: ${endpointId}`)
  return endpoint
}

export function storageKey(storageId: StorageId): string {
  const storage = storageContracts.find((candidate) => candidate.id === storageId)
  if (!storage) throw new Error(`Unknown storage contract: ${storageId}`)
  return storage.key
}

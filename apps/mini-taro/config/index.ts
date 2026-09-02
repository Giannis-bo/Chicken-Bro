import path from 'node:path'

import { defineConfig } from '@tarojs/cli'

const appRoot = path.resolve(__dirname, '..')
const repositoryRoot = path.resolve(appRoot, '../..')
const target = process.env['TARO_ENV'] === 'h5' ? 'h5' : 'weapp'
const configuredOutputRoot = process.env['WOW_TARO_OUTPUT_ROOT']?.trim()
const outputRoot = configuredOutputRoot || `dist/${target}`
const isolatedBuild = process.env['WOW_TARO_ISOLATED_BUILD'] === '1'
const productionBuild = process.env['NODE_ENV'] === 'production'
const configuredBackendApiBaseUrl = (process.env['WOW_BACKEND_API_BASE_URL'] ?? '').trim()
const configuredApiV2Prefix = (
  process.env['WOW_API_V2_PREFIX']?.trim()
  || process.env['WOW_WEB_AUTH_API_PREFIX']?.trim()
  || '/api/v2'
).replace(/\/+$/u, '')
const configuredWebAuthApiPrefix = (
  process.env['WOW_WEB_AUTH_API_PREFIX']?.trim()
  || configuredApiV2Prefix
).replace(/\/+$/u, '')
if (configuredApiV2Prefix !== configuredWebAuthApiPrefix) {
  throw new Error('WOW_API_V2_PREFIX and WOW_WEB_AUTH_API_PREFIX must match')
}
if (!/^\/[A-Za-z0-9][A-Za-z0-9/_-]*$/u.test(configuredWebAuthApiPrefix)) {
  throw new Error('WOW_WEB_AUTH_API_PREFIX must be a slash-prefixed path')
}
const configuredWebCsrfCookieName = process.env['WOW_WEB_CSRF_COOKIE_NAME']?.trim() || '__Host-chickenbro-csrf'
if (!configuredWebCsrfCookieName.startsWith('__Host-') || /\s/u.test(configuredWebCsrfCookieName)) {
  throw new Error('WOW_WEB_CSRF_COOKIE_NAME must use the __Host- prefix')
}
const configuredH5PublicPath = process.env['WOW_H5_PUBLIC_PATH']?.trim() || '/'
if (!/^\/[A-Za-z0-9._/-]*\/?$/u.test(configuredH5PublicPath) || configuredH5PublicPath.includes('//')) {
  throw new Error('WOW_H5_PUBLIC_PATH must be a safe slash-prefixed path')
}
const runtimeGitHead = process.env['WOW_WEAPP_RUNTIME_GIT_HEAD']?.trim() ?? ''
const runtimeSourceHash = process.env['WOW_WEAPP_RUNTIME_SOURCE_HASH']?.trim() ?? ''
const sharedCompileIncludes = [
  path.join(repositoryRoot, 'packages/domain/src'),
  path.join(repositoryRoot, 'packages/api-client/src'),
]

export default defineConfig<'webpack5'>({
  projectName: 'wow-mini-taro',
  date: '2026-07-11',
  designWidth: 390,
  deviceRatio: {
    390: 750 / 390,
  },
  sourceRoot: 'src',
  outputRoot,
  framework: 'react',
  compiler: {
    type: 'webpack5',
    prebundle: {
      enable: false,
    },
  },
  cache: {
    enable: !productionBuild && !isolatedBuild,
  },
  defineConstants: {
    __WOW_BACKEND_API_BASE_URL__: JSON.stringify(configuredBackendApiBaseUrl),
    __WOW_API_V2_PREFIX__: JSON.stringify(configuredApiV2Prefix),
    __WOW_WEB_AUTH_API_PREFIX__: JSON.stringify(configuredWebAuthApiPrefix),
    __WOW_WEB_CSRF_COOKIE_NAME__: JSON.stringify(configuredWebCsrfCookieName),
    __WOW_WEAPP_RUNTIME_GIT_HEAD__: JSON.stringify(runtimeGitHead),
    __WOW_WEAPP_RUNTIME_SOURCE_HASH__: JSON.stringify(runtimeSourceHash),
  },
  csso: {
    config: {
      calc: false,
    },
  },
  alias: {
    '@tarojs/plugin-framework-react/dist/runtime': path.join(
      appRoot,
      'node_modules/@tarojs/plugin-framework-react/dist/runtime',
    ),
    '@wow-mini/domain': path.join(repositoryRoot, 'packages/domain/src'),
    '@wow-mini/api-client': path.join(repositoryRoot, 'packages/api-client/src'),
  },
  h5: {
    publicPath: configuredH5PublicPath.endsWith('/') ? configuredH5PublicPath : `${configuredH5PublicPath}/`,
    staticDirectory: 'static',
    router: {
      mode: 'hash',
    },
    devServer: {
      host: '127.0.0.1',
      port: 10086,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8790',
          changeOrigin: true,
        },
      },
    },
    compile: {
      include: sharedCompileIncludes,
    },
    postcss: {
      autoprefixer: {
        enable: true,
        config: {},
      },
      cssModules: {
        enable: true,
        config: {
          namingPattern: 'module',
          generateScopedName: '[name]__[local]___[hash:base64:5]',
        },
      },
    },
  },
  mini: {
    compile: {
      include: sharedCompileIncludes,
    },
    postcss: {
      cssModules: {
        enable: true,
        config: {
          namingPattern: 'module',
          generateScopedName: '[name]__[local]___[hash:base64:5]',
        },
      },
      './config/postcss-weapp-compatible.cjs': {
        enable: true,
        config: {
          childTags: ['view', 'text', 'image', 'button'],
        },
      },
    },
  },
})

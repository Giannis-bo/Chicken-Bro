import path from 'node:path'

import { defineConfig } from '@tarojs/cli'

import { isImmutableRemoteAssetRoot } from '../../../packages/assets-manifest/src/runtime-root.cjs'

const appRoot = path.resolve(__dirname, '..')
const repositoryRoot = path.resolve(appRoot, '../..')
const target = process.env['TARO_ENV'] === 'h5' ? 'h5' : 'weapp'
const configuredOutputRoot = process.env['WOW_TARO_OUTPUT_ROOT']?.trim()
const outputRoot = configuredOutputRoot || `dist/${target}`
const isolatedBuild = process.env['WOW_TARO_ISOLATED_BUILD'] === '1'
const productionBuild = process.env['NODE_ENV'] === 'production'
const configuredBackendApiBaseUrl = (
  process.env['WOW_BACKEND_API_BASE_URL']
  ?? process.env['WOW_NEWS_API_BASE_URL']
  ?? ''
).trim()
const configuredAssetRuntimeRoot = process.env['WOW_ASSET_RUNTIME_ROOT']?.trim() ?? ''
if (configuredAssetRuntimeRoot && !isImmutableRemoteAssetRoot(configuredAssetRuntimeRoot)) {
  throw new Error('WOW_ASSET_RUNTIME_ROOT must be an immutable HTTPS path ending in /releases/<release-id>')
}
const configuredRuntimeMediaRoot = process.env['WOW_RUNTIME_MEDIA_ROOT']?.trim() ?? ''
if (configuredRuntimeMediaRoot && !isImmutableRemoteAssetRoot(configuredRuntimeMediaRoot)) {
  throw new Error('WOW_RUNTIME_MEDIA_ROOT must be an immutable HTTPS path ending in /releases/<release-id>')
}
const localAssetRuntime = !configuredAssetRuntimeRoot
const vectorAssetPattern = {
  from: path.join(repositoryRoot, 'packages/design-system/assets/vector-runtime'),
  to: `${outputRoot}/assets/ui-v2/vector-runtime`,
}
const rasterAssetPatterns = [
  {
    from: path.join(repositoryRoot, 'packages/design-system/assets/raster/news-home-v1/runtime/2x'),
    to: `${outputRoot}/assets/ui-v2/raster/news-home-v1/runtime/2x`,
  },
  {
    from: path.join(repositoryRoot, 'packages/design-system/assets/raster/builds-home-v1/runtime/2x'),
    to: `${outputRoot}/assets/ui-v2/raster/builds-home-v1/runtime/2x`,
  },
  {
    from: path.join(repositoryRoot, 'packages/design-system/assets/raster/shared-chrome-v1/runtime/2x'),
    to: `${outputRoot}/assets/ui-v2/raster/shared-chrome-v1/runtime/2x`,
  },
  {
    from: path.join(repositoryRoot, 'packages/design-system/assets/raster/news-list-v1/runtime/2x'),
    to: `${outputRoot}/assets/ui-v2/raster/news-list-v1/runtime/2x`,
  },
  {
    from: path.join(repositoryRoot, 'packages/design-system/assets/raster/news-detail-v1/runtime/2x'),
    to: `${outputRoot}/assets/ui-v2/raster/news-detail-v1/runtime/2x`,
  },
  {
    from: path.join(repositoryRoot, 'packages/design-system/assets/raster/build-intel-v1/runtime/2x'),
    to: `${outputRoot}/assets/ui-v2/raster/build-intel-v1/runtime/2x`,
  },
]
const sharedCompileIncludes = [
  path.join(repositoryRoot, 'packages/design-system/src'),
  path.join(repositoryRoot, 'packages/domain/src'),
  path.join(repositoryRoot, 'packages/api-client/src'),
  path.join(repositoryRoot, 'packages/assets-manifest/src'),
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
    __WOW_ASSET_RUNTIME_ROOT__: JSON.stringify(configuredAssetRuntimeRoot || '/assets/ui-v2'),
    __WOW_RUNTIME_MEDIA_ROOT__: JSON.stringify(configuredRuntimeMediaRoot),
    __WOW_BACKEND_API_BASE_URL__: JSON.stringify(configuredBackendApiBaseUrl),
  },
  csso: {
    config: {
      calc: false,
    },
  },
  copy: {
    // WeChat true devices do not reliably render SVG files or CSS masks. The
    // deterministic PNG derivatives remain local; large raster art still
    // moves to the immutable CDN release.
    patterns: [vectorAssetPattern, ...(localAssetRuntime ? rasterAssetPatterns : [])],
    options: {},
  },
  alias: {
    '@tarojs/plugin-framework-react/dist/runtime': path.join(
      appRoot,
      'node_modules/@tarojs/plugin-framework-react/dist/runtime',
    ),
    '@wow-mini/design-system': path.join(repositoryRoot, 'packages/design-system/src'),
    '@wow-mini/domain': path.join(repositoryRoot, 'packages/domain/src'),
    '@wow-mini/api-client': path.join(repositoryRoot, 'packages/api-client/src'),
    '@wow-mini/assets-manifest': path.join(repositoryRoot, 'packages/assets-manifest/src'),
  },
  h5: {
    publicPath: '/',
    staticDirectory: 'static',
    router: {
      mode: 'hash',
    },
    devServer: {
      host: '127.0.0.1',
      port: 10086,
      proxy: {
        '/wow-api': {
          target: 'http://124.223.51.33',
          changeOrigin: true,
          pathRewrite: { '^/wow-api': '' },
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

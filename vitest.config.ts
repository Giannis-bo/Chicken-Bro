import { defineConfig } from 'vitest/config'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  resolve: {
    alias: {
      '@wow-mini/domain': fileURLToPath(new URL('./packages/domain/src/index.ts', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
    include: [
      'apps/mini-taro/src/features/**/*.test.ts',
      'apps/mini-taro/src/features/**/*.test.tsx',
      'apps/mini-taro/src/pages/auth/**/*.test.ts',
      'apps/mini-taro/src/pages/auth/**/*.test.tsx',
      'apps/mini-taro/src/pages/chickenbro/**/*.test.ts',
      'apps/mini-taro/src/pages/chickenbro/**/*.test.tsx',
      'apps/mini-taro/src/pages/simc/**/*.test.ts',
      'apps/mini-taro/src/pages/simc/**/*.test.tsx',
      'apps/mini-taro/src/web/**/*.test.ts',
      'apps/mini-taro/src/web/**/*.test.tsx',
      'apps/mini-taro/src/tab-bar-items.test.ts',
      'apps/mini-taro/src/tab-bar-state.test.ts',
      'packages/api-client/src/auth-context.test.ts',
      'packages/api-client/src/chat.test.ts',
      'packages/api-client/src/simc.test.ts',
      'packages/api-client/src/transport.test.ts',
      'packages/api-client/src/web-auth.test.ts',
      'packages/domain/src/chat.test.ts',
      'packages/domain/src/simc.test.ts',
      'packages/domain/src/web-auth.test.ts',
    ],
    coverage: {
      reporter: ['text', 'json-summary'],
    },
  },
})

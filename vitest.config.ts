import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    include: [
      'apps/mini-taro/src/**/*.test.ts',
      'apps/mini-taro/src/**/*.test.tsx',
      'packages/**/*.test.ts',
      'packages/**/*.test.tsx',
    ],
    coverage: {
      reporter: ['text', 'json-summary'],
    },
  },
})

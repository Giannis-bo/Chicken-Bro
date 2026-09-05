declare const __WOW_TEST_LOGIN__: boolean

export function isTestLoginEnabled(): boolean {
  return typeof __WOW_TEST_LOGIN__ === 'boolean' && __WOW_TEST_LOGIN__
}

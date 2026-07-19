/// <reference types="@tarojs/taro" />

declare const defineAppConfig: <T>(config: T) => T
declare const definePageConfig: <T>(config: T) => T
declare const defineComponentConfig: <T>(config: T) => T
declare const __WOW_ASSET_RUNTIME_ROOT__: string
declare const __WOW_BACKEND_API_BASE_URL__: string

declare module '*.module.scss' {
  const classes: Readonly<Record<string, string>>
  export default classes
}

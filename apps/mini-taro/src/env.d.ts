/// <reference types="@tarojs/taro" />

declare const defineAppConfig: <T>(config: T) => T
declare const definePageConfig: <T>(config: T) => T
declare const defineComponentConfig: <T>(config: T) => T

declare module '*.module.scss' {
  const classes: Readonly<Record<string, string>>
  export default classes
}

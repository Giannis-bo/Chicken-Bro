import Taro from '@tarojs/taro'

export interface StorageAdapter {
  get<T>(key: string): T | undefined
  set<T>(key: string, value: T): void
  remove(key: string): void
}

export const taroStorage: StorageAdapter = {
  get<T>(key: string): T | undefined {
    const value = Taro.getStorageSync<T>(key)
    return value === '' || value === null ? undefined : value
  },
  set<T>(key: string, value: T): void {
    Taro.setStorageSync(key, value)
  },
  remove(key: string): void {
    Taro.removeStorageSync(key)
  },
}

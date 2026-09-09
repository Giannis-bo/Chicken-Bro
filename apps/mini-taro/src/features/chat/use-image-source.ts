export function useImageSource(dataUrl: string) {
  return {source: dataUrl, failed: false, retry: () => undefined}
}

declare module '@babel/core' {
  export interface TransformOptions {
    plugins?: readonly unknown[]
    [key: string]: unknown
  }

  export interface BabelFileResult {
    code?: string | null
  }

  export function transformSync(code: string, options?: TransformOptions): BabelFileResult | null
}

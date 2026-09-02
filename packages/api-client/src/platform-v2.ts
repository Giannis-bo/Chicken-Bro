import {
  isPlatformReadinessEnvelope,
  type PlatformReadinessEnvelope,
} from '@wow-mini/domain'

import type { ApiResult, ApiTransport } from './transport'
import { apiV2Path } from './api-v2-prefix'


export class PlatformV2Client {
  constructor(private readonly transport: ApiTransport) {}

  readiness(): Promise<ApiResult<PlatformReadinessEnvelope>> {
    return this.transport.request<PlatformReadinessEnvelope>(apiV2Path('/health/readiness'), {
      method: 'GET',
      timeoutMs: 5000,
      auth: false,
      fallback: () => ({ status: 'blocked', requestId: '', components: {} }),
      validate: isPlatformReadinessEnvelope,
    })
  }
}

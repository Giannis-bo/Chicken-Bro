export interface GearRequestToken {
  readonly draftRevision: number
  readonly requestId: number
}

export type GearFencedResult<T> =
  | { readonly status: 'current'; readonly value: T }
  | { readonly status: 'stale' }

export class GearRequestFence {
  private draftRevision = 0
  private resolveRequestId = 0
  private statRequestId = 0
  private importRequestId = 0

  replaceDraft(): void {
    this.draftRevision += 1
    this.resolveRequestId += 1
    this.statRequestId += 1
    this.importRequestId += 1
  }

  beginResolve(): GearRequestToken {
    this.resolveRequestId += 1
    this.statRequestId += 1
    this.importRequestId += 1
    return { draftRevision: this.draftRevision, requestId: this.resolveRequestId }
  }

  isResolveCurrent(token: GearRequestToken): boolean {
    return token.draftRevision === this.draftRevision
      && token.requestId === this.resolveRequestId
  }

  async runResolve<T>(operation: () => Promise<T>): Promise<GearFencedResult<T>> {
    const token = this.beginResolve()
    const value = await operation()
    return this.isResolveCurrent(token)
      ? { status: 'current', value }
      : { status: 'stale' }
  }

  beginStats(): GearRequestToken {
    this.statRequestId += 1
    return { draftRevision: this.draftRevision, requestId: this.statRequestId }
  }

  isStatsCurrent(token: GearRequestToken): boolean {
    return token.draftRevision === this.draftRevision
      && token.requestId === this.statRequestId
  }

  beginImport(): GearRequestToken {
    this.importRequestId += 1
    this.resolveRequestId += 1
    this.statRequestId += 1
    return { draftRevision: this.draftRevision, requestId: this.importRequestId }
  }

  isImportCurrent(token: GearRequestToken): boolean {
    return token.draftRevision === this.draftRevision
      && token.requestId === this.importRequestId
  }
}

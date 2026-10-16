export interface CharacterInput { name: string; realm: string; region?: string }
export interface BoundCharacter { id: string; name: string; realm: string; region: string; sourceUrl: string }
export interface CharacterCollection { items: BoundCharacter[]; selectedId: string | null }

export function isCharacterCollection(value: unknown): value is CharacterCollection {
  if (typeof value !== 'object' || value === null) return false
  const row = value as Record<string, unknown>
  if (Object.keys(row).some(key => !['items', 'selectedId'].includes(key)) || !Array.isArray(row['items']) || row['items'].length > 3) return false
  const ids = new Set<string>()
  for (const item of row['items'] as unknown[]) {
    if (typeof item !== 'object' || item === null) return false
    const entry = item as Record<string, unknown>
    if (Object.keys(entry).length !== 5 || !['id', 'name', 'realm', 'region', 'sourceUrl'].every(key => typeof entry[key] === 'string' && Boolean(entry[key]))) return false
    const bound = item as BoundCharacter
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu.test(bound.id)
      || bound.name.length > 64 || bound.realm.length > 128 || bound.sourceUrl.length > 2048
      || !['cn', 'us', 'eu', 'tw', 'kr'].includes(bound.region) || ids.has(bound.id)) return false
    try {
      const source = new URL(bound.sourceUrl)
      if (source.protocol !== 'https:' || !['raider.io', 'www.raider.io'].includes(source.hostname)
        || source.username || source.password || source.search || source.hash || (source.port && source.port !== '443')) return false
    } catch { return false }
    ids.add(bound.id)
  }
  return row['selectedId'] === null || (typeof row['selectedId'] === 'string' && ids.has(row['selectedId']))
}

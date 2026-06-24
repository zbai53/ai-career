/**
 * Spring Boot stores parsedData as a JSONB column but serialises it to a
 * JSON *string* in the HTTP response (double-encoded).  This utility detects
 * that case and replaces the field with the parsed object in-place so that
 * every consumer can safely treat parsedData as a plain object.
 */
export function parseParsedData<T extends { parsedData: unknown }>(entity: T): T {
  if (typeof entity.parsedData !== 'string') return entity
  try {
    return { ...entity, parsedData: JSON.parse(entity.parsedData) }
  } catch {
    // Malformed JSON — leave as-is rather than crashing; callers already
    // guard against missing fields via the str()/arr() helpers.
    return entity
  }
}

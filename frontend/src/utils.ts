import type { DetectionEvent, RulesConfig } from './types';

// ── Grid Layout ──

/**
 * Return the number of grid columns for a given camera count.
 * 1→1, 2→2, 3~4→2, 5~9→3. Clamps to 1 for n≤0 and 3 for n>9.
 */
export function getGridColumns(n: number): number {
  if (n <= 0) return 1;
  if (n === 1) return 1;
  if (n === 2) return 2;
  if (n <= 4) return 2;
  return 3; // 5~9 and beyond
}

// ── Event Filtering ──

/**
 * Filter events by sub_type. Returns all events when type is 'all' or empty.
 */
export function filterEvents(
  events: DetectionEvent[],
  type: string,
): DetectionEvent[] {
  if (!type || type === 'all') return events;
  return events.filter((e) => e.sub_type === type);
}

// ── Pagination ──

/**
 * Return the slice of events for the given 1-indexed page.
 * Page 1 = items [0, pageSize), Page 2 = items [pageSize, 2*pageSize), etc.
 */
export function paginateEvents(
  events: DetectionEvent[],
  page: number,
  pageSize: number,
): DetectionEvent[] {
  const start = (page - 1) * pageSize;
  return events.slice(start, start + pageSize);
}

// ── Coordinate Transforms ──

/**
 * Convert pixel coordinates to normalised 0~1 coordinates.
 */
export function normalizeCoord(
  px: number,
  py: number,
  w: number,
  h: number,
): [number, number] {
  return [px / w, py / h];
}

/**
 * Convert normalised 0~1 coordinates back to pixel coordinates.
 */
export function denormalizeCoord(
  nx: number,
  ny: number,
  w: number,
  h: number,
): [number, number] {
  return [nx * w, ny * h];
}

/**
 * Convert a single normalised coordinate pair to pixel coordinates on a canvas.
 * Equivalent to denormalizeCoord but named for clarity in Canvas overlay usage.
 */
export function normalizedToPixel(
  nx: number,
  ny: number,
  canvasWidth: number,
  canvasHeight: number,
): [number, number] {
  return [nx * canvasWidth, ny * canvasHeight];
}

// ── Reconnect Backoff ──

/**
 * Calculate exponential backoff delay: min(2^attempt * 1000, 30000) ms.
 * Also exported from useWebSocket.ts — duplicated here for standalone testing.
 */
export function getReconnectDelay(attempt: number): number {
  return Math.min(Math.pow(2, attempt) * 1000, 30_000);
}

// ── Serialisation ──

/**
 * Serialise a RulesConfig object to a JSON string.
 */
export function serializeRulesConfig(config: RulesConfig): string {
  return JSON.stringify(config);
}

// ── Formatting ──

/**
 * Format a byte count to a human-readable string (e.g. "24.5MB", "1.2GB").
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)}GB`;
}

/**
 * Format a timestamp (ISO string or Unix seconds) to "YYYY-MM-DD HH:mm:ss".
 */
export function formatTimestamp(ts: string | number): string {
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts);
  const yyyy = d.getFullYear();
  const MM = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  return `${yyyy}-${MM}-${dd} ${hh}:${mm}:${ss}`;
}

// ── Event Colours ──

/**
 * Return the CSS colour string for a given event sub_type.
 * crowd→red, fight→red, fall→orange, default→blue.
 */
export function getEventColor(subType: string): string {
  switch (subType) {
    case 'crowd':
    case 'fight':
      return 'red';
    case 'fall':
      return 'orange';
    default:
      return 'blue';
  }
}

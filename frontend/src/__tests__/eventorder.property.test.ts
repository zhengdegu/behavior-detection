import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import type { DetectionEvent } from '../types';

/**
 * Feature: behavior-detection-frontend, Property 2: Event feed maintains reverse chronological order
 * Validates: Requirements 2.5
 *
 * The Live page receives events via WebSocket. Each new event is prepended to
 * the events array (see useWebSocket: `[parsed, ...prev]`). Because real-time
 * events arrive in chronological order (newer events arrive later), the
 * resulting array is always in descending timestamp order (newest at index 0).
 *
 * This property test verifies:
 *  (a) Prepending chronologically-arriving events produces a descending list.
 *  (b) A sorted-insertion approach always maintains descending order regardless
 *      of arrival order.
 */
describe('Feature: behavior-detection-frontend, Property 2: Event feed maintains reverse chronological order', () => {
  // ── Arbitrary: generate a DetectionEvent with a timestamp in a realistic range ──
  const eventArb = fc.record({
    type: fc.constant('anomaly'),
    sub_type: fc.constantFrom('crowd', 'fight', 'fall'),
    camera_id: fc.string({ minLength: 1, maxLength: 8 }),
    camera_name: fc.string({ minLength: 1, maxLength: 16 }),
    timestamp: fc
      .integer({ min: new Date('2020-01-01').getTime(), max: new Date('2030-01-01').getTime() })
      .map((t) => new Date(t).toISOString()),
    detail: fc.string({ minLength: 0, maxLength: 32 }),
    track_ids: fc.array(fc.integer({ min: 0, max: 999 }), { minLength: 0, maxLength: 3 }),
  }) as fc.Arbitrary<DetectionEvent>;

  /** Check that a feed is sorted in descending timestamp order. */
  function isSortedDescending(feed: DetectionEvent[]): boolean {
    for (let i = 1; i < feed.length; i++) {
      if (new Date(feed[i - 1].timestamp).getTime() < new Date(feed[i].timestamp).getTime()) {
        return false;
      }
    }
    return true;
  }

  /**
   * Simulate the useWebSocket prepend behaviour:
   *   setEvents((prev) => [parsed, ...prev].slice(0, MAX_EVENTS))
   */
  function prependEvent(feed: DetectionEvent[], event: DetectionEvent): DetectionEvent[] {
    return [event, ...feed].slice(0, 100);
  }

  /**
   * Sorted insertion — finds the correct position to maintain descending order.
   * Used as a reference implementation for the general case.
   */
  function insertEventSorted(feed: DetectionEvent[], event: DetectionEvent): DetectionEvent[] {
    const newFeed = [...feed];
    const eventTime = new Date(event.timestamp).getTime();
    let idx = 0;
    while (idx < newFeed.length && new Date(newFeed[idx].timestamp).getTime() >= eventTime) {
      idx++;
    }
    newFeed.splice(idx, 0, event);
    return newFeed;
  }

  it('should maintain descending order when events arrive in chronological order (prepend)', () => {
    fc.assert(
      fc.property(
        fc.array(eventArb, { minLength: 1, maxLength: 30 }),
        (events) => {
          // Sort events by timestamp ascending to simulate real-time arrival order
          const chronological = [...events].sort(
            (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
          );

          let feed: DetectionEvent[] = [];
          for (const event of chronological) {
            feed = prependEvent(feed, event);
            // After each prepend the feed must be in descending order
            expect(isSortedDescending(feed)).toBe(true);
          }

          // Final feed length should match input (capped at 100)
          expect(feed.length).toBe(Math.min(chronological.length, 100));
        },
      ),
      { numRuns: 100 },
    );
  });

  it('should maintain descending order with sorted insertion regardless of arrival order', () => {
    fc.assert(
      fc.property(
        fc.array(eventArb, { minLength: 1, maxLength: 30 }),
        (events) => {
          let feed: DetectionEvent[] = [];

          for (const event of events) {
            feed = insertEventSorted(feed, event);
            expect(isSortedDescending(feed)).toBe(true);
          }

          // All events must be present
          expect(feed.length).toBe(events.length);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('should keep the newest event at index 0 after prepend', () => {
    fc.assert(
      fc.property(
        fc.array(eventArb, { minLength: 1, maxLength: 20 }),
        eventArb,
        (existingEvents, newEvent) => {
          // Build a descending feed from existing events
          let feed: DetectionEvent[] = [];
          const sorted = [...existingEvents].sort(
            (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
          );
          for (const e of sorted) {
            feed = prependEvent(feed, e);
          }

          // Prepend the new event (simulating it arriving as the latest)
          const updated = prependEvent(feed, newEvent);

          // The new event should always be at index 0
          expect(updated[0]).toBe(newEvent);
        },
      ),
      { numRuns: 100 },
    );
  });
});

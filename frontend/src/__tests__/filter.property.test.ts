import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { filterEvents } from '../utils';
import type { DetectionEvent } from '../types';

/**
 * Feature: behavior-detection-frontend, Property 4: Event type filter correctness
 * Validates: Requirements 3.3
 */
describe('Feature: behavior-detection-frontend, Property 4: Event type filter correctness', () => {
  const subTypes = ['crowd', 'fight', 'fall'] as const;

  const eventArb = fc.record({
    type: fc.constant('anomaly'),
    sub_type: fc.constantFrom(...subTypes),
    camera_id: fc.string({ minLength: 1, maxLength: 8 }),
    camera_name: fc.string({ minLength: 1, maxLength: 16 }),
    timestamp: fc.date().map((d) => d.toISOString()),
    detail: fc.string({ minLength: 0, maxLength: 32 }),
    track_ids: fc.array(fc.integer({ min: 0, max: 999 }), { minLength: 0, maxLength: 3 }),
  }) as fc.Arbitrary<DetectionEvent>;

  it('should return only events matching the filter type, and include all matching events', () => {
    fc.assert(
      fc.property(
        fc.array(eventArb, { minLength: 0, maxLength: 30 }),
        fc.constantFrom(...subTypes),
        (events, filterType) => {
          const result = filterEvents(events, filterType);

          // All results have matching sub_type
          for (const e of result) {
            expect(e.sub_type).toBe(filterType);
          }

          // All matching events from original are in results (completeness)
          const expectedCount = events.filter((e) => e.sub_type === filterType).length;
          expect(result.length).toBe(expectedCount);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('should return all events when filter type is "all" or empty', () => {
    fc.assert(
      fc.property(
        fc.array(eventArb, { minLength: 0, maxLength: 30 }),
        fc.constantFrom('all', ''),
        (events, filterType) => {
          const result = filterEvents(events, filterType);
          expect(result.length).toBe(events.length);
          expect(result).toEqual(events);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('should preserve original event order after filtering', () => {
    fc.assert(
      fc.property(
        fc.array(eventArb, { minLength: 0, maxLength: 30 }),
        fc.constantFrom(...subTypes),
        (events, filterType) => {
          const result = filterEvents(events, filterType);

          // Filtered results should appear in the same relative order as in the original list
          let lastIdx = -1;
          for (const e of result) {
            const idx = events.indexOf(e, lastIdx + 1);
            expect(idx).toBeGreaterThan(lastIdx);
            lastIdx = idx;
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});

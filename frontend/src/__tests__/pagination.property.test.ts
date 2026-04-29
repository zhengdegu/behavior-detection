import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { paginateEvents } from '../utils';
import type { DetectionEvent } from '../types';

/**
 * Feature: behavior-detection-frontend, Property 5: Pagination slice correctness
 * Validates: Requirements 3.4
 */
describe('Feature: behavior-detection-frontend, Property 5: Pagination slice correctness', () => {
  const eventArb = fc.record({
    type: fc.constant('anomaly'),
    sub_type: fc.constantFrom('crowd', 'fight', 'fall'),
    camera_id: fc.string({ minLength: 1, maxLength: 8 }),
    camera_name: fc.string({ minLength: 1, maxLength: 16 }),
    timestamp: fc.date().map((d) => d.toISOString()),
    detail: fc.string({ minLength: 0, maxLength: 32 }),
    track_ids: fc.array(fc.integer({ min: 0, max: 999 }), { minLength: 0, maxLength: 3 }),
  }) as fc.Arbitrary<DetectionEvent>;

  it('should return correct page slices and all pages concatenated equal original', () => {
    const pageSize = 20;

    fc.assert(
      fc.property(
        fc.array(eventArb, { minLength: 0, maxLength: 100 }),
        (events) => {
          const totalPages = Math.max(1, Math.ceil(events.length / pageSize));

          // Collect all pages
          const allPaged: DetectionEvent[] = [];
          for (let page = 1; page <= totalPages; page++) {
            const slice = paginateEvents(events, page, pageSize);

            // Each page has at most pageSize items
            expect(slice.length).toBeLessThanOrEqual(pageSize);

            // Last page may have fewer items
            if (page < totalPages) {
              expect(slice.length).toBe(pageSize);
            } else {
              const remaining = events.length - (totalPages - 1) * pageSize;
              expect(slice.length).toBe(Math.max(0, remaining));
            }

            allPaged.push(...slice);
          }

          // All pages concatenated equal original
          expect(allPaged).toEqual(events);
        },
      ),
      { numRuns: 100 },
    );
  });
});

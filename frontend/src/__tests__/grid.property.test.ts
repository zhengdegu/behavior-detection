import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { getGridColumns } from '../utils';

/**
 * Feature: behavior-detection-frontend, Property 1: Camera grid layout calculation
 * Validates: Requirements 2.2
 */
describe('Feature: behavior-detection-frontend, Property 1: Camera grid layout calculation', () => {
  it('should return correct column count for any camera count 1~9', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 9 }),
        (n) => {
          const cols = getGridColumns(n);
          if (n === 1) {
            expect(cols).toBe(1);
          } else if (n === 2) {
            expect(cols).toBe(2);
          } else if (n >= 3 && n <= 4) {
            expect(cols).toBe(2);
          } else if (n >= 5 && n <= 9) {
            expect(cols).toBe(3);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});

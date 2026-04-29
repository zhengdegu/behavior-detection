import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { getReconnectDelay } from '../hooks/useWebSocket';

/**
 * Feature: behavior-detection-frontend, Property 3: WebSocket exponential backoff delay
 * Validates: Requirements 2.10, 9.3
 */
describe('Feature: behavior-detection-frontend, Property 3: WebSocket exponential backoff delay', () => {
  it('should return min(2^attempt * 1000, 30000) for any attempt number 0~20', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 20 }),
        (attempt) => {
          const expected = Math.min(Math.pow(2, attempt) * 1000, 30000);
          const actual = getReconnectDelay(attempt);
          expect(actual).toBe(expected);
        },
      ),
      { numRuns: 100 },
    );
  });
});

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as fc from 'fast-check';
import { ApiError } from '../api';

/**
 * Feature: behavior-detection-frontend, Property 8: API non-2xx status code error handling
 * Validates: Requirements 10.3
 */
describe('Feature: behavior-detection-frontend, Property 8: API non-2xx status code error handling', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('should throw ApiError with matching status code for any non-2xx response', async () => {
    // We need to dynamically import the module's internal request function.
    // Since `request` is not exported, we test through a public API method.
    // We'll use getCameras which calls GET /api/cameras.
    const { getCameras } = await import('../api');

    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 400, max: 599 }),
        async (statusCode) => {
          const mockResponse = {
            ok: false,
            status: statusCode,
            statusText: `Error ${statusCode}`,
            json: () => Promise.reject(new Error('no json')),
          } as unknown as Response;

          vi.mocked(globalThis.fetch).mockResolvedValue(mockResponse);

          try {
            await getCameras();
            // Should not reach here
            expect.unreachable('Expected ApiError to be thrown');
          } catch (err) {
            expect(err).toBeInstanceOf(ApiError);
            expect((err as ApiError).status).toBe(statusCode);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});

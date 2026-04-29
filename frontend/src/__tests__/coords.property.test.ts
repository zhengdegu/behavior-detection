import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { normalizeCoord, denormalizeCoord } from '../utils';

/**
 * Feature: behavior-detection-frontend, Property 6: ROI coordinate normalization roundtrip
 * Validates: Requirements 5.7, 5.9
 */
describe('Feature: behavior-detection-frontend, Property 6: ROI coordinate normalization roundtrip', () => {
  it('should roundtrip normalizeCoord then denormalizeCoord with same canvas size back to original coords', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 1920 }),   // px
        fc.integer({ min: 0, max: 1080 }),   // py
        fc.integer({ min: 1, max: 3840 }),   // canvas width
        fc.integer({ min: 1, max: 2160 }),   // canvas height
        (px, py, w, h) => {
          const [nx, ny] = normalizeCoord(px, py, w, h);
          const [rx, ry] = denormalizeCoord(nx, ny, w, h);

          // Roundtrip should return original coords within floating point tolerance
          expect(rx).toBeCloseTo(px, 5);
          expect(ry).toBeCloseTo(py, 5);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('should produce normalized values in [0, 1] when pixel coords are within canvas bounds', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 3840 }),   // canvas width
        fc.integer({ min: 1, max: 2160 }),   // canvas height
        fc.float({ min: 0, max: 1, noNaN: true }),  // fraction for x
        fc.float({ min: 0, max: 1, noNaN: true }),  // fraction for y
        (w, h, fracX, fracY) => {
          const px = Math.floor(fracX * w);
          const py = Math.floor(fracY * h);
          const [nx, ny] = normalizeCoord(px, py, w, h);

          expect(nx).toBeGreaterThanOrEqual(0);
          expect(nx).toBeLessThanOrEqual(1);
          expect(ny).toBeGreaterThanOrEqual(0);
          expect(ny).toBeLessThanOrEqual(1);
        },
      ),
      { numRuns: 100 },
    );
  });
});

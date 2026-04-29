import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { serializeRulesConfig } from '../utils';
import type { RulesConfig, CrowdConfig, FightConfig, FallConfig } from '../types';

/**
 * Feature: behavior-detection-frontend, Property 7: Rules config serialization structure
 * Validates: Requirements 6.5
 */
describe('Feature: behavior-detection-frontend, Property 7: Rules config serialization structure', () => {
  const crowdArb: fc.Arbitrary<CrowdConfig> = fc.record({
    enabled: fc.boolean(),
    max_count: fc.integer({ min: 1, max: 100 }),
    radius: fc.integer({ min: 10, max: 500 }),
    confirm_frames: fc.integer({ min: 1, max: 60 }),
    cooldown: fc.integer({ min: 1, max: 300 }),
  });

  const fightArb: fc.Arbitrary<FightConfig> = fc.record({
    enabled: fc.boolean(),
    proximity_radius: fc.integer({ min: 10, max: 500 }),
    min_speed: fc.integer({ min: 1, max: 100 }),
    min_persons: fc.integer({ min: 2, max: 10 }),
    confirm_frames: fc.integer({ min: 1, max: 60 }),
    cooldown: fc.integer({ min: 1, max: 300 }),
  });

  const fallArb: fc.Arbitrary<FallConfig> = fc.record({
    enabled: fc.boolean(),
    ratio_threshold: fc.float({ min: Math.fround(0.1), max: Math.fround(5.0), noNaN: true }),
    min_ratio_change: fc.float({ min: Math.fround(0.01), max: Math.fround(2.0), noNaN: true }),
    min_y_drop: fc.float({ min: Math.fround(1), max: Math.fround(200), noNaN: true }),
    confirm_frames: fc.integer({ min: 1, max: 60 }),
    cooldown: fc.integer({ min: 1, max: 300 }),
  });

  const rulesConfigArb: fc.Arbitrary<RulesConfig> = fc.record({
    crowd: crowdArb,
    fight: fightArb,
    fall: fallArb,
  });

  it('should serialize to JSON containing all required keys and deserialize back to original', () => {
    fc.assert(
      fc.property(rulesConfigArb, (config) => {
        const json = serializeRulesConfig(config);
        const parsed = JSON.parse(json);

        // Top-level keys
        expect(parsed).toHaveProperty('crowd');
        expect(parsed).toHaveProperty('fight');
        expect(parsed).toHaveProperty('fall');

        // Crowd sub-keys
        expect(parsed.crowd).toHaveProperty('enabled');
        expect(parsed.crowd).toHaveProperty('max_count');
        expect(parsed.crowd).toHaveProperty('radius');
        expect(parsed.crowd).toHaveProperty('confirm_frames');
        expect(parsed.crowd).toHaveProperty('cooldown');

        // Fight sub-keys
        expect(parsed.fight).toHaveProperty('enabled');
        expect(parsed.fight).toHaveProperty('proximity_radius');
        expect(parsed.fight).toHaveProperty('min_speed');
        expect(parsed.fight).toHaveProperty('min_persons');
        expect(parsed.fight).toHaveProperty('confirm_frames');
        expect(parsed.fight).toHaveProperty('cooldown');

        // Fall sub-keys
        expect(parsed.fall).toHaveProperty('enabled');
        expect(parsed.fall).toHaveProperty('ratio_threshold');
        expect(parsed.fall).toHaveProperty('min_ratio_change');
        expect(parsed.fall).toHaveProperty('min_y_drop');
        expect(parsed.fall).toHaveProperty('confirm_frames');
        expect(parsed.fall).toHaveProperty('cooldown');

        // Deserialized object deep-equals original
        expect(parsed).toEqual(config);
      }),
      { numRuns: 100 },
    );
  });
});

import { describe, expect, it } from 'vitest';
import { interpretarKappa, kappaCohen } from './acuerdo';

describe('kappaCohen', () => {
  it('corrige el acuerdo por azar', () => {
    expect(kappaCohen(['a', 'a', 'b', 'b'], ['a', 'a', 'b', 'b'])).toBe(1);
    expect(kappaCohen(['a', 'a', 'b', 'b'], ['a', 'b', 'a', 'b'])).toBe(0);
    expect(kappaCohen(['a', 'a'], ['a', 'a'])).toBeNull();
    expect(interpretarKappa(0.7)).toBe('sustancial');
  });
});

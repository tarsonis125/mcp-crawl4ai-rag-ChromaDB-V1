import { describe, it, expect, vi } from 'vitest';
import { retry } from '../../src/services/api';

describe('retry', () => {
  it('retries on failure and eventually succeeds', async () => {
    let attempts = 0;
    const fn = vi.fn(async () => {
      attempts++;
      if (attempts < 3) throw new Error('fail');
      return 'success';
    });
    const result = await retry(fn, 3, 10);
    expect(result).toBe('success');
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it('throws after max retries', async () => {
    const fn = vi.fn(async () => { throw new Error('fail'); });
    await expect(retry(fn, 2, 10)).rejects.toThrow('fail');
    expect(fn).toHaveBeenCalledTimes(2);
  });
});

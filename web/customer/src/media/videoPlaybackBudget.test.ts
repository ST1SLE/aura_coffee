import { describe, expect, it, vi, afterEach } from 'vitest';
import {
  hasVideoPlaybackSlot,
  hasVisibleVideoCandidate,
  requestVideoPlaybackSlot,
  resetVideoPlaybackBudgetForTests,
  setVideoPlaybackBudgetMaxSlotsForTests,
  subscribeVideoPlaybackBudget,
  updateVisibleVideoCandidate,
} from './videoPlaybackBudget';

afterEach(() => {
  resetVideoPlaybackBudgetForTests();
});

describe('videoPlaybackBudget', () => {
  it('grants only the configured number of slots', () => {
    setVideoPlaybackBudgetMaxSlotsForTests(1);

    const releaseA = requestVideoPlaybackSlot('a', 'visible');
    const releaseB = requestVideoPlaybackSlot('b', 'visible');

    expect(hasVideoPlaybackSlot('a')).toBe(false);
    expect(hasVideoPlaybackSlot('b')).toBe(true);

    releaseB();
    expect(hasVideoPlaybackSlot('a')).toBe(true);

    releaseA();
  });

  it('lets user intent displace lower-priority warmup', () => {
    setVideoPlaybackBudgetMaxSlotsForTests(1);

    const releaseWarmup = requestVideoPlaybackSlot('warmup', 'warmup');
    expect(hasVideoPlaybackSlot('warmup')).toBe(true);

    const releaseUser = requestVideoPlaybackSlot('user', 'user');
    expect(hasVideoPlaybackSlot('warmup')).toBe(false);
    expect(hasVideoPlaybackSlot('user')).toBe(true);

    releaseUser();
    releaseWarmup();
  });

  it('notifies subscribers when grants change', () => {
    setVideoPlaybackBudgetMaxSlotsForTests(1);
    const listener = vi.fn();
    const unsubscribe = subscribeVideoPlaybackBudget(listener);

    const release = requestVideoPlaybackSlot('a', 'visible');
    release();

    expect(listener).toHaveBeenCalledTimes(2);
    unsubscribe();
  });

  it('selects only the visible candidate closest to the viewport center', () => {
    updateVisibleVideoCandidate('top', true, 240);
    updateVisibleVideoCandidate('center', true, 20);
    updateVisibleVideoCandidate('bottom', true, 120);

    expect(hasVisibleVideoCandidate('top')).toBe(false);
    expect(hasVisibleVideoCandidate('center')).toBe(true);
    expect(hasVisibleVideoCandidate('bottom')).toBe(false);

    updateVisibleVideoCandidate('center', false);
    expect(hasVisibleVideoCandidate('bottom')).toBe(true);
  });
});

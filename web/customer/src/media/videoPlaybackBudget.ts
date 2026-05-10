// START_MODULE_CONTRACT
//   PURPOSE: Shared client-side budget for customer menu video playback so
//            scrolling cannot enqueue dozens of simultaneous MP4 downloads.
//   SCOPE:   In-memory browser singleton only. Coordinates MenuMedia playback
//            and low-priority login warmup; does not persist data or call APIs.
//   DEPENDS: browser matchMedia where available.
//   LINKS:   docs/development-plan.xml M-WEB-CUSTOMER, PDD §5.2 menu media.
//   ROLE:    RUNTIME
//   MAP_MODE: EXPORTS
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   VideoPlaybackPriority                  - slot request priority enum
//   requestVideoPlaybackSlot               - request one budget slot
//   hasVideoPlaybackSlot                   - inspect whether request is granted
//   subscribeVideoPlaybackBudget           - listen for grant/release changes
//   updateVisibleVideoCandidate            - report viewport playback candidate
//   hasVisibleVideoCandidate               - inspect selected viewport candidate
//   setVideoPlaybackBudgetMaxSlotsForTests - test-only slot-count override
//   resetVideoPlaybackBudgetForTests       - test-only singleton reset
// END_MODULE_MAP

export type VideoPlaybackPriority = 'warmup' | 'visible' | 'user';

interface SlotRequest {
  id: string;
  priority: VideoPlaybackPriority;
  sequence: number;
}

interface VisibleVideoCandidate {
  id: string;
  distanceFromViewportCenter: number;
  sequence: number;
}

const PRIORITY_SCORE: Record<VideoPlaybackPriority, number> = {
  warmup: 1,
  visible: 2,
  user: 3,
};

const requests = new Map<string, SlotRequest>();
const visibleCandidates = new Map<string, VisibleVideoCandidate>();
const listeners = new Set<() => void>();
let sequence = 0;
let maxSlotsOverride: number | null = null;

function notifyListeners(): void {
  for (const listener of listeners) {
    listener();
  }
}

function defaultMaxSlots(): number {
  if (
    typeof window === 'undefined' ||
    typeof window.matchMedia !== 'function'
  ) {
    return 1;
  }

  const hasFinePointer =
    window.matchMedia('(hover: hover) and (pointer: fine)').matches ||
    window.matchMedia('(any-hover: hover) and (any-pointer: fine)').matches;
  return hasFinePointer ? 2 : 1;
}

function maxSlots(): number {
  return Math.max(1, maxSlotsOverride ?? defaultMaxSlots());
}

function grantedSlotIds(): Set<string> {
  return new Set(
    Array.from(requests.values())
      .sort((a, b) => {
        const priorityDelta =
          PRIORITY_SCORE[b.priority] - PRIORITY_SCORE[a.priority];
        if (priorityDelta !== 0) return priorityDelta;
        return b.sequence - a.sequence;
      })
      .slice(0, maxSlots())
      .map((request) => request.id),
  );
}

function selectedVisibleCandidateId(): string | null {
  return (
    Array.from(visibleCandidates.values()).sort((a, b) => {
      const distanceDelta =
        a.distanceFromViewportCenter - b.distanceFromViewportCenter;
      if (distanceDelta !== 0) return distanceDelta;
      return b.sequence - a.sequence;
    })[0]?.id ?? null
  );
}

// START_CONTRACT: requestVideoPlaybackSlot
//   PURPOSE: Request an active video download/playback slot for a mounted media
//            component or low-priority warmup task.
//   INPUTS:  id: string — stable caller id for the request lifetime
//            priority: VideoPlaybackPriority — warmup < visible < user
//   OUTPUTS: () => void — idempotent release callback.
//   SIDE_EFFECTS: Mutates in-memory request queue and notifies subscribers.
//   LINKS:   PDD §5.2 menu media.
// END_CONTRACT: requestVideoPlaybackSlot
export function requestVideoPlaybackSlot(
  id: string,
  priority: VideoPlaybackPriority,
): () => void {
  let released = false;
  requests.set(id, { id, priority, sequence: ++sequence });
  notifyListeners();

  return () => {
    if (released) return;
    released = true;
    requests.delete(id);
    notifyListeners();
  };
}

// START_CONTRACT: hasVideoPlaybackSlot
//   PURPOSE: Check whether the caller currently owns one of the active slots.
//   INPUTS:  id: string — caller id passed to requestVideoPlaybackSlot.
//   OUTPUTS: boolean — true when the request is inside the granted budget.
//   SIDE_EFFECTS: none.
//   LINKS:   PDD §5.2 menu media.
// END_CONTRACT: hasVideoPlaybackSlot
export function hasVideoPlaybackSlot(id: string): boolean {
  return grantedSlotIds().has(id);
}

// START_CONTRACT: subscribeVideoPlaybackBudget
//   PURPOSE: Subscribe UI hooks/warmup code to budget grant changes.
//   INPUTS:  listener: () => void — callback fired after queue mutation.
//   OUTPUTS: () => void — unsubscribe callback.
//   SIDE_EFFECTS: Adds/removes listener from in-memory singleton.
//   LINKS:   PDD §5.2 menu media.
// END_CONTRACT: subscribeVideoPlaybackBudget
export function subscribeVideoPlaybackBudget(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

// START_CONTRACT: updateVisibleVideoCandidate
//   PURPOSE: Report whether a menu video is currently a viewport autoplay
//            candidate and how close it is to the viewport center.
//   INPUTS:  id: string — stable caller id
//            visible: boolean — false removes the candidate
//            distanceFromViewportCenter?: number — lower wins when visible
//   OUTPUTS: void.
//   SIDE_EFFECTS: Mutates in-memory viewport candidate set and notifies
//                 subscribers.
//   LINKS:   PDD §5.2 menu media.
// END_CONTRACT: updateVisibleVideoCandidate
export function updateVisibleVideoCandidate(
  id: string,
  visible: boolean,
  distanceFromViewportCenter = Number.POSITIVE_INFINITY,
): void {
  if (!visible) {
    visibleCandidates.delete(id);
  } else {
    visibleCandidates.set(id, {
      id,
      distanceFromViewportCenter,
      sequence: ++sequence,
    });
  }
  notifyListeners();
}

// START_CONTRACT: hasVisibleVideoCandidate
//   PURPOSE: Check whether this video is the single selected viewport autoplay
//            candidate.
//   INPUTS:  id: string — stable caller id.
//   OUTPUTS: boolean — true when selected as center-most visible candidate.
//   SIDE_EFFECTS: none.
//   LINKS:   PDD §5.2 menu media.
// END_CONTRACT: hasVisibleVideoCandidate
export function hasVisibleVideoCandidate(id: string): boolean {
  return selectedVisibleCandidateId() === id;
}

// START_CONTRACT: setVideoPlaybackBudgetMaxSlotsForTests
//   PURPOSE: Override slot count in Vitest without depending on browser media
//            query implementation details.
//   INPUTS:  slots: number | null — max slots, or null to restore browser rule.
//   OUTPUTS: void.
//   SIDE_EFFECTS: Mutates test-only override and notifies subscribers.
//   LINKS:   web/customer Vitest media tests.
// END_CONTRACT: setVideoPlaybackBudgetMaxSlotsForTests
export function setVideoPlaybackBudgetMaxSlotsForTests(
  slots: number | null,
): void {
  maxSlotsOverride = slots;
  notifyListeners();
}

// START_CONTRACT: resetVideoPlaybackBudgetForTests
//   PURPOSE: Reset singleton state between tests.
//   INPUTS:  none.
//   OUTPUTS: void.
//   SIDE_EFFECTS: Clears request queue, listeners, sequence, and max-slot
//                 override.
//   LINKS:   web/customer Vitest media tests.
// END_CONTRACT: resetVideoPlaybackBudgetForTests
export function resetVideoPlaybackBudgetForTests(): void {
  requests.clear();
  visibleCandidates.clear();
  listeners.clear();
  sequence = 0;
  maxSlotsOverride = null;
}

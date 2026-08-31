/**
 * The alert sound for new notifications.
 *
 * The tone is synthesised rather than loaded from a file: an audio asset would
 * be one more request to get past the content-security policy, one more thing
 * to ship, and one more thing to break offline. Two short sine notes are
 * enough to be noticed across a room without being unpleasant on the twentieth
 * repetition of a working day.
 *
 * Browsers refuse to start audio before the user has interacted with the page.
 * Signing in is such an interaction, so by the time a notification can arrive
 * the context is nearly always allowed to run; when it is not, the chime is
 * skipped silently rather than throwing.
 */

const STORAGE_KEY = "vipl.notification-sound";

let context: AudioContext | null = null;

type WindowWithLegacyAudio = Window &
  typeof globalThis & { webkitAudioContext?: typeof AudioContext };

function audioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor =
    window.AudioContext ?? (window as WindowWithLegacyAudio).webkitAudioContext;
  if (!Ctor) return null;
  if (context === null) {
    try {
      context = new Ctor();
    } catch {
      return null;
    }
  }
  return context;
}

/** Whether the chime is enabled. Defaults to on, and survives a reload. */
export function soundEnabled(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) !== "off";
  } catch {
    // Private windows and locked-down browsers throw on access; a missing
    // preference is not a reason to go silent.
    return true;
  }
}

export function setSoundEnabled(enabled: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, enabled ? "on" : "off");
  } catch {
    // Nothing to do: the preference simply will not survive this session.
  }
}

/** Two short notes. Does nothing if audio is unavailable or muted. */
export function playNotificationChime(): void {
  if (!soundEnabled()) return;
  const ctx = audioContext();
  if (!ctx) return;

  // Suspended is the normal state before the first gesture, and after the tab
  // has been in the background. Resuming may be refused; that is fine.
  if (ctx.state === "suspended") void ctx.resume().catch(() => undefined);

  const start = ctx.currentTime;
  // A rising fifth: recognisable as "something arrived" rather than "error".
  for (const [offset, frequency] of [
    [0, 660],
    [0.12, 990],
  ] as const) {
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.type = "sine";
    oscillator.frequency.value = frequency;

    // Shaped rather than switched: an instant start or stop on a sine wave
    // produces an audible click.
    const at = start + offset;
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(0.16, at + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.22);

    oscillator.connect(gain).connect(ctx.destination);
    oscillator.start(at);
    oscillator.stop(at + 0.24);
  }
}

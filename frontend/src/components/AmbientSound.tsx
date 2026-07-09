import { useEffect, useRef, useState } from "react";
import { ForestIcon, MuteIcon, RainIcon, VolumeIcon, WaveIcon } from "./icons";

type SoundKey = "off" | "rain" | "forest" | "waves";

const SOUNDS: { key: SoundKey; label: string; Icon: typeof RainIcon }[] = [
  { key: "off", label: "No sound", Icon: MuteIcon },
  { key: "rain", label: "Rain", Icon: RainIcon },
  { key: "forest", label: "Forest", Icon: ForestIcon },
  { key: "waves", label: "Waves", Icon: WaveIcon },
];

const VOLUME_STORAGE_KEY = "convex-ambient-volume";
const FADE_SECONDS = 0.25;

interface Voice {
  stop: () => void;
}

function makeNoiseBuffer(ctx: AudioContext): AudioBuffer {
  const seconds = 6;
  const buffer = ctx.createBuffer(1, ctx.sampleRate * seconds, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  return buffer;
}

function fadeOutAndStop(ctx: AudioContext, gain: GainNode, cleanup: () => void) {
  const now = ctx.currentTime;
  gain.gain.cancelScheduledValues(now);
  gain.gain.setValueAtTime(gain.gain.value, now);
  gain.gain.linearRampToValueAtTime(0, now + FADE_SECONDS);
  setTimeout(cleanup, FADE_SECONDS * 1000 + 60);
}

function playRain(ctx: AudioContext, dest: GainNode): Voice {
  const noise = ctx.createBufferSource();
  noise.buffer = makeNoiseBuffer(ctx);
  noise.loop = true;

  const bandpass = ctx.createBiquadFilter();
  bandpass.type = "bandpass";
  bandpass.frequency.value = 3200;
  bandpass.Q.value = 0.6;

  const highshelf = ctx.createBiquadFilter();
  highshelf.type = "highshelf";
  highshelf.frequency.value = 4200;
  highshelf.gain.value = 5;

  const gain = ctx.createGain();
  gain.gain.value = 0;

  const lfo = ctx.createOscillator();
  lfo.frequency.value = 0.06; // slow intensity swell, like passing gusts of rain
  const lfoGain = ctx.createGain();
  lfoGain.gain.value = 0.1;
  lfo.connect(lfoGain);
  lfoGain.connect(gain.gain);
  lfo.start();

  noise.connect(bandpass);
  bandpass.connect(highshelf);
  highshelf.connect(gain);
  gain.connect(dest);
  noise.start();
  gain.gain.linearRampToValueAtTime(0.8, ctx.currentTime + FADE_SECONDS);

  return {
    stop: () =>
      fadeOutAndStop(ctx, gain, () => {
        lfo.stop();
        noise.stop();
        [noise, bandpass, highshelf, gain, lfo, lfoGain].forEach((n) => n.disconnect());
      }),
  };
}

function playForest(ctx: AudioContext, dest: GainNode): Voice {
  const noise = ctx.createBufferSource();
  noise.buffer = makeNoiseBuffer(ctx);
  noise.loop = true;

  const lowpass = ctx.createBiquadFilter();
  lowpass.type = "lowpass";
  lowpass.frequency.value = 450;

  const bedGain = ctx.createGain();
  bedGain.gain.value = 0;

  noise.connect(lowpass);
  lowpass.connect(bedGain);
  bedGain.connect(dest);
  noise.start();
  bedGain.gain.linearRampToValueAtTime(0.3, ctx.currentTime + FADE_SECONDS);

  let stopped = false;
  let chirpTimeout: number;

  function scheduleChirp() {
    if (stopped) return;
    chirpTimeout = window.setTimeout(() => {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      osc.type = "sine";
      const chirpGain = ctx.createGain();
      chirpGain.gain.value = 0;
      osc.connect(chirpGain);
      chirpGain.connect(dest);

      const baseFreq = 1800 + Math.random() * 1400;
      osc.frequency.setValueAtTime(baseFreq, now);
      osc.frequency.exponentialRampToValueAtTime(baseFreq * 1.35, now + 0.08);
      osc.frequency.exponentialRampToValueAtTime(baseFreq * 0.82, now + 0.17);

      chirpGain.gain.setValueAtTime(0, now);
      chirpGain.gain.linearRampToValueAtTime(0.1, now + 0.02);
      chirpGain.gain.linearRampToValueAtTime(0, now + 0.22);

      osc.start(now);
      osc.stop(now + 0.24);
      osc.onended = () => {
        osc.disconnect();
        chirpGain.disconnect();
      };

      scheduleChirp();
    }, 1800 + Math.random() * 4200);
  }
  scheduleChirp();

  return {
    stop: () =>
      fadeOutAndStop(ctx, bedGain, () => {
        stopped = true;
        clearTimeout(chirpTimeout);
        noise.stop();
        [noise, lowpass, bedGain].forEach((n) => n.disconnect());
      }),
  };
}

function playWaves(ctx: AudioContext, dest: GainNode): Voice {
  const noise = ctx.createBufferSource();
  noise.buffer = makeNoiseBuffer(ctx);
  noise.loop = true;

  const lowpass = ctx.createBiquadFilter();
  lowpass.type = "lowpass";
  lowpass.frequency.value = 700;
  lowpass.Q.value = 0.4;

  const gain = ctx.createGain();
  gain.gain.value = 0;

  const lfo = ctx.createOscillator();
  lfo.frequency.value = 0.1; // one swell roughly every 10s, like waves breaking
  const lfoGain = ctx.createGain();
  lfoGain.gain.value = 450;
  lfo.connect(lfoGain);
  lfoGain.connect(lowpass.frequency);
  lfo.start();

  noise.connect(lowpass);
  lowpass.connect(gain);
  gain.connect(dest);
  noise.start();
  gain.gain.linearRampToValueAtTime(0.7, ctx.currentTime + FADE_SECONDS);

  return {
    stop: () =>
      fadeOutAndStop(ctx, gain, () => {
        lfo.stop();
        noise.stop();
        [noise, lowpass, gain, lfo, lfoGain].forEach((n) => n.disconnect());
      }),
  };
}

export function AmbientSound() {
  const [active, setActive] = useState<SoundKey>("off");
  const [volume, setVolume] = useState(() => {
    const stored = Number(localStorage.getItem(VOLUME_STORAGE_KEY));
    return Number.isFinite(stored) && stored > 0 ? stored : 0.5;
  });

  const ctxRef = useRef<AudioContext | null>(null);
  const masterGainRef = useRef<GainNode | null>(null);
  const voiceRef = useRef<Voice | null>(null);

  function ensureContext(): { ctx: AudioContext; master: GainNode } {
    if (!ctxRef.current || !masterGainRef.current) {
      const ctx = new AudioContext();
      const master = ctx.createGain();
      master.gain.value = volume;
      master.connect(ctx.destination);
      ctxRef.current = ctx;
      masterGainRef.current = master;
    }
    return { ctx: ctxRef.current, master: masterGainRef.current };
  }

  function handleSelect(key: SoundKey) {
    voiceRef.current?.stop();
    voiceRef.current = null;
    setActive(key);
    if (key === "off") return;

    const { ctx, master } = ensureContext();
    if (ctx.state === "suspended") void ctx.resume();

    if (key === "rain") voiceRef.current = playRain(ctx, master);
    else if (key === "forest") voiceRef.current = playForest(ctx, master);
    else if (key === "waves") voiceRef.current = playWaves(ctx, master);
  }

  useEffect(() => {
    localStorage.setItem(VOLUME_STORAGE_KEY, String(volume));
    if (masterGainRef.current && ctxRef.current) {
      masterGainRef.current.gain.setTargetAtTime(volume, ctxRef.current.currentTime, 0.05);
    }
  }, [volume]);

  // Stop everything and release the audio context when leaving the session screen.
  useEffect(() => {
    return () => {
      voiceRef.current?.stop();
      void ctxRef.current?.close();
    };
  }, []);

  return (
    <div className="ambient-picker">
      {SOUNDS.map(({ key, label, Icon }) => (
        <button
          key={key}
          type="button"
          className={`ambient-btn ${active === key ? "is-active" : ""}`}
          aria-label={label}
          aria-pressed={active === key}
          title={label}
          onClick={() => handleSelect(key)}
        >
          <Icon size={15} />
        </button>
      ))}
      <div className={`ambient-volume-wrap ${active !== "off" ? "is-visible" : ""}`}>
        <VolumeIcon size={13} />
        <input
          className="ambient-volume"
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={volume}
          aria-label="Ambient sound volume"
          onChange={(e) => setVolume(Number(e.target.value))}
        />
      </div>
    </div>
  );
}

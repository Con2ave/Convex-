import { useEffect, useRef, useState } from "react";

const CYCLE_SECONDS = 3600; // one physical "flip" per hour of verified study time

interface SandTimerProps {
  elapsedSeconds: number;
  active: boolean;
}

export function SandTimer({ elapsedSeconds, active }: SandTimerProps) {
  const cycleIndex = Math.floor(elapsedSeconds / CYCLE_SECONDS);
  const fraction = (elapsedSeconds % CYCLE_SECONDS) / CYCLE_SECONDS;

  const [rotation, setRotation] = useState(0);
  const lastCycle = useRef(cycleIndex);

  useEffect(() => {
    if (cycleIndex !== lastCycle.current) {
      const delta = cycleIndex - lastCycle.current;
      lastCycle.current = cycleIndex;
      setRotation((r) => r + delta * 180);
    }
  }, [cycleIndex]);

  const bulbHeight = 40;
  const bottomFillHeight = fraction * bulbHeight;
  const topFillHeight = (1 - fraction) * bulbHeight;

  return (
    <div className="sand-timer">
      <div className="sand-timer-glass" style={{ transform: `rotate(${rotation}deg)` }}>
        <svg viewBox="0 0 64 96" width="56" height="84">
          <defs>
            <linearGradient id="sandGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#d8fa3e" />
              <stop offset="100%" stopColor="#f0b429" />
            </linearGradient>
            <clipPath id="clipTopBulb">
              <polygon points="10,6 54,6 38,46 26,46" />
            </clipPath>
            <clipPath id="clipBottomBulb">
              <polygon points="26,50 38,50 54,90 10,90" />
            </clipPath>
          </defs>

          {/* remaining sand, top bulb */}
          <rect x="6" y="6" width="52" height={topFillHeight} fill="url(#sandGradient)" clipPath="url(#clipTopBulb)" opacity={0.9} />
          {/* accumulated sand, bottom bulb */}
          <rect
            x="6"
            y={90 - bottomFillHeight}
            width="52"
            height={bottomFillHeight}
            fill="url(#sandGradient)"
            clipPath="url(#clipBottomBulb)"
          />

          {/* falling grains through the neck */}
          {active && (
            <g className="sand-trickle">
              <circle cx="32" cy="47" r="0.9" />
              <circle cx="32" cy="47" r="0.9" className="grain-2" />
            </g>
          )}

          {/* glass frame */}
          <path
            d="M6 6 H58 M10 6 26,46 H38 L54,6 M26,50 10,90 H54 L38,50 M6 90 H58"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={0.55}
          />
        </svg>
      </div>
      <p className="sand-timer-caption">Hour {cycleIndex + 1}</p>
    </div>
  );
}

// A calm, generative forest scene for the study timer screen - three depth layers of
// silhouette pines behind a dusk gradient, so entering timer mode reads as leaving the app's
// normal UI for a quieter place. Shapes are plain polygons computed at module load rather than
// hand-authored path data, and the whole scene is a fixed background layer behind the content.

interface Tree {
  x: number;
  height: number;
  width: number;
}

// Hand-composed (not random) so the skyline reads as deliberately arranged, not scattered.
function buildLayer(spread: number[], baseHeight: number, jitter: number[]): Tree[] {
  return spread.map((x, i) => {
    const h = baseHeight + jitter[i % jitter.length];
    return { x, height: h, width: h * 0.62 };
  });
}

const BACK_TREES = buildLayer(
  [-10, 40, 95, 150, 205, 260, 315, 370, 420],
  90,
  [10, -8, 14, -4, 18, -12, 8, -6, 12]
);
const MID_TREES = buildLayer(
  [-15, 55, 120, 180, 240, 300, 360, 415],
  130,
  [14, -10, 18, -6, 22, -14, 10, -8]
);
const FRONT_TREES = buildLayer(
  [-25, 45, 110, 175, 240, 305, 370, 430],
  260,
  [30, -22, 34, -18, 28, -24, 20, -14]
);

function pineFoliage(cx: number, baseY: number, height: number, width: number): string {
  // A simple three-tier stacked-triangle silhouette - reads as a pine without hand-drawn detail.
  const tiers = 3;
  const pts: string[] = [];
  for (let t = 0; t < tiers; t++) {
    const tierTop = baseY - height * ((t + 1) / tiers);
    const tierBase = baseY - height * (t / tiers) + (t === 0 ? 0 : height * 0.06);
    const tierWidth = width * (1 - t * 0.24);
    pts.push(
      `M${cx - tierWidth / 2},${tierBase} L${cx},${tierTop} L${cx + tierWidth / 2},${tierBase} Z`
    );
  }
  return pts.join(" ");
}

function TreeLayer({ trees, baseY, fill, opacity }: { trees: Tree[]; baseY: number; fill: string; opacity: number }) {
  return (
    <g fill={fill} opacity={opacity}>
      {trees.map((t, i) => (
        <path key={i} d={pineFoliage(t.x, baseY, t.height, t.width)} />
      ))}
      <rect x={-30} y={baseY - 2} width={460} height={40} fill={fill} />
    </g>
  );
}

const FIREFLIES = [
  { left: "14%", top: "58%", delay: "0s", duration: "9s" },
  { left: "78%", top: "48%", delay: "1.4s", duration: "11s" },
  { left: "34%", top: "70%", delay: "2.6s", duration: "8s" },
  { left: "62%", top: "64%", delay: "0.7s", duration: "10s" },
  { left: "22%", top: "40%", delay: "3.3s", duration: "12s" },
  { left: "88%", top: "62%", delay: "1.9s", duration: "9.5s" },
];

export function ForestBackdrop() {
  return (
    <div className="forest-backdrop" aria-hidden="true">
      <svg viewBox="0 0 400 800" preserveAspectRatio="xMidYMax slice">
        <defs>
          <linearGradient id="forestSky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0a1220" />
            <stop offset="30%" stopColor="#16233c" />
            <stop offset="54%" stopColor="#3a3155" />
            <stop offset="68%" stopColor="#6a4a48" />
            <stop offset="80%" stopColor="#3a2a28" />
            <stop offset="100%" stopColor="#120e10" />
          </linearGradient>
          <radialGradient id="forestGlow" cx="50%" cy="8%" r="42%">
            <stop offset="0%" stopColor="#ffd98a" stopOpacity="0.4" />
            <stop offset="45%" stopColor="#ffd98a" stopOpacity="0.16" />
            <stop offset="80%" stopColor="#ffd98a" stopOpacity="0.05" />
            <stop offset="100%" stopColor="#ffd98a" stopOpacity="0" />
          </radialGradient>
        </defs>

        <rect x="0" y="0" width="400" height="800" fill="url(#forestSky)" />
        <ellipse cx="200" cy="280" rx="260" ry="240" fill="url(#forestGlow)" />

        <TreeLayer trees={BACK_TREES} baseY={430} fill="#2a3550" opacity={0.5} />
        <TreeLayer trees={MID_TREES} baseY={490} fill="#1a2135" opacity={0.72} />
        <TreeLayer trees={FRONT_TREES} baseY={640} fill="#0c0f18" opacity={1} />
      </svg>

      {FIREFLIES.map((f, i) => (
        <span
          key={i}
          className="firefly"
          style={{ left: f.left, top: f.top, animationDelay: f.delay, animationDuration: f.duration }}
        />
      ))}
    </div>
  );
}

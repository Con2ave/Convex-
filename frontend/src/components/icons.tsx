import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base(size: number, props: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    ...props,
  };
}

export function MenuIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <line x1="4" y1="7" x2="20" y2="7" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="17" x2="14" y2="17" />
    </svg>
  );
}

export function BellIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M6 9a6 6 0 1 1 12 0c0 3.4 1 5 2 6H4c1-1 2-2.6 2-6Z" />
      <path d="M10 19a2 2 0 0 0 4 0" />
    </svg>
  );
}

export function SearchIcon({ size = 18, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <circle cx="11" cy="11" r="7" />
      <line x1="21" y1="21" x2="16.2" y2="16.2" />
    </svg>
  );
}

export function SlidersIcon({ size = 18, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <line x1="5" y1="6" x2="19" y2="6" />
      <line x1="5" y1="12" x2="19" y2="12" />
      <line x1="5" y1="18" x2="19" y2="18" />
      <circle cx="9" cy="6" r="1.6" fill="currentColor" />
      <circle cx="15" cy="12" r="1.6" fill="currentColor" />
      <circle cx="9" cy="18" r="1.6" fill="currentColor" />
    </svg>
  );
}

export function ChevronRightIcon({ size = 18, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <polyline points="9 6 15 12 9 18" />
    </svg>
  );
}

export function ChevronLeftIcon({ size = 18, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <polyline points="15 6 9 12 15 18" />
    </svg>
  );
}

export function CheckIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <polyline points="4 12 9 17 20 6" />
    </svg>
  );
}

export function FlagIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <line x1="5" y1="4" x2="5" y2="20" />
      <path d="M5 5c3-1.5 5.5 1 8.5-0.5S19 5 19 5v9c-2.5 1.5-5.5-1-8.5 0.5S5 14 5 14" />
    </svg>
  );
}

export function ClockIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <circle cx="12" cy="12" r="8.5" />
      <polyline points="12 7.5 12 12 15.5 14" />
    </svg>
  );
}

export function HomeIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M4 11.5 12 4l8 7.5" />
      <path d="M6 10v9h12v-9" />
    </svg>
  );
}

export function HistoryIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M4 12a8 8 0 1 0 2.6-5.9" />
      <polyline points="4 5 4 10 9 10" />
      <polyline points="12 8 12 12.5 15.5 14.5" />
    </svg>
  );
}

export function ProfileIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <circle cx="12" cy="8.2" r="3.4" />
      <path d="M5 20c1.2-3.6 4-5.4 7-5.4s5.8 1.8 7 5.4" />
    </svg>
  );
}

export function PauseIconTile({ size = 22, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <line x1="9" y1="6" x2="9" y2="18" />
      <line x1="15" y1="6" x2="15" y2="18" />
    </svg>
  );
}

export function LockIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

export function LogoutIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M9 4H5v16h4" />
      <line x1="21" y1="12" x2="10" y2="12" />
      <polyline points="16 7 21 12 16 17" />
    </svg>
  );
}

export function CloseIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <line x1="6" y1="6" x2="18" y2="18" />
      <line x1="18" y1="6" x2="6" y2="18" />
    </svg>
  );
}

export function SettingsIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 3v2.6M12 18.4V21M21 12h-2.6M5.6 12H3M18.4 5.6l-1.85 1.85M7.45 16.55l-1.85 1.85M18.4 18.4l-1.85-1.85M7.45 7.45 5.6 5.6" />
    </svg>
  );
}

export function HelpIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.4 9.3a2.6 2.6 0 1 1 3.6 2.4c-.9.4-1.4 1.1-1.4 2.1v.3" />
      <circle cx="12" cy="17" r="0.65" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function SunIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <circle cx="12" cy="12" r="4.3" />
      <path d="M12 2.5v2.5M12 19v2.5M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M2.5 12H5M19 12h2.5M4.6 19.4l1.8-1.8M17.6 6.4l1.8-1.8" />
    </svg>
  );
}

export function MoonIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M20 14.3A8.5 8.5 0 1 1 9.7 4a7 7 0 0 0 10.3 10.3Z" />
    </svg>
  );
}

export function DeviceIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <rect x="3" y="4.5" width="18" height="12" rx="1.6" />
      <line x1="8" y1="20" x2="16" y2="20" />
      <line x1="12" y1="16.5" x2="12" y2="20" />
    </svg>
  );
}

export function MailIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <polyline points="3 6.5 12 13 21 6.5" />
    </svg>
  );
}

export function RainIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M7 13a4.5 4.5 0 0 1 .7-8.94A5.5 5.5 0 0 1 18 6.2 4 4 0 0 1 17 14H7Z" />
      <line x1="8" y1="17" x2="7" y2="19.5" />
      <line x1="12.5" y1="17" x2="11.5" y2="19.5" />
      <line x1="17" y1="17" x2="16" y2="19.5" />
    </svg>
  );
}

export function ForestIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M9 3 4.5 10h2.3L3 17h7.5V3Z" />
      <path d="M15.5 6 11.5 12.5h2L10 20h9l-3.7-7.5h2Z" />
      <line x1="10" y1="17" x2="10" y2="21" />
    </svg>
  );
}

export function WaveIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M3 9c1.5-1.4 3-1.4 4.5 0s3 1.4 4.5 0 3-1.4 4.5 0 3 1.4 4.5 0" />
      <path d="M3 14.5c1.5-1.4 3-1.4 4.5 0s3 1.4 4.5 0 3-1.4 4.5 0 3 1.4 4.5 0" />
      <path d="M3 20c1.5-1.4 3-1.4 4.5 0s3 1.4 4.5 0 3-1.4 4.5 0 3 1.4 4.5 0" />
    </svg>
  );
}

export function MuteIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M4 9v6h4l5 4V5L8 9H4Z" />
      <line x1="16" y1="9" x2="21" y2="15" />
      <line x1="21" y1="9" x2="16" y2="15" />
    </svg>
  );
}

export function VolumeIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M4 9v6h4l5 4V5L8 9H4Z" />
      <path d="M16.5 8.5a5 5 0 0 1 0 7" />
      <path d="M19 6a8.5 8.5 0 0 1 0 12" />
    </svg>
  );
}

export function UploadIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M12 15V4" />
      <polyline points="7.5 8.5 12 4 16.5 8.5" />
      <path d="M4.5 15v3.5A1.5 1.5 0 0 0 6 20h12a1.5 1.5 0 0 0 1.5-1.5V15" />
    </svg>
  );
}

export function DocumentIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M7 3.5h7L18.5 8v12A1.5 1.5 0 0 1 17 21.5H7A1.5 1.5 0 0 1 5.5 20V5A1.5 1.5 0 0 1 7 3.5Z" />
      <polyline points="14 3.5 14 8.5 18.5 8.5" />
      <line x1="8.5" y1="13" x2="15" y2="13" />
      <line x1="8.5" y1="16.5" x2="13" y2="16.5" />
    </svg>
  );
}

export function BookIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H12v16H5.5A1.5 1.5 0 0 1 4 18.5Z" />
      <path d="M20 5.5A1.5 1.5 0 0 0 18.5 4H12v16h6.5a1.5 1.5 0 0 0 1.5-1.5Z" />
    </svg>
  );
}

export function TrophyIcon({ size = 20, ...props }: IconProps) {
  return (
    <svg {...base(size, props)}>
      <path d="M7 4h10v5a5 5 0 0 1-10 0Z" />
      <path d="M7 5H4v2a3 3 0 0 0 3 3M17 5h3v2a3 3 0 0 1-3 3" />
      <line x1="12" y1="14" x2="12" y2="18" />
      <path d="M8.5 20.5h7" />
      <line x1="12" y1="18" x2="12" y2="20.5" />
    </svg>
  );
}

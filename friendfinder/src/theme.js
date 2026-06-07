// Central design tokens for BatchMate.
export const colors = {
  primary: '#4f46e5',
  primaryDark: '#4338ca',
  primarySoft: '#eef2ff',
  accent: '#06b6d4',
  purple: '#a855f7',
  bg: '#f6f7fb',
  card: '#ffffff',
  ink: '#0f172a',
  body: '#475569',
  muted: '#94a3b8',
  border: '#e8ecf3',
  success: '#16a34a',
  successSoft: '#dcfce7',
  danger: '#ef4444',
  warning: '#f59e0b',
  white: '#ffffff',
  gold: '#f59e0b',
};

// Deterministic avatar color from a string (name/id).
const AVATAR_COLORS = ['#4f46e5', '#06b6d4', '#a855f7', '#ef4444', '#f59e0b', '#16a34a', '#0ea5e9', '#db2777'];
export function colorFor(seed = '') {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

export function initials(name = '') {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join('');
}

export const radius = { sm: 10, md: 16, lg: 22, pill: 999 };
export const space = (n) => n * 4;

export const shadow = {
  card: {
    shadowColor: '#0f172a',
    shadowOpacity: 0.06,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 6 },
    elevation: 2,
  },
  fab: {
    shadowColor: colors.primary,
    shadowOpacity: 0.35,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 8 },
    elevation: 6,
  },
};

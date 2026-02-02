/**
 * Color Palette - Monochrome Design System (UA App Style)
 *
 * A minimal, monochrome color palette matching the UA app screenshots.
 * No gradients, no hover effects, clean and professional.
 */

export const colors = {
  // Base colors
  background: '#FFFFFF',
  foreground: '#171717',

  // Card colors
  card: '#FFFFFF',
  cardForeground: '#171717',

  // Popover colors
  popover: '#FFFFFF',
  popoverForeground: '#171717',

  // Primary brand color (dark gray/black)
  primary: '#171717',
  primaryForeground: '#FAFAFA',

  // Secondary colors (light gray)
  secondary: '#F5F5F5',
  secondaryForeground: '#171717',

  // Muted colors
  muted: '#F5F5F5',
  mutedForeground: '#737373',

  // Accent colors
  accent: '#F5F5F5',
  accentForeground: '#171717',

  // Destructive/error colors
  destructive: '#EF4444',
  destructiveForeground: '#FAFAFA',

  // Border colors
  border: '#E5E5E5',
  borderDark: '#D4D4D4',

  // Input colors
  input: '#E5E5E5',
  inputBackground: '#F7F7F5',

  // Ring/focus indicator
  ring: '#171717',

  // Status colors - Attendance states
  status: {
    present: {
      bg: '#DCFCE7',
      fg: '#166534',
      border: '#86EFAC',
    },
    late: {
      bg: '#FEF3C7',
      fg: '#92400E',
      border: '#FDE047',
    },
    absent: {
      bg: '#FEE2E2',
      fg: '#991B1B',
      border: '#FCA5A5',
    },
    early_leave: {
      bg: '#FED7AA',
      fg: '#9A3412',
      border: '#FDBA74',
    },
  },

  // Success/info/warning (for other use cases)
  success: '#166534',
  successLight: '#DCFCE7',
  warning: '#92400E',
  warningLight: '#FEF3C7',
  error: '#991B1B',
  errorLight: '#FEE2E2',
  info: '#1E40AF',
  infoLight: '#DBEAFE',

  // Text colors
  text: {
    primary: '#171717',
    secondary: '#737373',
    tertiary: '#A3A3A3',
    disabled: '#D4D4D4',
    inverse: '#FAFAFA',
  },
} as const;

export type ColorKey = keyof typeof colors;
export type StatusKey = keyof typeof colors.status;

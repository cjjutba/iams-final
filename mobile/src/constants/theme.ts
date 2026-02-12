/**
 * Theme - Consolidated Design System
 *
 * Central export of all design tokens: colors, typography, spacing, shadows.
 * Import this file throughout the app for consistent styling.
 */

import { colors } from './colors';
import { typography } from './typography';
import { spacing, borderRadius, shadows } from './spacing';

export const theme = {
  colors,
  typography,
  spacing,
  borderRadius,
  shadows,

  // Common layout values
  layout: {
    screenPadding: spacing[4], // 16px
    cardPadding: spacing[4], // 16px
    sectionSpacing: spacing[6], // 24px
    listItemSpacing: spacing[3], // 12px

    // Header heights
    headerHeight: 56,
    tabBarHeight: 56,

    // Input heights
    inputHeight: {
      sm: 36,
      md: 44,
      lg: 52,
    },

    // Button heights
    buttonHeight: {
      sm: 36,
      md: 44,
      lg: 52,
    },
  },

  // Press feedback opacity (no other effects)
  interaction: {
    activeOpacity: 0.8,
    disabledOpacity: 0.5,
  },
} as const;

// Export individual tokens for convenience
export { colors } from './colors';
export { typography } from './typography';
export { spacing, borderRadius, shadows } from './spacing';

// Type exports
export type Theme = typeof theme;

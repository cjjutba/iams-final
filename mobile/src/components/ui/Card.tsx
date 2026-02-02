/**
 * Card Component - Container with Shadow
 *
 * Card container matching UA app style:
 * - White background
 * - 16px padding
 * - 12px border radius
 * - Subtle shadow
 * - Optional press feedback
 */

import React from 'react';
import { View, TouchableOpacity, ViewStyle } from 'react-native';
import { theme } from '../../constants';

interface CardProps {
  variant?: 'default' | 'outlined';
  children: React.ReactNode;
  style?: ViewStyle;
  onPress?: () => void;
}

export const Card: React.FC<CardProps> = ({
  variant = 'default',
  children,
  style,
  onPress,
}) => {
  const cardStyle: ViewStyle = {
    backgroundColor: theme.colors.card,
    borderRadius: theme.borderRadius.lg,
    padding: theme.layout.cardPadding,
    ...(variant === 'default' ? theme.shadows.sm : {}),
    ...(variant === 'outlined' && {
      borderWidth: 1,
      borderColor: theme.colors.border,
    }),
  };

  if (onPress) {
    return (
      <TouchableOpacity
        style={[cardStyle, style]}
        onPress={onPress}
        activeOpacity={theme.interaction.activeOpacity}
      >
        {children}
      </TouchableOpacity>
    );
  }

  return <View style={[cardStyle, style]}>{children}</View>;
};

/**
 * Card Component - Flat Container with Border
 *
 * Card container with clean, minimal style:
 * - White background
 * - 12px padding (compact)
 * - 12px border radius
 * - 1px border, no shadow
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
    borderRadius: 12,
    padding: theme.spacing[3],
    borderWidth: 1,
    borderColor: theme.colors.border,
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

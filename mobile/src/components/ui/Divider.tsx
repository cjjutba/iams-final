/**
 * Divider Component - Horizontal Separator
 *
 * Simple divider line with configurable spacing.
 */

import React from 'react';
import { View, ViewStyle } from 'react-native';
import { theme, SpacingKey } from '../../constants';

interface DividerProps {
  spacing?: SpacingKey;
  color?: string;
}

export const Divider: React.FC<DividerProps> = ({
  spacing = 4,
  color = theme.colors.border,
}) => {
  const containerStyle: ViewStyle = {
    marginVertical: theme.spacing[spacing],
  };

  const lineStyle: ViewStyle = {
    height: 1,
    backgroundColor: color,
  };

  return (
    <View style={containerStyle}>
      <View style={lineStyle} />
    </View>
  );
};

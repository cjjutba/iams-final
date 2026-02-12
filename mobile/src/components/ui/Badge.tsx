/**
 * Badge Component - Status Badge
 *
 * Displays attendance status with appropriate colors:
 * - Present: Green
 * - Late: Yellow
 * - Absent: Red
 * - Early Leave: Orange
 */

import React from 'react';
import { View, ViewStyle } from 'react-native';
import { theme } from '../../constants';
import { Text } from './Text';
import { AttendanceStatus } from '../../types';
import { getStatusBackgroundColor, getStatusColor, getStatusLabel } from '../../utils';

interface BadgeProps {
  status: AttendanceStatus;
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({ status, size = 'md' }) => {
  const backgroundColor = getStatusBackgroundColor(status);
  const textColor = getStatusColor(status);
  const label = getStatusLabel(status);

  const containerStyle: ViewStyle = {
    backgroundColor,
    borderRadius: theme.borderRadius.full,
    paddingHorizontal: size === 'sm' ? theme.spacing[2] : theme.spacing[3],
    paddingVertical: size === 'sm' ? theme.spacing[1] : theme.spacing[1],
    alignSelf: 'flex-start',
  };

  return (
    <View style={containerStyle}>
      <Text
        variant={size === 'sm' ? 'caption' : 'bodySmall'}
        weight="600"
        color={textColor}
      >
        {label}
      </Text>
    </View>
  );
};

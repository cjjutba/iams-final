/**
 * Loader Component - Loading Indicator
 *
 * Displays loading spinner with optional message.
 * Can be used inline or full-screen.
 */

import React from 'react';
import { View, ActivityIndicator, ViewStyle } from 'react-native';
import { theme } from '../../constants';
import { Text } from './Text';

interface LoaderProps {
  message?: string;
  fullScreen?: boolean;
  size?: 'small' | 'large';
  color?: string;
}

export const Loader: React.FC<LoaderProps> = ({
  message,
  fullScreen = false,
  size = 'large',
  color = theme.colors.primary,
}) => {
  const containerStyle: ViewStyle = fullScreen
    ? {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: theme.colors.background,
      }
    : {
        padding: theme.spacing[4],
        alignItems: 'center',
      };

  return (
    <View style={containerStyle}>
      <ActivityIndicator size={size} color={color} />
      {message && (
        <Text
          variant="bodySmall"
          color={theme.colors.text.secondary}
          align="center"
          style={{ marginTop: theme.spacing[3] }}
        >
          {message}
        </Text>
      )}
    </View>
  );
};

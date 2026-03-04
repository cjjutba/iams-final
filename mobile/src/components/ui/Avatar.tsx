/**
 * Avatar Component - User Avatar with Initials Fallback
 *
 * Displays user avatar with:
 * - Image if URL provided
 * - Initials fallback if no image
 * - 4 size options (sm, md, lg, xl)
 * - Circular shape
 */

import React from 'react';
import { View, Image, ViewStyle, TextStyle } from 'react-native';
import { theme } from '../../constants';
import { Text } from './Text';
import { getInitials } from '../../utils';

interface AvatarProps {
  firstName: string;
  lastName: string;
  imageUrl?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

export const Avatar: React.FC<AvatarProps> = ({
  firstName,
  lastName,
  imageUrl,
  size = 'md',
}) => {
  const sizeMap = {
    sm: 32,
    md: 40,
    lg: 56,
    xl: 80,
  };

  const fontSizeMap = {
    sm: theme.typography.fontSize.xs,
    md: theme.typography.fontSize.sm,
    lg: theme.typography.fontSize.lg,
    xl: theme.typography.fontSize['2xl'],
  };

  const dimensions = sizeMap[size];
  const fontSize = fontSizeMap[size];

  const containerStyle: ViewStyle = {
    width: dimensions,
    height: dimensions,
    borderRadius: dimensions / 2,
    backgroundColor: theme.colors.secondary,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  };

  const initials = getInitials(firstName, lastName);

  return (
    <View style={containerStyle}>
      {imageUrl ? (
        <Image
          source={{ uri: imageUrl }}
          style={{ width: dimensions, height: dimensions }}
          resizeMode="cover"
        />
      ) : (
        <Text
          variant="body"
          weight="600"
          color={theme.colors.text.primary}
          style={{ fontSize }}
        >
          {initials}
        </Text>
      )}
    </View>
  );
};

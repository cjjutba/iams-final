/**
 * Button Component - Interactive Button with Variants
 *
 * Supports 4 variants matching UA app style:
 * - primary: Solid black background, white text
 * - secondary: Light gray background, dark text
 * - outline: Transparent background, dark border
 * - ghost: Transparent background, no border
 */

import React from 'react';
import {
  TouchableOpacity,
  TouchableOpacityProps,
  ViewStyle,
  TextStyle,
  ActivityIndicator,
  View,
} from 'react-native';
import { theme } from '../../constants';
import { Text } from './Text';

interface ButtonProps extends TouchableOpacityProps {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  fullWidth?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  children: string | React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  fullWidth = false,
  disabled = false,
  leftIcon,
  rightIcon,
  style,
  children,
  ...props
}) => {
  // Variant styles
  const variantStyles: Record<string, { container: ViewStyle; text: TextStyle }> = {
    primary: {
      container: {
        backgroundColor: theme.colors.primary,
        borderWidth: 0,
      },
      text: {
        color: theme.colors.primaryForeground,
      },
    },
    secondary: {
      container: {
        backgroundColor: theme.colors.secondary,
        borderWidth: 0,
      },
      text: {
        color: theme.colors.secondaryForeground,
      },
    },
    outline: {
      container: {
        backgroundColor: 'transparent',
        borderWidth: 1,
        borderColor: theme.colors.border,
      },
      text: {
        color: theme.colors.foreground,
      },
    },
    ghost: {
      container: {
        backgroundColor: 'transparent',
        borderWidth: 0,
      },
      text: {
        color: theme.colors.foreground,
      },
    },
  };

  // Size styles
  const sizeStyles: Record<string, ViewStyle> = {
    sm: {
      height: theme.layout.buttonHeight.sm,
      paddingHorizontal: theme.spacing[3],
    },
    md: {
      height: theme.layout.buttonHeight.md,
      paddingHorizontal: theme.spacing[4],
    },
    lg: {
      height: theme.layout.buttonHeight.lg,
      paddingHorizontal: theme.spacing[5],
    },
  };

  const containerStyle: ViewStyle = {
    ...variantStyles[variant].container,
    ...sizeStyles[size],
    borderRadius: theme.borderRadius.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    opacity: disabled || loading ? theme.interaction.disabledOpacity : 1,
    ...(fullWidth && { width: '100%' }),
  };

  const textStyle: TextStyle = {
    ...variantStyles[variant].text,
  };

  return (
    <TouchableOpacity
      style={[containerStyle, style]}
      disabled={disabled || loading}
      activeOpacity={theme.interaction.activeOpacity}
      {...props}
    >
      {loading ? (
        <ActivityIndicator
          size="small"
          color={variant === 'primary' ? theme.colors.primaryForeground : theme.colors.foreground}
        />
      ) : (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.spacing[2] }}>
          {leftIcon}
          {typeof children === 'string' ? (
            <Text variant="button" style={textStyle}>
              {children}
            </Text>
          ) : (
            children
          )}
          {rightIcon}
        </View>
      )}
    </TouchableOpacity>
  );
};

/**
 * Input Component - Text Input with Error States
 *
 * Form input component with:
 * - Label support
 * - Error message display
 * - Left/right icon support
 * - Password toggle
 * - Light background (#F7F7F5) matching UA app
 */

import React, { useState } from 'react';
import {
  View,
  TextInput,
  TextInputProps,
  ViewStyle,
  TextStyle,
  TouchableOpacity,
} from 'react-native';
import { Eye, EyeOff } from 'lucide-react-native';
import { theme } from '../../constants';
import { Text } from './Text';

interface InputProps extends TextInputProps {
  label?: string;
  error?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  isPassword?: boolean;
  containerStyle?: ViewStyle;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  leftIcon,
  rightIcon,
  isPassword = false,
  containerStyle,
  style,
  ...props
}) => {
  const [isFocused, setIsFocused] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const inputContainerStyle: ViewStyle = {
    backgroundColor: theme.colors.inputBackground,
    borderWidth: 1,
    borderColor: isFocused
      ? theme.colors.borderDark
      : theme.colors.border,
    borderRadius: theme.borderRadius.md,
    height: theme.layout.inputHeight.md,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: theme.spacing[3],
  };

  const inputStyle: TextStyle = {
    flex: 1,
    fontSize: theme.typography.fontSize.base,
    color: theme.colors.text.primary,
    paddingHorizontal: theme.spacing[2],
  };

  return (
    <View style={containerStyle}>
      {label && (
        <Text
          variant="label"
          color={theme.colors.text.secondary}
          style={{ marginBottom: theme.spacing[2] }}
        >
          {label}
        </Text>
      )}

      <View style={inputContainerStyle}>
        {leftIcon && <View style={{ marginRight: theme.spacing[2] }}>{leftIcon}</View>}

        <TextInput
          style={inputStyle}
          placeholderTextColor={theme.colors.text.tertiary}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          secureTextEntry={isPassword && !showPassword}
          {...props}
        />

        {isPassword && (
          <TouchableOpacity
            onPress={() => setShowPassword(!showPassword)}
            style={{ marginLeft: theme.spacing[2], padding: 4 }}
            activeOpacity={theme.interaction.activeOpacity}
          >
            {showPassword ? (
              <Eye size={20} color={theme.colors.text.tertiary} />
            ) : (
              <EyeOff size={20} color={theme.colors.text.tertiary} />
            )}
          </TouchableOpacity>
        )}

        {rightIcon && !isPassword && (
          <View style={{ marginLeft: theme.spacing[2] }}>{rightIcon}</View>
        )}
      </View>

      {error && (
        <Text
          variant="caption"
          color={theme.colors.error}
          style={{ marginTop: theme.spacing[1] }}
        >
          {error}
        </Text>
      )}
    </View>
  );
};

/**
 * Text Component - Typography with Design System
 *
 * Custom text component that applies typography variants from the design system.
 * Supports all typography variants: h1, h2, h3, h4, body, bodySmall, caption, button, label.
 */

import React from 'react';
import { Text as RNText, TextProps as RNTextProps, TextStyle } from 'react-native';
import { theme, TypographyVariant } from '../../constants';

interface TextProps extends RNTextProps {
  variant?: TypographyVariant;
  color?: string;
  align?: 'left' | 'center' | 'right' | 'justify';
  weight?: '400' | '500' | '600' | '700';
}

export const Text: React.FC<TextProps> = ({
  variant = 'body',
  color = theme.colors.text.primary,
  align = 'left',
  weight,
  style,
  children,
  ...props
}) => {
  const variantStyle = theme.typography.variants[variant];

  const textStyle: TextStyle = {
    fontSize: variantStyle.fontSize,
    fontWeight: weight || variantStyle.fontWeight,
    lineHeight: variantStyle.lineHeight,
    letterSpacing: variantStyle.letterSpacing,
    color,
    textAlign: align,
  };

  return (
    <RNText style={[textStyle, style]} {...props}>
      {children}
    </RNText>
  );
};

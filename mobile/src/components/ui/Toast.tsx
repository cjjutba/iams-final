/**
 * Toast Component
 *
 * Animated toast notification for success, error, warning, and info messages.
 * Appears at the top of the screen with auto-dismiss functionality.
 */

import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Animated, TouchableOpacity, Platform } from 'react-native';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react-native';
import { Text } from './Text';
import { theme } from '../../constants';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastProps {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
  onDismiss: (id: string) => void;
}

const TOAST_CONFIG = {
  success: {
    icon: CheckCircle,
    backgroundColor: theme.colors.success,
    color: theme.colors.background,
  },
  error: {
    icon: XCircle,
    backgroundColor: theme.colors.error,
    color: theme.colors.background,
  },
  warning: {
    icon: AlertTriangle,
    backgroundColor: theme.colors.warning,
    color: theme.colors.text.primary,
  },
  info: {
    icon: Info,
    backgroundColor: theme.colors.primary,
    color: theme.colors.background,
  },
};

export const Toast: React.FC<ToastProps> = ({
  id,
  type,
  title,
  message,
  duration = 4000,
  onDismiss,
}) => {
  const translateY = useRef(new Animated.Value(-100)).current;
  const opacity = useRef(new Animated.Value(0)).current;

  const config = TOAST_CONFIG[type];
  const Icon = config.icon;

  useEffect(() => {
    // Slide in animation
    Animated.parallel([
      Animated.spring(translateY, {
        toValue: 0,
        useNativeDriver: true,
        tension: 50,
        friction: 8,
      }),
      Animated.timing(opacity, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }),
    ]).start();

    // Auto dismiss
    const timer = setTimeout(() => {
      handleDismiss();
    }, duration);

    return () => clearTimeout(timer);
  }, []);

  const handleDismiss = () => {
    Animated.parallel([
      Animated.timing(translateY, {
        toValue: -100,
        duration: 250,
        useNativeDriver: true,
      }),
      Animated.timing(opacity, {
        toValue: 0,
        duration: 250,
        useNativeDriver: true,
      }),
    ]).start(() => {
      onDismiss(id);
    });
  };

  return (
    <Animated.View
      style={[
        styles.container,
        {
          backgroundColor: config.backgroundColor,
          transform: [{ translateY }],
          opacity,
        },
      ]}
    >
      <View style={styles.content}>
        <Icon size={22} color={config.color} style={styles.icon} />
        <View style={styles.textContainer}>
          {title ? (
            <Text
              variant="body"
              weight="600"
              style={[styles.title, { color: config.color }]}
            >
              {title}
            </Text>
          ) : null}
          <Text
            variant="bodySmall"
            style={[styles.message, { color: config.color }]}
          >
            {message}
          </Text>
        </View>
        <TouchableOpacity
          onPress={handleDismiss}
          style={styles.closeButton}
          activeOpacity={theme.interaction.activeOpacity}
        >
          <X size={18} color={config.color} />
        </TouchableOpacity>
      </View>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: Platform.OS === 'ios' ? 50 : 20,
    left: theme.spacing[4],
    right: theme.spacing[4],
    borderRadius: theme.borderRadius.lg,
    paddingHorizontal: theme.spacing[4],
    paddingVertical: theme.spacing[3],
    ...theme.shadows.md,
    zIndex: 9999,
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  icon: {
    marginRight: theme.spacing[3],
  },
  textContainer: {
    flex: 1,
  },
  title: {
    marginBottom: theme.spacing[1],
  },
  message: {
    lineHeight: 18,
  },
  closeButton: {
    marginLeft: theme.spacing[2],
    padding: theme.spacing[1],
  },
});

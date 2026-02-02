/**
 * Header Component
 *
 * Reusable header with title, back button, and action buttons.
 * Used across main screens for consistent navigation.
 */

import React from 'react';
import { View, TouchableOpacity, StyleSheet } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { ChevronLeft, Bell } from 'lucide-react-native';
import { theme } from '../../constants';
import { Text } from '../ui';

interface HeaderProps {
  title: string;
  showBack?: boolean;
  showNotification?: boolean;
  rightAction?: React.ReactNode;
  onNotificationPress?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  showBack = false,
  showNotification = false,
  rightAction,
  onNotificationPress,
}) => {
  const navigation = useNavigation();

  return (
    <View style={styles.container}>
      {/* Left section */}
      <View style={styles.section}>
        {showBack && (
          <TouchableOpacity
            onPress={() => navigation.goBack()}
            activeOpacity={theme.interaction.activeOpacity}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            <ChevronLeft size={24} color={theme.colors.text.primary} />
          </TouchableOpacity>
        )}
      </View>

      {/* Center section */}
      <View style={styles.titleContainer}>
        <Text variant="h3" weight="semibold" align="center" numberOfLines={1}>
          {title}
        </Text>
      </View>

      {/* Right section */}
      <View style={styles.section}>
        {rightAction ? (
          rightAction
        ) : showNotification ? (
          <TouchableOpacity
            onPress={onNotificationPress}
            activeOpacity={theme.interaction.activeOpacity}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            <Bell size={24} color={theme.colors.text.primary} />
          </TouchableOpacity>
        ) : null}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: theme.spacing[4], // 16px
    paddingVertical: theme.spacing[3], // 12px
    backgroundColor: theme.colors.background,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  section: {
    width: 40,
    alignItems: 'flex-start',
  },
  titleContainer: {
    flex: 1,
    paddingHorizontal: theme.spacing[4], // 16px
  },
});

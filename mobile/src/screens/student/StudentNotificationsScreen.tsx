/**
 * Student Notifications Screen
 *
 * Displays list of notifications
 * For now, shows placeholder UI - can be connected to real notification service later
 */

import React from 'react';
import { View, StyleSheet, FlatList } from 'react-native';
import { Bell, CheckCircle, AlertTriangle, Info } from 'lucide-react-native';
import { theme, strings } from '../../constants';
import { formatTimeAgo } from '../../utils';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card } from '../../components/ui';

interface Notification {
  id: string;
  type: 'success' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
}

// Mock data - replace with real API integration
const MOCK_NOTIFICATIONS: Notification[] = [
  {
    id: '1',
    type: 'success',
    title: 'Attendance Recorded',
    message: 'Your attendance for CS101 has been recorded successfully',
    timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(), // 30 min ago
    read: false,
  },
  {
    id: '2',
    type: 'warning',
    title: 'Early Leave Alert',
    message: 'You left CS102 class 15 minutes early',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
    read: false,
  },
  {
    id: '3',
    type: 'info',
    title: 'Schedule Update',
    message: 'Your MATH101 class has been moved to Room 203',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), // 1 day ago
    read: true,
  },
];

export const StudentNotificationsScreen: React.FC = () => {
  const getIcon = (type: Notification['type']) => {
    switch (type) {
      case 'success':
        return <CheckCircle size={24} color={theme.colors.status.success} />;
      case 'warning':
        return <AlertTriangle size={24} color={theme.colors.status.warning} />;
      case 'info':
        return <Info size={24} color={theme.colors.primary} />;
    }
  };

  const renderNotification = ({ item }: { item: Notification }) => (
    <Card
      variant={item.read ? 'outlined' : 'default'}
      style={[styles.notificationCard, !item.read && styles.unreadCard]}
    >
      <View style={styles.notificationContent}>
        <View style={styles.iconContainer}>{getIcon(item.type)}</View>

        <View style={styles.textContainer}>
          <Text variant="body" weight="semibold" style={styles.title}>
            {item.title}
          </Text>
          <Text variant="bodySmall" color={theme.colors.text.secondary} style={styles.message}>
            {item.message}
          </Text>
          <Text variant="caption" color={theme.colors.text.tertiary} style={styles.timestamp}>
            {formatTimeAgo(item.timestamp)}
          </Text>
        </View>

        {!item.read && <View style={styles.unreadDot} />}
      </View>
    </Card>
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Bell size={48} color={theme.colors.text.tertiary} style={styles.emptyIcon} />
      <Text variant="body" color={theme.colors.text.secondary} align="center">
        {strings.empty.noNotifications}
      </Text>
      <Text
        variant="bodySmall"
        color={theme.colors.text.tertiary}
        align="center"
        style={styles.emptySubtext}
      >
        You're all caught up!
      </Text>
    </View>
  );

  return (
    <ScreenLayout safeArea padded={false}>
      <Header showBack title={strings.student.notifications} />

      <FlatList
        data={MOCK_NOTIFICATIONS}
        keyExtractor={(item) => item.id}
        renderItem={renderNotification}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
      />
    </ScreenLayout>
  );
};

const styles = StyleSheet.create({
  listContent: {
    padding: theme.spacing[4],
  },
  notificationCard: {
    marginBottom: theme.spacing[3],
  },
  unreadCard: {
    borderLeftWidth: 3,
    borderLeftColor: theme.colors.primary,
  },
  notificationContent: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  iconContainer: {
    marginRight: theme.spacing[3],
  },
  textContainer: {
    flex: 1,
  },
  title: {
    marginBottom: theme.spacing[1],
  },
  message: {
    marginBottom: theme.spacing[2],
    lineHeight: 20,
  },
  timestamp: {
    // No additional styles needed
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: theme.colors.primary,
    marginLeft: theme.spacing[2],
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: theme.spacing[12],
  },
  emptyIcon: {
    marginBottom: theme.spacing[4],
  },
  emptySubtext: {
    marginTop: theme.spacing[2],
  },
});

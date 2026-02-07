/**
 * Student Notifications Screen
 *
 * Displays list of notifications fetched from the API.
 * Supports pull-to-refresh, mark as read, loading/error/empty states.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  RefreshControl,
  TouchableOpacity,
  ActivityIndicator,
  type ViewStyle,
} from 'react-native';
import { Bell, CheckCircle, AlertTriangle, Info, RefreshCw } from 'lucide-react-native';
import { api } from '../../utils/api';
import { theme, strings } from '../../constants';
import { formatTimeAgo, getErrorMessage } from '../../utils';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Button } from '../../components/ui';
import type { ApiResponse } from '../../types';

/** Notification shape returned by the API */
interface Notification {
  id: string;
  type: 'success' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
}

export const StudentNotificationsScreen: React.FC = () => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [markingReadIds, setMarkingReadIds] = useState<Set<string>>(new Set());

  // ---------- data fetching ----------

  const fetchNotifications = useCallback(async (silent = false) => {
    if (!silent) setIsLoading(true);
    setError(null);

    try {
      const response = await api.get<ApiResponse<Notification[]>>('/notifications');
      setNotifications(response.data.data || []);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    fetchNotifications(true);
  }, [fetchNotifications]);

  // ---------- mark as read ----------

  const handleMarkAsRead = useCallback(async (id: string) => {
    // Optimistic update
    setMarkingReadIds((prev) => new Set(prev).add(id));
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );

    try {
      await api.patch(`/notifications/${id}/read`);
    } catch (err) {
      // Revert on failure
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read: false } : n))
      );
      console.error('Failed to mark notification as read:', err);
    } finally {
      setMarkingReadIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }, []);

  // ---------- icon helper ----------

  const getIcon = (type: Notification['type']) => {
    switch (type) {
      case 'success':
        return <CheckCircle size={24} color={theme.colors.success} />;
      case 'warning':
        return <AlertTriangle size={24} color={theme.colors.warning} />;
      case 'info':
        return <Info size={24} color={theme.colors.info} />;
    }
  };

  // ---------- render items ----------

  const renderNotification = ({ item }: { item: Notification }) => (
    <TouchableOpacity
      activeOpacity={theme.interaction.activeOpacity}
      onPress={() => {
        if (!item.read && !markingReadIds.has(item.id)) {
          handleMarkAsRead(item.id);
        }
      }}
      disabled={item.read || markingReadIds.has(item.id)}
    >
      <Card
        variant={item.read ? 'outlined' : 'default'}
        style={StyleSheet.flatten([styles.notificationCard, !item.read && styles.unreadCard]) as ViewStyle}
      >
        <View style={styles.notificationContent}>
          <View style={styles.iconContainer}>{getIcon(item.type)}</View>

          <View style={styles.textContainer}>
            <Text variant="body" weight="600" style={styles.title}>
              {item.title}
            </Text>
            <Text variant="bodySmall" color={theme.colors.text.secondary} style={styles.message}>
              {item.message}
            </Text>
            <Text variant="caption" color={theme.colors.text.tertiary} style={styles.timestamp}>
              {formatTimeAgo(item.timestamp)}
            </Text>
          </View>

          {!item.read && !markingReadIds.has(item.id) && <View style={styles.unreadDot} />}
          {markingReadIds.has(item.id) && (
            <ActivityIndicator size="small" color={theme.colors.text.tertiary} />
          )}
        </View>
      </Card>
    </TouchableOpacity>
  );

  // ---------- empty state ----------

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

  // ---------- error state ----------

  if (error && !isRefreshing && notifications.length === 0) {
    return (
      <ScreenLayout safeArea padded={false}>
        <Header showBack title={strings.student.notifications} />
        <View style={styles.errorContainer}>
          <RefreshCw size={40} color={theme.colors.text.tertiary} style={styles.errorIcon} />
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            {error}
          </Text>
          <Button
            variant="secondary"
            size="md"
            onPress={() => fetchNotifications()}
            style={styles.retryButton}
          >
            {strings.common.retry}
          </Button>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- loading state ----------

  if (isLoading && notifications.length === 0) {
    return (
      <ScreenLayout safeArea padded={false}>
        <Header showBack title={strings.student.notifications} />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text
            variant="bodySmall"
            color={theme.colors.text.secondary}
            align="center"
            style={styles.loadingText}
          >
            {strings.common.loading}
          </Text>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- main render ----------

  return (
    <ScreenLayout safeArea padded={false}>
      <Header showBack title={strings.student.notifications} />

      <FlatList
        data={notifications}
        keyExtractor={(item) => item.id}
        renderItem={renderNotification}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={[
          styles.listContent,
          notifications.length === 0 && styles.listContentEmpty,
        ]}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            colors={[theme.colors.primary]}
            tintColor={theme.colors.primary}
          />
        }
      />
    </ScreenLayout>
  );
};

const styles = StyleSheet.create({
  listContent: {
    padding: theme.spacing[4],
  },
  listContentEmpty: {
    flexGrow: 1,
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
    marginTop: theme.spacing[1],
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
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: theme.spacing[3],
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: theme.spacing[6],
  },
  errorIcon: {
    marginBottom: theme.spacing[4],
  },
  retryButton: {
    marginTop: theme.spacing[4],
  },
});

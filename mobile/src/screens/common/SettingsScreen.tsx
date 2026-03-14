/**
 * Settings Screen
 *
 * App settings and preferences used by both students and faculty.
 * Implements:
 * - Notification preference toggles (synced with backend API)
 *   - Attendance Confirmations
 *   - Early Leave Alerts
 *   - Anomaly Alerts (faculty only)
 *   - Low Attendance Warning
 *   - Daily Digest (faculty only)
 *   - Weekly Digest
 *   - Email Notifications
 * - Theme display (read-only for now)
 * - About section with real app version
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Linking,
  Platform,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { ChevronRight } from 'lucide-react-native';
import { useAuth } from '../../hooks';
import { useToast } from '../../hooks/useToast';
import { theme, config } from '../../constants';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card } from '../../components/ui';
import {
  notificationService,
  type NotificationPreference,
  type NotificationPreferenceUpdate,
} from '../../services/notificationService';

export const SettingsScreen: React.FC = () => {
  const navigation = useNavigation();
  const { isFaculty } = useAuth();
  const { showError } = useToast();

  const [prefs, setPrefs] = useState<NotificationPreference | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [updatingKey, setUpdatingKey] = useState<string | null>(null);

  const loadPreferences = useCallback(async () => {
    try {
      const data = await notificationService.getPreferences();
      setPrefs(data);
    } catch (err) {
      console.error('Failed to load notification preferences:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPreferences();
  }, [loadPreferences]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await loadPreferences();
    setIsRefreshing(false);
  }, [loadPreferences]);

  const handleToggle = async (key: keyof NotificationPreference, value: boolean) => {
    if (!prefs) return;
    const previous = prefs[key];
    // Optimistic update
    setPrefs({ ...prefs, [key]: value });
    setUpdatingKey(key);
    try {
      const updated = await notificationService.updatePreferences({
        [key]: value,
      } as NotificationPreferenceUpdate);
      setPrefs(updated);
    } catch {
      // Revert on failure
      setPrefs({ ...prefs, [key]: previous });
      showError('Failed to update preference');
    } finally {
      setUpdatingKey(null);
    }
  };

  return (
    <ScreenLayout safeArea padded={false}>
      <Header showBack title="Settings" />

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        alwaysBounceVertical={true}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            colors={[theme.colors.primary]}
            tintColor={theme.colors.primary}
          />
        }
      >
        {/* Notification Preferences */}
        <Card>
          <Text variant="h4" weight="600" style={styles.sectionTitle}>
            Notification Preferences
          </Text>

          {isLoading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="small" color={theme.colors.primary} />
              <Text
                variant="bodySmall"
                color={theme.colors.text.tertiary}
                style={styles.loadingText}
              >
                Loading preferences...
              </Text>
            </View>
          ) : prefs ? (
            <>
              <ToggleItem
                label="Attendance Confirmations"
                description="Confirm when your attendance is successfully recorded"
                value={prefs.attendance_confirmation}
                onToggle={(v) => handleToggle('attendance_confirmation', v)}
                disabled={updatingKey === 'attendance_confirmation'}
              />

              <ToggleItem
                label="Early Leave Alerts"
                description="Get notified when an early leave is detected"
                value={prefs.early_leave_alerts}
                onToggle={(v) => handleToggle('early_leave_alerts', v)}
                disabled={updatingKey === 'early_leave_alerts'}
              />

              {isFaculty && (
                <ToggleItem
                  label="Anomaly Alerts"
                  description="Receive alerts about unusual attendance patterns"
                  value={prefs.anomaly_alerts}
                  onToggle={(v) => handleToggle('anomaly_alerts', v)}
                  disabled={updatingKey === 'anomaly_alerts'}
                />
              )}

              <ToggleItem
                label="Low Attendance Warning"
                description="Get warned when attendance drops below the threshold"
                value={prefs.low_attendance_warning}
                onToggle={(v) => handleToggle('low_attendance_warning', v)}
                disabled={updatingKey === 'low_attendance_warning'}
              />

              {isFaculty && (
                <ToggleItem
                  label="Daily Digest"
                  description="Receive a daily attendance summary at 8 PM"
                  value={prefs.daily_digest}
                  onToggle={(v) => handleToggle('daily_digest', v)}
                  disabled={updatingKey === 'daily_digest'}
                />
              )}

              <ToggleItem
                label="Weekly Digest"
                description="Receive a weekly attendance summary"
                value={prefs.weekly_digest}
                onToggle={(v) => handleToggle('weekly_digest', v)}
                disabled={updatingKey === 'weekly_digest'}
              />

              <ToggleItem
                label="Email Notifications"
                description="Also receive notifications via email"
                value={prefs.email_enabled}
                onToggle={(v) => handleToggle('email_enabled', v)}
                disabled={updatingKey === 'email_enabled'}
                isLast
              />
            </>
          ) : (
            <Text variant="bodySmall" color={theme.colors.text.tertiary}>
              Unable to load preferences. Pull to refresh.
            </Text>
          )}
        </Card>

        {/* Appearance */}
        <Card style={styles.card}>
          <Text variant="h4" weight="600" style={styles.sectionTitle}>
            Appearance
          </Text>

          <SettingItem label="Theme" value="Light" />
          <SettingItem label="Language" value="English" isLast />
        </Card>

        {/* About */}
        <Card style={styles.card}>
          <Text variant="h4" weight="600" style={styles.sectionTitle}>
            About
          </Text>

          <SettingItem label="App Version" value={config.APP_VERSION} />
          <SettingItem label="App Name" value={config.APP_NAME} />
          <SettingItem
            label="Platform"
            value={Platform.OS === 'ios' ? 'iOS' : 'Android'}
            isLast
          />
        </Card>

        {/* Legal */}
        <Card style={styles.card}>
          <Text variant="h4" weight="600" style={styles.sectionTitle}>
            Legal
          </Text>

          <SettingItem
            label="Privacy Policy"
            onPress={() => {
              Linking.openURL('https://iams.jrmsu.edu.ph/privacy').catch(() => {});
            }}
          />
          <SettingItem
            label="Terms of Service"
            onPress={() => {
              Linking.openURL('https://iams.jrmsu.edu.ph/terms').catch(() => {});
            }}
            isLast
          />
        </Card>

        {/* Footer */}
        <View style={styles.footer}>
          <Text
            variant="caption"
            color={theme.colors.text.tertiary}
            align="center"
          >
            IAMS - Intelligent Attendance Monitoring System
          </Text>
          <Text
            variant="caption"
            color={theme.colors.text.tertiary}
            align="center"
            style={styles.footerSubtext}
          >
            Jose Rizal Memorial State University
          </Text>
        </View>
      </ScrollView>
    </ScreenLayout>
  );
};

// ---------- sub-components ----------

/** A toggle row (switch) for notification preferences */
const ToggleItem: React.FC<{
  label: string;
  description?: string;
  value: boolean;
  onToggle: (value: boolean) => void;
  disabled?: boolean;
  isLast?: boolean;
}> = ({ label, description, value, onToggle, disabled = false, isLast = false }) => (
  <View style={[styles.settingItem, isLast && styles.settingItemLast]}>
    <View style={styles.toggleTextContainer}>
      <Text variant="body">{label}</Text>
      {description && (
        <Text
          variant="caption"
          color={theme.colors.text.tertiary}
          style={styles.toggleDescription}
        >
          {description}
        </Text>
      )}
    </View>
    <Switch
      value={value}
      onValueChange={onToggle}
      disabled={disabled}
      trackColor={{
        false: theme.colors.border,
        true: theme.colors.primary,
      }}
      thumbColor={theme.colors.background}
      ios_backgroundColor={theme.colors.border}
    />
  </View>
);

/** A static or tappable settings row */
const SettingItem: React.FC<{
  label: string;
  value?: string;
  onPress?: () => void;
  isLast?: boolean;
}> = ({ label, value, onPress, isLast = false }) => (
  <TouchableOpacity
    style={[styles.settingItem, isLast && styles.settingItemLast]}
    onPress={onPress}
    disabled={!onPress}
    activeOpacity={onPress ? theme.interaction.activeOpacity : 1}
  >
    <Text variant="body">{label}</Text>
    <View style={styles.settingRight}>
      {value && (
        <Text variant="body" color={theme.colors.text.secondary} style={styles.settingValue}>
          {value}
        </Text>
      )}
      {onPress && <ChevronRight size={20} color={theme.colors.text.tertiary} />}
    </View>
  </TouchableOpacity>
);

const styles = StyleSheet.create({
  scrollContent: {
    padding: theme.spacing[4],
    paddingBottom: theme.spacing[8],
  },
  card: {
    marginTop: theme.spacing[4],
  },
  sectionTitle: {
    marginBottom: theme.spacing[4],
  },
  settingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: theme.spacing[4],
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  settingItemLast: {
    borderBottomWidth: 0,
  },
  settingRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  settingValue: {
    marginRight: theme.spacing[2],
  },
  toggleTextContainer: {
    flex: 1,
    marginRight: theme.spacing[3],
  },
  toggleDescription: {
    marginTop: theme.spacing[1],
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: theme.spacing[4],
  },
  loadingText: {
    marginLeft: theme.spacing[2],
  },
  footer: {
    marginTop: theme.spacing[8],
    marginBottom: theme.spacing[4],
  },
  footerSubtext: {
    marginTop: theme.spacing[1],
  },
});

/**
 * Settings Screen
 *
 * App settings and preferences used by both students and faculty.
 * Implements:
 * - Notification preference toggles (persisted locally)
 * - Theme display (read-only for now)
 * - Password change navigation
 * - About section with real app version
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Linking,
  Platform,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { ChevronRight, Info } from 'lucide-react-native';
import { theme, config } from '../../constants';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Divider } from '../../components/ui';

/** Keys for persisted notification preferences */
const PREF_KEYS = {
  NOTIF_ATTENDANCE: '@iams/pref_notif_attendance',
  NOTIF_ALERTS: '@iams/pref_notif_alerts',
  NOTIF_SCHEDULE: '@iams/pref_notif_schedule',
} as const;

export const SettingsScreen: React.FC = () => {
  const navigation = useNavigation();

  // Notification preferences (defaults to true)
  const [attendanceNotifs, setAttendanceNotifs] = useState(true);
  const [alertNotifs, setAlertNotifs] = useState(true);
  const [scheduleNotifs, setScheduleNotifs] = useState(true);

  // Load saved preferences on mount
  useEffect(() => {
    const loadPreferences = async () => {
      try {
        // SecureStore only stores strings, so we check for 'false'
        const SecureStore = await import('expo-secure-store');

        const attVal = await SecureStore.getItemAsync(PREF_KEYS.NOTIF_ATTENDANCE);
        if (attVal !== null) setAttendanceNotifs(attVal !== 'false');

        const alertVal = await SecureStore.getItemAsync(PREF_KEYS.NOTIF_ALERTS);
        if (alertVal !== null) setAlertNotifs(alertVal !== 'false');

        const schedVal = await SecureStore.getItemAsync(PREF_KEYS.NOTIF_SCHEDULE);
        if (schedVal !== null) setScheduleNotifs(schedVal !== 'false');
      } catch (err) {
        // Silently fail -- defaults are fine
        console.error('Failed to load preferences:', err);
      }
    };

    loadPreferences();
  }, []);

  // Persist a preference toggle
  const togglePreference = async (
    key: string,
    value: boolean,
    setter: (v: boolean) => void
  ) => {
    setter(value);
    try {
      const SecureStore = await import('expo-secure-store');
      await SecureStore.setItemAsync(key, value.toString());
    } catch (err) {
      console.error('Failed to save preference:', err);
    }
  };

  return (
    <ScreenLayout safeArea padded={false}>
      <Header showBack title="Settings" />

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Notification Settings */}
        <Card>
          <Text variant="h4" weight="600" style={styles.sectionTitle}>
            Notifications
          </Text>

          <ToggleItem
            label="Attendance Updates"
            description="Get notified when your attendance is recorded"
            value={attendanceNotifs}
            onToggle={(v) =>
              togglePreference(PREF_KEYS.NOTIF_ATTENDANCE, v, setAttendanceNotifs)
            }
          />

          <ToggleItem
            label="Early Leave Alerts"
            description="Receive alerts about early leave detections"
            value={alertNotifs}
            onToggle={(v) =>
              togglePreference(PREF_KEYS.NOTIF_ALERTS, v, setAlertNotifs)
            }
          />

          <ToggleItem
            label="Schedule Reminders"
            description="Get reminders before classes start"
            value={scheduleNotifs}
            onToggle={(v) =>
              togglePreference(PREF_KEYS.NOTIF_SCHEDULE, v, setScheduleNotifs)
            }
            isLast
          />
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
              // Link to privacy policy once available
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
  isLast?: boolean;
}> = ({ label, description, value, onToggle, isLast = false }) => (
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
  footer: {
    marginTop: theme.spacing[8],
    marginBottom: theme.spacing[4],
  },
  footerSubtext: {
    marginTop: theme.spacing[1],
  },
});

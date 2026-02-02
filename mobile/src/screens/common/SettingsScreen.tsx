/**
 * Settings Screen
 *
 * App settings and preferences
 * Used by both students and faculty
 */

import React from 'react';
import { View, StyleSheet, ScrollView, TouchableOpacity, Alert } from 'react-native';
import { ChevronRight } from 'lucide-react-native';
import { theme } from '../../constants';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card } from '../../components/ui';

export const SettingsScreen: React.FC = () => {
  const handlePress = (option: string) => {
    Alert.alert(option, 'Feature coming soon');
  };

  return (
    <ScreenLayout safeArea scrollable>
      <Header showBack title="Settings" />

      <View style={styles.container}>
        {/* App Settings */}
        <Card>
          <Text variant="h4" weight="semibold" style={styles.sectionTitle}>
            App Settings
          </Text>

          <SettingItem label="Notifications" onPress={() => handlePress('Notifications')} />
          <SettingItem label="Language" value="English" onPress={() => handlePress('Language')} />
          <SettingItem label="Theme" value="Light" onPress={() => handlePress('Theme')} />
        </Card>

        {/* Privacy & Security */}
        <Card style={styles.card}>
          <Text variant="h4" weight="semibold" style={styles.sectionTitle}>
            Privacy & Security
          </Text>

          <SettingItem label="Change Password" onPress={() => handlePress('Change Password')} />
          <SettingItem label="Privacy Policy" onPress={() => handlePress('Privacy Policy')} />
          <SettingItem label="Terms of Service" onPress={() => handlePress('Terms of Service')} />
        </Card>

        {/* About */}
        <Card style={styles.card}>
          <Text variant="h4" weight="semibold" style={styles.sectionTitle}>
            About
          </Text>

          <SettingItem label="App Version" value="1.0.0" />
          <SettingItem label="Help & Support" onPress={() => handlePress('Help & Support')} />
        </Card>
      </View>
    </ScreenLayout>
  );
};

const SettingItem: React.FC<{
  label: string;
  value?: string;
  onPress?: () => void;
}> = ({ label, value, onPress }) => (
  <TouchableOpacity
    style={styles.settingItem}
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
  container: {
    padding: theme.spacing[4],
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
  settingRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  settingValue: {
    marginRight: theme.spacing[2],
  },
});

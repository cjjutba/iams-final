/**
 * Student Profile Screen
 *
 * Shows student information and profile actions:
 * - Avatar with initials and basic info
 * - Student details (email, phone, role)
 * - Action menu (Edit Profile, Re-register Face, Notifications, Settings)
 * - Sign out with confirmation
 */

import React, { useState, useCallback } from 'react';
import { View, StyleSheet, ScrollView, TouchableOpacity, Alert, RefreshControl } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import {
  ChevronRight,
  User,
  Camera,
  Bell,
  Settings as SettingsIcon,
  LogOut,
} from 'lucide-react-native';
import { useAuth } from '../../hooks';
import { theme, strings } from '../../constants';
import { capitalize } from '../../utils';
import type { StudentStackParamList } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Avatar, Card, Divider, Button } from '../../components/ui';

type StudentProfileNavigationProp = StackNavigationProp<StudentStackParamList, 'StudentTabs'>;

export const StudentProfileScreen: React.FC = () => {
  const navigation = useNavigation<StudentProfileNavigationProp>();
  const { user, logout, refreshUser } = useAuth();
  const [isRefreshing, setIsRefreshing] = useState(false);

  // ---------- refresh handler ----------

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await refreshUser();
    } catch (error) {
      console.error('Failed to refresh user data:', error);
    } finally {
      setIsRefreshing(false);
    }
  }, [refreshUser]);

  // ---------- navigation handlers ----------

  const handleEditProfile = () => {
    navigation.navigate('EditProfile');
  };

  const handleReregisterFace = () => {
    navigation.navigate('FaceRegister', { mode: 'reregister' });
  };

  const handleNotifications = () => {
    navigation.navigate('Notifications');
  };

  const handleSettings = () => {
    navigation.navigate('Settings');
  };

  const handleSignOut = () => {
    Alert.alert(
      'Sign Out',
      'Are you sure you want to sign out?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Sign Out',
          style: 'destructive',
          onPress: async () => {
            await logout();
          },
        },
      ]
    );
  };

  // ---------- guard ----------

  if (!user) return null;

  // ---------- render ----------

  return (
    <ScreenLayout safeArea padded={false}>
      <Header title={strings.student.profile} />

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
        {/* Profile header */}
        <View style={styles.profileHeader}>
          <View style={styles.avatar}>
            <Avatar
              firstName={user.first_name}
              lastName={user.last_name}
              size="xl"
            />
          </View>

          <Text variant="h2" weight="700" align="center" style={styles.name}>
            {user.first_name} {user.last_name}
          </Text>

          {user.student_id && (
            <Text variant="body" color={theme.colors.text.secondary} align="center">
              {user.student_id}
            </Text>
          )}
        </View>

        {/* User info card */}
        <Card style={styles.card}>
          <InfoRow label={strings.form.email} value={user.email} />
          {user.phone && <InfoRow label={strings.form.phone} value={user.phone} />}
          <InfoRow label="Role" value={capitalize(user.role)} />
        </Card>

        <Divider spacing={6} />

        {/* Actions */}
        <View style={styles.actionsContainer}>
          <ActionItem
            icon={<User size={20} color={theme.colors.text.secondary} />}
            label={strings.student.editProfile}
            onPress={handleEditProfile}
          />

          <ActionItem
            icon={<Camera size={20} color={theme.colors.text.secondary} />}
            label={strings.student.reregisterFace}
            onPress={handleReregisterFace}
          />

          <ActionItem
            icon={<Bell size={20} color={theme.colors.text.secondary} />}
            label={strings.student.notifications}
            onPress={handleNotifications}
          />

          <ActionItem
            icon={<SettingsIcon size={20} color={theme.colors.text.secondary} />}
            label={strings.student.settings}
            onPress={handleSettings}
          />
        </View>

        <Divider spacing={6} />

        {/* Sign out */}
        <View style={styles.signOutContainer}>
          <Button
            variant="outline"
            size="lg"
            fullWidth
            onPress={handleSignOut}
            leftIcon={<LogOut size={20} color={theme.colors.error} />}
          >
            <Text variant="button" color={theme.colors.error}>
              {strings.student.signOut}
            </Text>
          </Button>
        </View>
      </ScrollView>
    </ScreenLayout>
  );
};

// ---------- sub-components ----------

/** Single row of label + value in the info card */
const InfoRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <View style={styles.infoRow}>
    <Text variant="bodySmall" color={theme.colors.text.tertiary}>
      {label}
    </Text>
    <Text variant="body" weight="500">
      {value}
    </Text>
  </View>
);

/** Pressable action row with icon, label, and chevron */
const ActionItem: React.FC<{
  icon: React.ReactNode;
  label: string;
  onPress: () => void;
}> = ({ icon, label, onPress }) => (
  <TouchableOpacity
    style={styles.actionItem}
    onPress={onPress}
    activeOpacity={theme.interaction.activeOpacity}
  >
    <View style={styles.actionLeft}>
      {icon}
      <Text variant="body" style={styles.actionLabel}>
        {label}
      </Text>
    </View>
    <ChevronRight size={20} color={theme.colors.text.tertiary} />
  </TouchableOpacity>
);

const styles = StyleSheet.create({
  scrollContent: {
    paddingHorizontal: theme.spacing[4],
    paddingTop: theme.spacing[6],
    paddingBottom: theme.spacing[8],
  },
  profileHeader: {
    alignItems: 'center',
    marginBottom: theme.spacing[8],
  },
  avatar: {
    marginBottom: theme.spacing[4],
  },
  name: {
    marginBottom: theme.spacing[2],
  },
  card: {
    marginBottom: theme.spacing[6],
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing[3],
  },
  actionsContainer: {
    marginBottom: theme.spacing[6],
  },
  actionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: theme.spacing[4],
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  actionLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  actionLabel: {
    marginLeft: theme.spacing[3],
  },
  signOutContainer: {
    marginBottom: theme.spacing[6],
  },
});

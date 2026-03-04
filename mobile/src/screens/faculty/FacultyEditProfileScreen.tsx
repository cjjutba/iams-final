/**
 * Faculty Edit Profile Screen
 *
 * Allows faculty to update their profile (email, phone)
 * and change their password. Uses real API calls via authService.
 * Follows the same pattern as StudentEditProfileScreen.
 */

import React, { useState, useCallback } from 'react';
import { View, StyleSheet, Alert, RefreshControl } from 'react-native';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Mail, Phone, Lock } from 'lucide-react-native';
import { useAuth } from '../../hooks';
import { authService } from '../../services';
import { theme, strings } from '../../constants';
import { ScreenLayout, Header } from '../../components/layouts';
import { Button, Divider } from '../../components/ui';
import { FormInput, FormPassword } from '../../components/forms';

// Profile update schema
const profileSchema = z.object({
  email: z.string().min(1, strings.errors.required).email(strings.errors.invalidEmail),
  phone: z
    .string()
    .regex(/^09\d{9}$/, strings.errors.invalidPhone)
    .or(z.literal(''))
    .optional(),
});

// Password change schema
const passwordSchema = z
  .object({
    currentPassword: z.string().min(1, strings.errors.required),
    newPassword: z.string().min(1, strings.errors.required).min(8, strings.errors.passwordMin),
    confirmPassword: z.string().min(1, strings.errors.required),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: strings.errors.passwordMismatch,
    path: ['confirmPassword'],
  });

type ProfileData = z.infer<typeof profileSchema>;
type PasswordData = z.infer<typeof passwordSchema>;

export const FacultyEditProfileScreen: React.FC = () => {
  const { user, refreshUser } = useAuth();

  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

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

  const {
    control: profileControl,
    handleSubmit: handleProfileSubmit,
    formState: { isDirty: isProfileDirty },
  } = useForm<ProfileData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      email: user?.email || '',
      phone: user?.phone || '',
    },
  });

  const {
    control: passwordControl,
    handleSubmit: handlePasswordSubmit,
    reset: resetPasswordForm,
  } = useForm<PasswordData>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
    },
  });

  const onSaveProfile = async (data: ProfileData) => {
    try {
      setIsSavingProfile(true);
      await authService.updateProfile(user!.id, {
        email: data.email,
        phone: data.phone || undefined,
      });

      Alert.alert('Success', 'Profile updated successfully');
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string } } };
      Alert.alert('Error', err.response?.data?.message || strings.errors.generic);
    } finally {
      setIsSavingProfile(false);
    }
  };

  const onChangePassword = async (data: PasswordData) => {
    try {
      setIsChangingPassword(true);
      await authService.changePassword(data.currentPassword, data.newPassword);

      resetPasswordForm();
      Alert.alert('Success', 'Password changed successfully');
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string } } };
      Alert.alert('Error', err.response?.data?.message || strings.errors.generic);
    } finally {
      setIsChangingPassword(false);
    }
  };

  return (
    <ScreenLayout
      safeArea
      scrollable
      keyboardAvoiding
      refreshControl={
        <RefreshControl
          refreshing={isRefreshing}
          onRefresh={handleRefresh}
          colors={[theme.colors.primary]}
          tintColor={theme.colors.primary}
        />
      }
    >
      <Header showBack title={strings.student.editProfile} />

      <View style={styles.container}>
        {/* Profile section */}
        <View style={styles.section}>
          <FormInput
            name="email"
            control={profileControl}
            label={strings.form.email}
            placeholder="your.email@example.com"
            leftIcon={<Mail size={20} color={theme.colors.text.tertiary} />}
            keyboardType="email-address"
            autoCapitalize="none"
          />

          <FormInput
            name="phone"
            control={profileControl}
            label={strings.form.phone}
            placeholder="09XXXXXXXXX"
            leftIcon={<Phone size={20} color={theme.colors.text.tertiary} />}
            keyboardType="phone-pad"
          />

          <Button
            variant="primary"
            size="lg"
            fullWidth
            onPress={handleProfileSubmit(onSaveProfile)}
            loading={isSavingProfile}
            disabled={!isProfileDirty}
          >
            {strings.common.save}
          </Button>
        </View>

        <Divider spacing={6} />

        {/* Password section */}
        <View style={styles.section}>
          <FormPassword
            name="currentPassword"
            control={passwordControl}
            label={strings.form.currentPassword}
            placeholder={strings.form.currentPassword}
            leftIcon={<Lock size={20} color={theme.colors.text.tertiary} />}
          />

          <FormPassword
            name="newPassword"
            control={passwordControl}
            label={strings.form.newPassword}
            placeholder={strings.form.newPassword}
            leftIcon={<Lock size={20} color={theme.colors.text.tertiary} />}
          />

          <FormPassword
            name="confirmPassword"
            control={passwordControl}
            label={strings.form.confirmPassword}
            placeholder={strings.form.confirmPassword}
            leftIcon={<Lock size={20} color={theme.colors.text.tertiary} />}
          />

          <Button
            variant="secondary"
            size="lg"
            fullWidth
            onPress={handlePasswordSubmit(onChangePassword)}
            loading={isChangingPassword}
          >
            {strings.student.changePassword}
          </Button>
        </View>
      </View>
    </ScreenLayout>
  );
};

const styles = StyleSheet.create({
  container: {
    padding: theme.spacing[4],
  },
  section: {
    marginBottom: theme.spacing[6],
  },
});

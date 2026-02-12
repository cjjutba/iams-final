/**
 * Reset Password Screen
 *
 * Handles the deep link from password reset emails (Supabase Auth).
 * Allows the user to set a new password after clicking the reset link.
 * Deep link format: iams://reset-password
 */

import React, { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Lock, CheckCircle } from 'lucide-react-native';
import { useNavigation } from '@react-navigation/native';
import { authService } from '../../services';
import { theme, strings } from '../../constants';
import { AuthLayout } from '../../components/layouts';
import { Text, Button } from '../../components/ui';
import { FormInput } from '../../components/forms';

const resetPasswordSchema = z
  .object({
    password: z.string().min(8, strings.errors.passwordMin),
    confirmPassword: z.string().min(1, strings.errors.required),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: strings.errors.passwordMismatch,
    path: ['confirmPassword'],
  });

type ResetPasswordData = z.infer<typeof resetPasswordSchema>;

export const ResetPasswordScreen: React.FC = () => {
  const navigation = useNavigation();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { control, handleSubmit } = useForm<ResetPasswordData>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: {
      password: '',
      confirmPassword: '',
    },
  });

  const onSubmit = async (data: ResetPasswordData) => {
    try {
      setIsSubmitting(true);
      setError(null);
      await authService.resetPassword(data.password);
      setIsSuccess(true);
    } catch (err: any) {
      setError(err.message || strings.errors.generic);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoToLogin = () => {
    navigation.navigate('Welcome' as never);
  };

  if (isSuccess) {
    return (
      <AuthLayout
        showBack
        title="Password Updated"
        subtitle="Your password has been changed successfully"
      >
        <View style={styles.successSection}>
          <CheckCircle size={56} color={theme.colors.success} />
          <Text variant="h3" weight="600" align="center" style={styles.successTitle}>
            Password Reset Complete
          </Text>
          <Text variant="body" color={theme.colors.text.secondary} align="center" style={styles.successMessage}>
            Your password has been updated. You can now sign in with your new password.
          </Text>
          <Button
            variant="primary"
            size="lg"
            fullWidth
            onPress={handleGoToLogin}
            style={styles.loginButton}
          >
            Go to Login
          </Button>
        </View>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      showBack
      title="Set New Password"
      subtitle="Choose a strong password for your account"
    >
      <View style={styles.formSection}>
        <View style={styles.inputContainer}>
          <FormInput
            name="password"
            control={control}
            label={strings.form.newPassword}
            placeholder="Enter new password"
            leftIcon={<Lock size={20} color={theme.colors.text.tertiary} />}
            secureTextEntry
          />
        </View>

        <View style={styles.inputContainer}>
          <FormInput
            name="confirmPassword"
            control={control}
            label={strings.form.confirmPassword}
            placeholder="Confirm new password"
            leftIcon={<Lock size={20} color={theme.colors.text.tertiary} />}
            secureTextEntry
          />
        </View>

        {error ? (
          <View style={styles.errorContainer}>
            <Text variant="bodySmall" color={theme.colors.error}>
              {error}
            </Text>
          </View>
        ) : null}

        <Button
          variant="primary"
          size="lg"
          fullWidth
          onPress={handleSubmit(onSubmit)}
          loading={isSubmitting}
          style={styles.submitButton}
        >
          Reset Password
        </Button>
      </View>
    </AuthLayout>
  );
};

const styles = StyleSheet.create({
  formSection: {
    marginTop: theme.spacing[8],
  },
  inputContainer: {
    marginBottom: theme.spacing[5],
  },
  errorContainer: {
    marginBottom: theme.spacing[5],
    padding: theme.spacing[4],
    backgroundColor: theme.colors.errorLight,
    borderRadius: theme.borderRadius.md,
  },
  submitButton: {
    marginTop: theme.spacing[2],
  },
  successSection: {
    marginTop: theme.spacing[8],
    alignItems: 'center',
    paddingHorizontal: theme.spacing[2],
  },
  successTitle: {
    marginTop: theme.spacing[6],
    marginBottom: theme.spacing[4],
  },
  successMessage: {
    lineHeight: 24,
    marginBottom: theme.spacing[6],
  },
  loginButton: {
    marginTop: theme.spacing[2],
  },
});

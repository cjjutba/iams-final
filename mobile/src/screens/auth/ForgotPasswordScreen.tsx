/**
 * Forgot Password Screen
 *
 * Allows users to request password reset via email
 */

import React, { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Mail, CheckCircle } from 'lucide-react-native';
import { authService } from '../../services';
import { theme, strings } from '../../constants';
import { AuthLayout } from '../../components/layouts';
import { Text, Button, Card } from '../../components/ui';
import { FormInput } from '../../components/forms';

// Validation schema
const forgotPasswordSchema = z.object({
  email: z.string().min(1, strings.errors.required).email(strings.errors.invalidEmail),
});

type ForgotPasswordData = z.infer<typeof forgotPasswordSchema>;

export const ForgotPasswordScreen: React.FC = () => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { control, handleSubmit } = useForm<ForgotPasswordData>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: {
      email: '',
    },
  });

  const onSubmit = async (data: ForgotPasswordData) => {
    try {
      setIsSubmitting(true);
      setError(null);

      await authService.requestPasswordReset(data.email);
      setIsSubmitted(true);
    } catch (err: any) {
      setError(err.response?.data?.message || strings.errors.generic);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSubmitted) {
    return (
      <AuthLayout showBack title={strings.auth.resetPassword}>
        <View style={styles.successContainer}>
          <View style={styles.iconContainer}>
            <CheckCircle size={64} color={theme.colors.status.success} />
          </View>

          <Text variant="h3" weight="semibold" align="center" style={styles.successTitle}>
            {strings.auth.resetEmailSent}
          </Text>

          <Text variant="body" color={theme.colors.text.secondary} align="center" style={styles.successMessage}>
            We've sent password reset instructions to your email. Please check your inbox and follow
            the link to reset your password.
          </Text>

          <Card variant="outlined" style={styles.infoCard}>
            <Text variant="bodySmall" color={theme.colors.text.secondary} align="center">
              Didn't receive the email? Check your spam folder or try again in a few minutes.
            </Text>
          </Card>
        </View>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      showBack
      title={strings.auth.resetPassword}
      subtitle={strings.auth.resetInstructions}
    >
      <View style={styles.form}>
        {/* Email Input */}
        <FormInput
          name="email"
          control={control}
          label={strings.form.email}
          placeholder="your.email@example.com"
          leftIcon={<Mail size={20} color={theme.colors.text.tertiary} />}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
        />

        {/* Error Message */}
        {error && (
          <View style={styles.errorContainer}>
            <Text variant="bodySmall" color={theme.colors.status.error}>
              {error}
            </Text>
          </View>
        )}

        {/* Submit Button */}
        <Button
          variant="primary"
          size="lg"
          fullWidth
          onPress={handleSubmit(onSubmit)}
          loading={isSubmitting}
          style={styles.submitButton}
        >
          {strings.auth.sendResetLink}
        </Button>
      </View>
    </AuthLayout>
  );
};

const styles = StyleSheet.create({
  form: {
    flex: 1,
  },
  errorContainer: {
    marginTop: theme.spacing[4],
    padding: theme.spacing[4],
    backgroundColor: theme.colors.status.errorLight,
    borderRadius: theme.borderRadius.md,
  },
  submitButton: {
    marginTop: theme.spacing[8],
  },
  successContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: theme.spacing[8],
  },
  iconContainer: {
    marginBottom: theme.spacing[6],
  },
  successTitle: {
    marginBottom: theme.spacing[4],
  },
  successMessage: {
    marginBottom: theme.spacing[8],
    lineHeight: 24,
  },
  infoCard: {
    width: '100%',
  },
});

/**
 * Forgot Password Screen
 *
 * Allows users to request password reset via email.
 */

import React, { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Mail, CheckCircle } from 'lucide-react-native';
import { authService } from '../../services';
import { useToast } from '../../hooks';
import { theme, strings } from '../../constants';
import { AuthLayout } from '../../components/layouts';
import { Text, Button } from '../../components/ui';
import { FormInput } from '../../components/forms';

const forgotPasswordSchema = z.object({
  email: z.string().min(1, strings.errors.required).email(strings.errors.invalidEmail),
});

type ForgotPasswordData = z.infer<typeof forgotPasswordSchema>;

export const ForgotPasswordScreen: React.FC = () => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const { showError } = useToast();

  const { control, handleSubmit } = useForm<ForgotPasswordData>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: {
      email: '',
    },
  });

  const onSubmit = async (data: ForgotPasswordData) => {
    try {
      setIsSubmitting(true);
      await authService.forgotPassword(data.email);
      setIsSubmitted(true);
    } catch (err: any) {
      showError(err.response?.data?.message || strings.errors.generic, 'Reset Failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSubmitted) {
    return (
      <AuthLayout showBack title={strings.auth.resetPassword} subtitle={strings.auth.resetInstructions}>
        <View style={styles.successSection}>
          <CheckCircle size={56} color={theme.colors.success} />
          <Text variant="h3" weight="600" align="center" style={styles.successTitle}>
            {strings.auth.resetEmailSent}
          </Text>
          <Text variant="body" color={theme.colors.text.secondary} align="center" style={styles.successMessage}>
            We sent password reset instructions to your email. Follow the link in your inbox to continue.
          </Text>
          <Text variant="bodySmall" color={theme.colors.text.tertiary} align="center" style={styles.successHint}>
            If you do not see the email, check spam or try again after a few minutes.
          </Text>
        </View>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout showBack title={strings.auth.resetPassword} subtitle={strings.auth.resetInstructions}>
      <View style={styles.formSection}>
        <View style={styles.inputContainer}>
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
        </View>

        <Button
          variant="primary"
          size="lg"
          fullWidth
          onPress={handleSubmit(onSubmit, (formErrors) => {
            const firstError = Object.values(formErrors)[0]?.message;
            if (firstError) showError(firstError, 'Validation Error');
          })}
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
  formSection: {
    marginTop: theme.spacing[8],
  },
  inputContainer: {
    marginBottom: theme.spacing[5],
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
    marginBottom: theme.spacing[2],
  },
  successHint: {
    marginTop: theme.spacing[5],
    lineHeight: 20,
  },
});

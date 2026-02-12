/**
 * Faculty Login Screen
 *
 * Login form for faculty using Email + Password.
 * Features:
 * - Input validation with Zod schema
 * - Toast notifications for errors
 * - Input sanitization (trim whitespace, lowercase email)
 * - User-friendly error messages
 */

import React, { useState, useEffect, useCallback } from 'react';
import { View, StyleSheet } from 'react-native';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Mail, Lock } from 'lucide-react-native';
import { useAuth } from '../../hooks';
import { useToast } from '../../hooks/useToast';
import { theme, strings } from '../../constants';
import { AuthLayout } from '../../components/layouts';
import { Text, Button } from '../../components/ui';
import { FormInput, FormPassword } from '../../components/forms';

const facultyLoginSchema = z.object({
  email: z.string().min(1, strings.errors.required).email(strings.errors.invalidEmail),
  password: z.string().min(1, strings.errors.required),
});

type FacultyLoginData = z.infer<typeof facultyLoginSchema>;

export const FacultyLoginScreen: React.FC = () => {
  const { login, error: authError, clearError } = useAuth();
  const { showError } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { control, handleSubmit } = useForm<FacultyLoginData>({
    resolver: zodResolver(facultyLoginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  /**
   * Convert technical error messages to user-friendly ones
   */
  const getUserFriendlyErrorMessage = useCallback((error: string): string => {
    // Error messages from authService are already user-friendly, so return them directly
    return error;
  }, []);

  // Show toast notification when auth error changes
  useEffect(() => {
    if (authError && !isSubmitting) {
      showError(getUserFriendlyErrorMessage(authError), 'Login Failed');
    }
  }, [authError, isSubmitting, showError, getUserFriendlyErrorMessage]);

  const onSubmit = async (data: FacultyLoginData) => {
    try {
      setIsSubmitting(true);
      clearError();

      // Sanitize inputs (trim whitespace, lowercase email)
      const sanitizedEmail = data.email.trim().toLowerCase();
      const sanitizedPassword = data.password.trim();

      // Validate after sanitization
      if (!sanitizedEmail || !sanitizedPassword) {
        showError('Please enter both email and password', 'Missing Information');
        return;
      }

      // Additional email format validation
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(sanitizedEmail)) {
        showError('Please enter a valid email address', 'Invalid Email');
        return;
      }

      await login({ email: sanitizedEmail, password: sanitizedPassword });
      // Success - navigation is handled by RootNavigator based on auth state
    } catch (err: any) {
      console.error('Login error:', err);
      // Error toast is shown via useEffect hook above
      // Don't navigate away - stay on login screen
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout showBack title={strings.auth.welcomeFaculty} subtitle={strings.auth.signInToContinue}>
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

        <View style={styles.inputContainer}>
          <FormPassword
            name="password"
            control={control}
            label={strings.form.password}
            placeholder={strings.form.password}
            leftIcon={<Lock size={20} color={theme.colors.text.tertiary} />}
            autoCapitalize="none"
            autoCorrect={false}
          />
        </View>

        {authError ? (
          <View style={styles.errorContainer}>
            <Text variant="bodySmall" color={theme.colors.error}>
              {authError}
            </Text>
          </View>
        ) : null}

        <Button
          variant="primary"
          size="lg"
          fullWidth
          onPress={handleSubmit(onSubmit)}
          loading={isSubmitting}
          style={styles.loginButton}
        >
          {strings.auth.signIn}
        </Button>
      </View>

      <View style={styles.notice}>
        <Text variant="bodySmall" color={theme.colors.text.secondary} align="center">
          {strings.auth.facultyNotice}
        </Text>
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
  loginButton: {
    marginTop: theme.spacing[2],
  },
  notice: {
    marginTop: theme.spacing[8],
    paddingHorizontal: theme.spacing[2],
  },
});

/**
 * Student Login Screen
 *
 * Login form for students using Student ID + Password.
 * Features:
 * - Input validation with Zod schema
 * - Toast notifications for errors
 * - Input sanitization (trim whitespace)
 * - User-friendly error messages
 */

import React, { useState, useEffect, useCallback } from 'react';
import { View, StyleSheet, TouchableOpacity } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { IdCard, Lock } from 'lucide-react-native';
import type { AuthStackParamList } from '../../types';
import { studentLoginSchema, type StudentLoginFormData } from '../../utils/validators';
import { useAuthStore } from '../../stores';
import { useToast } from '../../hooks/useToast';
import { theme, strings } from '../../constants';
import { AuthLayout } from '../../components/layouts';
import { Text, Button, Input } from '../../components/ui';

type StudentLoginScreenNavigationProp = StackNavigationProp<AuthStackParamList, 'StudentLogin'>;

export const StudentLoginScreen: React.FC = () => {
  const navigation = useNavigation<StudentLoginScreenNavigationProp>();
  const { login, error: authError, clearError } = useAuthStore();
  const { showError } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    control,
    handleSubmit,
  } = useForm<StudentLoginFormData>({
    resolver: zodResolver(studentLoginSchema),
    defaultValues: {
      student_id: '',
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

  const onSubmit = async (data: StudentLoginFormData) => {
    try {
      setIsSubmitting(true);
      clearError();

      // Sanitize inputs (trim whitespace)
      const sanitizedStudentId = data.student_id.trim().toUpperCase();
      const sanitizedPassword = data.password.trim();

      // Validate after sanitization
      if (!sanitizedStudentId || !sanitizedPassword) {
        showError('Please enter both Student ID and password', 'Missing Information');
        return;
      }

      await login({ email: sanitizedStudentId, password: sanitizedPassword });
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
    <AuthLayout showBack title="Student Login" subtitle={strings.auth.signInToContinue}>
      <View style={styles.formSection}>
        <View style={styles.inputContainer}>
          <Controller
            control={control}
            name="student_id"
            render={({ field: { onChange, onBlur, value } }) => (
              <Input
                label={strings.form.studentId}
                placeholder={strings.register.studentIdPlaceholder}
                value={value}
                onChangeText={onChange}
                onBlur={onBlur}
                leftIcon={<IdCard size={20} color={theme.colors.text.tertiary} />}
                autoCapitalize="characters"
                autoCorrect={false}
              />
            )}
          />
        </View>

        <View style={styles.inputContainer}>
          <Controller
            control={control}
            name="password"
            render={({ field: { onChange, onBlur, value } }) => (
              <Input
                label={strings.form.password}
                placeholder="Enter your password"
                value={value}
                onChangeText={onChange}
                onBlur={onBlur}
                leftIcon={<Lock size={20} color={theme.colors.text.tertiary} />}
                isPassword
                autoCapitalize="none"
                autoCorrect={false}
              />
            )}
          />
        </View>

        <TouchableOpacity onPress={() => navigation.navigate('ForgotPassword')} style={styles.forgotPassword}>
          <Text variant="bodySmall" color={theme.colors.primary} weight="600">
            {strings.auth.forgotPassword}
          </Text>
        </TouchableOpacity>

        <Button
          variant="primary"
          size="lg"
          fullWidth
          onPress={handleSubmit(onSubmit, (formErrors) => {
            const firstError = Object.values(formErrors)[0]?.message;
            if (firstError) showError(firstError, 'Validation Error');
          })}
          loading={isSubmitting}
          style={styles.loginButton}
        >
          Login
        </Button>
      </View>

      <View style={styles.registerContainer}>
        <Text variant="body" color={theme.colors.text.secondary}>
          {strings.auth.noAccount}{' '}
        </Text>
        <TouchableOpacity onPress={() => navigation.navigate('RegisterStep1')}>
          <Text variant="body" color={theme.colors.primary} weight="600">
            Register
          </Text>
        </TouchableOpacity>
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
  forgotPassword: {
    alignSelf: 'flex-end',
    marginTop: theme.spacing[2],
    marginBottom: theme.spacing[6],
  },
  loginButton: {
    marginTop: theme.spacing[2],
  },
  registerContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: theme.spacing[8],
  },
});

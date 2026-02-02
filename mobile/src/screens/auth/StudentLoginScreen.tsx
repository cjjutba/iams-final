/**
 * Student Login Screen
 *
 * Login form for students using Student ID + Password
 * Uses React Hook Form with Zod validation
 * Integrates with authStore for authentication
 */

import React, { useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  TouchableOpacity,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import type { AuthStackParamList } from '../../types';
import { studentLoginSchema, type StudentLoginData } from '../../utils/validators';
import { useAuthStore } from '../../stores';
import { theme } from '../../constants';
import { Text, Button, Input } from '../../components/ui';

type StudentLoginScreenNavigationProp = StackNavigationProp<AuthStackParamList, 'StudentLogin'>;

export const StudentLoginScreen: React.FC = () => {
  const navigation = useNavigation<StudentLoginScreenNavigationProp>();
  const { login, error: authError, clearError } = useAuthStore();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<StudentLoginData>({
    resolver: zodResolver(studentLoginSchema),
    defaultValues: {
      student_id: '',
      password: '',
    },
  });

  const onSubmit = async (data: StudentLoginData) => {
    try {
      setIsSubmitting(true);
      clearError();
      await login({ ...data, role: 'student' });
      // Navigation is handled by RootNavigator when auth state changes
    } catch (err) {
      // Error is handled by authStore
      console.error('Login error:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegisterPress = () => {
    navigation.navigate('RegisterStep1');
  };

  const handleForgotPasswordPress = () => {
    navigation.navigate('ForgotPassword');
  };

  const handleBackPress = () => {
    navigation.goBack();
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 20}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={handleBackPress} style={styles.backButton}>
            <Text variant="body" color={theme.colors.primary}>
              ← Back
            </Text>
          </TouchableOpacity>

          <Text variant="h2" weight="bold" style={styles.title}>
            Student Login
          </Text>

          <Text variant="body" color={theme.colors.text.secondary} style={styles.subtitle}>
            Enter your Student ID and password to continue
          </Text>
        </View>

        {/* Form */}
        <View style={styles.form}>
          {/* Student ID Input */}
          <Controller
            control={control}
            name="student_id"
            render={({ field: { onChange, onBlur, value } }) => (
              <Input
                label="Student ID"
                placeholder="YYYY-NNNN (e.g., 2024-0001)"
                value={value}
                onChangeText={onChange}
                onBlur={onBlur}
                error={errors.student_id?.message}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="default"
              />
            )}
          />

          {/* Password Input */}
          <Controller
            control={control}
            name="password"
            render={({ field: { onChange, onBlur, value } }) => (
              <Input
                label="Password"
                placeholder="Enter your password"
                value={value}
                onChangeText={onChange}
                onBlur={onBlur}
                error={errors.password?.message}
                secureTextEntry
                autoCapitalize="none"
                autoCorrect={false}
              />
            )}
          />

          {/* Error Message */}
          {authError && (
            <View style={styles.errorContainer}>
              <Text variant="bodySmall" color={theme.colors.destructive}>
                {authError}
              </Text>
            </View>
          )}

          {/* Forgot Password Link */}
          <TouchableOpacity onPress={handleForgotPasswordPress} style={styles.forgotPassword}>
            <Text variant="bodySmall" color={theme.colors.primary}>
              Forgot Password?
            </Text>
          </TouchableOpacity>

          {/* Login Button */}
          <Button
            variant="primary"
            size="lg"
            fullWidth
            onPress={handleSubmit(onSubmit)}
            loading={isSubmitting}
            style={styles.loginButton}
          >
            Login
          </Button>

          {/* Register Link */}
          <View style={styles.registerContainer}>
            <Text variant="body" color={theme.colors.text.secondary}>
              Don't have an account?{' '}
            </Text>
            <TouchableOpacity onPress={handleRegisterPress}>
              <Text variant="body" color={theme.colors.primary} weight="semibold">
                Register
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: theme.spacing[6],
    paddingTop: theme.spacing[8],
    paddingBottom: theme.spacing[8],
  },
  header: {
    marginBottom: theme.spacing[8],
  },
  backButton: {
    marginBottom: theme.spacing[6],
  },
  title: {
    marginBottom: theme.spacing[3],
  },
  subtitle: {
    lineHeight: 24,
  },
  form: {
    flex: 1,
  },
  errorContainer: {
    marginTop: theme.spacing[4],
    padding: theme.spacing[4],
    backgroundColor: '#FEE2E2',
    borderRadius: theme.borderRadius.md,
  },
  forgotPassword: {
    alignSelf: 'flex-end',
    marginTop: theme.spacing[3],
  },
  loginButton: {
    marginTop: theme.spacing[8],
  },
  registerContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: theme.spacing[6],
  },
});

/**
 * Student Login Screen
 *
 * Login form for students using Student ID + Password.
 */

import React, { useState } from 'react';
import { View, StyleSheet, TouchableOpacity } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { IdCard, Lock } from 'lucide-react-native';
import type { AuthStackParamList } from '../../types';
import { studentLoginSchema, type StudentLoginData } from '../../utils/validators';
import { useAuthStore } from '../../stores';
import { theme, strings } from '../../constants';
import { AuthLayout } from '../../components/layouts';
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
    } catch (err) {
      console.error('Login error:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout showBack title="Student Login" subtitle={strings.auth.signInToContinue}>
      <View style={styles.formSection}>
        <Text variant="caption" color={theme.colors.text.secondary} style={styles.helperText}>
          Use your official student ID format: 21-A-02177
        </Text>

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
              error={errors.student_id?.message}
              leftIcon={<IdCard size={20} color={theme.colors.text.tertiary} />}
              autoCapitalize="characters"
              autoCorrect={false}
            />
          )}
        />

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
              error={errors.password?.message}
              leftIcon={<Lock size={20} color={theme.colors.text.tertiary} />}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
            />
          )}
        />

        <TouchableOpacity onPress={() => navigation.navigate('ForgotPassword')} style={styles.forgotPassword}>
          <Text variant="bodySmall" color={theme.colors.primary}>
            {strings.auth.forgotPassword}
          </Text>
        </TouchableOpacity>

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
    marginTop: theme.spacing[2],
  },
  helperText: {
    marginBottom: theme.spacing[4],
  },
  forgotPassword: {
    alignSelf: 'flex-end',
    marginTop: theme.spacing[1],
    marginBottom: theme.spacing[4],
  },
  errorContainer: {
    marginBottom: theme.spacing[4],
    padding: theme.spacing[4],
    backgroundColor: theme.colors.errorLight,
    borderRadius: theme.borderRadius.md,
  },
  loginButton: {
    marginTop: theme.spacing[1],
  },
  registerContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: theme.spacing[6],
  },
});

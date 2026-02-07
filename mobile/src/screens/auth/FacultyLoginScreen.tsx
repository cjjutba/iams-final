/**
 * Faculty Login Screen
 *
 * Login form for faculty using Email + Password.
 */

import React, { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Mail, Lock } from 'lucide-react-native';
import { useAuth } from '../../hooks';
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
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { control, handleSubmit } = useForm<FacultyLoginData>({
    resolver: zodResolver(facultyLoginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const onSubmit = async (data: FacultyLoginData) => {
    try {
      setIsSubmitting(true);
      clearError();
      await login({ email: data.email, password: data.password });
    } catch (err) {
      console.error('Login error:', err);
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

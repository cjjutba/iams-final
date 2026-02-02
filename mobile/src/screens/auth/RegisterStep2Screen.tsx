/**
 * Register Step 2 Screen - Account Details
 *
 * Second step of student registration
 * Collects email, phone, and password
 */

import React, { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RouteProp } from '@react-navigation/native';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Mail, Phone, Lock } from 'lucide-react-native';
import { theme, strings } from '../../constants';
import type { AuthStackParamList } from '../../types';
import { AuthLayout } from '../../components/layouts';
import { Button } from '../../components/ui';
import { FormInput, FormPassword } from '../../components/forms';

type RegisterStep2NavigationProp = StackNavigationProp<AuthStackParamList, 'RegisterStep2'>;
type RegisterStep2RouteProp = RouteProp<AuthStackParamList, 'RegisterStep2'>;

// Validation schema
const accountDetailsSchema = z
  .object({
    email: z.string().min(1, strings.errors.required).email(strings.errors.invalidEmail),
    phone: z
      .string()
      .min(1, strings.errors.required)
      .regex(/^09\d{9}$/, strings.errors.invalidPhone),
    password: z.string().min(1, strings.errors.required).min(8, strings.errors.passwordMin),
    confirmPassword: z.string().min(1, strings.errors.required),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: strings.errors.passwordMismatch,
    path: ['confirmPassword'],
  });

type AccountDetailsData = z.infer<typeof accountDetailsSchema>;

export const RegisterStep2Screen: React.FC = () => {
  const navigation = useNavigation<RegisterStep2NavigationProp>();
  const route = useRoute<RegisterStep2RouteProp>();

  const { studentInfo } = route.params;

  const { control, handleSubmit } = useForm<AccountDetailsData>({
    resolver: zodResolver(accountDetailsSchema),
    defaultValues: {
      email: studentInfo.email || '',
      phone: '',
      password: '',
      confirmPassword: '',
    },
  });

  const onSubmit = (data: AccountDetailsData) => {
    const accountInfo = {
      email: data.email,
      phone: data.phone,
      password: data.password,
    };

    navigation.navigate('RegisterStep3', { studentInfo, accountInfo });
  };

  return (
    <AuthLayout
      showBack
      title={strings.auth.createAccount}
      subtitle={strings.register.step2Title}
    >
      <View style={styles.container}>
        {/* Progress bar */}
        <View style={styles.progressContainer}>
          <View style={[styles.progressBar, { width: '50%' }]} />
        </View>

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

          {/* Phone Input */}
          <FormInput
            name="phone"
            control={control}
            label={strings.form.phone}
            placeholder="09XXXXXXXXX"
            leftIcon={<Phone size={20} color={theme.colors.text.tertiary} />}
            keyboardType="phone-pad"
          />

          {/* Password Input */}
          <FormPassword
            name="password"
            control={control}
            label={strings.form.password}
            placeholder={strings.form.password}
            leftIcon={<Lock size={20} color={theme.colors.text.tertiary} />}
          />

          {/* Confirm Password Input */}
          <FormPassword
            name="confirmPassword"
            control={control}
            label={strings.form.confirmPassword}
            placeholder={strings.form.confirmPassword}
            leftIcon={<Lock size={20} color={theme.colors.text.tertiary} />}
          />

          {/* Next Button */}
          <Button
            variant="primary"
            size="lg"
            fullWidth
            onPress={handleSubmit(onSubmit)}
            style={styles.button}
          >
            {strings.common.next}
          </Button>
        </View>
      </View>
    </AuthLayout>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  progressContainer: {
    height: 4,
    backgroundColor: theme.colors.backgroundSecondary,
    borderRadius: 2,
    marginBottom: theme.spacing[8],
  },
  progressBar: {
    height: '100%',
    backgroundColor: theme.colors.primary,
    borderRadius: 2,
  },
  form: {
    flex: 1,
  },
  button: {
    marginTop: theme.spacing[8],
  },
});

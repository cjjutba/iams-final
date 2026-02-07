/**
 * Register Step 2 Screen - Account Details
 *
 * Second step of student registration.
 */

import React from 'react';
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
import { Text, Button } from '../../components/ui';
import { FormInput, FormPassword } from '../../components/forms';

type RegisterStep2NavigationProp = StackNavigationProp<AuthStackParamList, 'RegisterStep2'>;
type RegisterStep2RouteProp = RouteProp<AuthStackParamList, 'RegisterStep2'>;

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
    <AuthLayout showBack title={strings.auth.createAccount} subtitle={strings.register.step2Title}>
      <View style={styles.progressSection}>
        <Text variant="caption" color={theme.colors.text.secondary}>
          Step 2 of 4
        </Text>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: '50%' }]} />
        </View>
      </View>

      <View style={styles.section}>
        <Text variant="caption" color={theme.colors.text.secondary} style={styles.helperText}>
          Set your contact details and secure password for your account.
        </Text>

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
          <FormInput
            name="phone"
            control={control}
            label={strings.form.phone}
            placeholder="09XXXXXXXXX"
            leftIcon={<Phone size={20} color={theme.colors.text.tertiary} />}
            keyboardType="phone-pad"
          />
        </View>

        <View style={styles.inputContainer}>
          <FormPassword
            name="password"
            control={control}
            label={strings.form.password}
            placeholder={strings.form.password}
            leftIcon={<Lock size={20} color={theme.colors.text.tertiary} />}
          />
        </View>

        <View style={styles.inputContainer}>
          <FormPassword
            name="confirmPassword"
            control={control}
            label={strings.form.confirmPassword}
            placeholder={strings.form.confirmPassword}
            leftIcon={<Lock size={20} color={theme.colors.text.tertiary} />}
          />
        </View>

        <Button variant="primary" size="lg" fullWidth onPress={handleSubmit(onSubmit)} style={styles.button}>
          {strings.common.next}
        </Button>
      </View>
    </AuthLayout>
  );
};

const styles = StyleSheet.create({
  progressSection: {
    marginTop: theme.spacing[2],
    marginBottom: theme.spacing[5],
    gap: theme.spacing[2],
  },
  progressTrack: {
    height: 6,
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.border,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.primary,
  },
  section: {
    marginTop: theme.spacing[4],
  },
  helperText: {
    marginBottom: theme.spacing[5],
  },
  inputContainer: {
    marginBottom: theme.spacing[5],
  },
  button: {
    marginTop: theme.spacing[2],
  },
});

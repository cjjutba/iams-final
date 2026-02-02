/**
 * Register Step 1 Screen - Student ID Verification
 *
 * First step of student registration
 * Verifies student ID exists in university database
 */

import React, { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { IdCard, CheckCircle } from 'lucide-react-native';
import { useAuth } from '../../hooks';
import { theme, strings } from '../../constants';
import type { AuthStackParamList } from '../../types';
import { AuthLayout } from '../../components/layouts';
import { Text, Button, Card } from '../../components/ui';
import { FormInput } from '../../components/forms';

type RegisterStep1NavigationProp = StackNavigationProp<AuthStackParamList, 'RegisterStep1'>;

// Validation schema
const studentIdSchema = z.object({
  studentId: z
    .string()
    .min(1, strings.errors.required)
    .regex(/^\d{4}-\d{4}$/, strings.errors.invalidStudentId),
});

type StudentIdData = z.infer<typeof studentIdSchema>;

export const RegisterStep1Screen: React.FC = () => {
  const navigation = useNavigation<RegisterStep1NavigationProp>();
  const { verifyStudentId } = useAuth();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [studentInfo, setStudentInfo] = useState<any | null>(null);

  const { control, handleSubmit } = useForm<StudentIdData>({
    resolver: zodResolver(studentIdSchema),
    defaultValues: {
      studentId: '',
    },
  });

  const onSubmit = async (data: StudentIdData) => {
    try {
      setIsSubmitting(true);
      setError(null);

      const response = await verifyStudentId({ student_id: data.studentId });

      if (response.success && response.data.valid) {
        setStudentInfo({ studentId: data.studentId, ...response.data });
      } else {
        setError('Student ID not found in university database');
      }
    } catch (err: any) {
      setError(err.response?.data?.message || strings.errors.generic);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleContinue = () => {
    navigation.navigate('RegisterStep2', { studentInfo });
  };

  return (
    <AuthLayout
      showBack
      title={strings.auth.createAccount}
      subtitle={strings.register.step1Title}
    >
      <View style={styles.container}>
        {/* Progress bar */}
        <View style={styles.progressContainer}>
          <View style={[styles.progressBar, { width: '25%' }]} />
        </View>

        {!studentInfo ? (
          // Verification form
          <View style={styles.form}>
            <FormInput
              name="studentId"
              control={control}
              label={strings.form.studentId}
              placeholder={strings.register.studentIdPlaceholder}
              leftIcon={<IdCard size={20} color={theme.colors.text.tertiary} />}
              autoCapitalize="none"
              autoCorrect={false}
            />

            {error && (
              <View style={styles.errorContainer}>
                <Text variant="bodySmall" color={theme.colors.status.error}>
                  {error}
                </Text>
              </View>
            )}

            <Button
              variant="secondary"
              size="lg"
              fullWidth
              onPress={handleSubmit(onSubmit)}
              loading={isSubmitting}
              style={styles.button}
            >
              {strings.register.verifyStudentId}
            </Button>
          </View>
        ) : (
          // Student found - show info
          <View style={styles.successContainer}>
            <View style={styles.iconContainer}>
              <CheckCircle size={48} color={theme.colors.status.success} />
            </View>

            <Text variant="h3" weight="semibold" align="center" style={styles.successTitle}>
              {strings.register.studentFound}
            </Text>

            <Card variant="outlined" style={styles.infoCard}>
              <View style={styles.infoRow}>
                <Text variant="bodySmall" color={theme.colors.text.tertiary}>
                  Name:
                </Text>
                <Text variant="body" weight="semibold">
                  {studentInfo.first_name} {studentInfo.last_name}
                </Text>
              </View>

              <View style={styles.infoRow}>
                <Text variant="bodySmall" color={theme.colors.text.tertiary}>
                  Course:
                </Text>
                <Text variant="body">{studentInfo.course}</Text>
              </View>

              <View style={styles.infoRow}>
                <Text variant="bodySmall" color={theme.colors.text.tertiary}>
                  Year & Section:
                </Text>
                <Text variant="body">
                  {studentInfo.year} - {studentInfo.section}
                </Text>
              </View>

              {studentInfo.email && (
                <View style={styles.infoRow}>
                  <Text variant="bodySmall" color={theme.colors.text.tertiary}>
                    Email:
                  </Text>
                  <Text variant="body">{studentInfo.email}</Text>
                </View>
              )}
            </Card>

            <Text variant="body" color={theme.colors.text.secondary} align="center" style={styles.confirmText}>
              {strings.register.isThisYou}
            </Text>

            <Button
              variant="primary"
              size="lg"
              fullWidth
              onPress={handleContinue}
            >
              {strings.register.yesContinue}
            </Button>
          </View>
        )}
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
  errorContainer: {
    marginTop: theme.spacing[4],
    padding: theme.spacing[4],
    backgroundColor: theme.colors.status.errorLight,
    borderRadius: theme.borderRadius.md,
  },
  button: {
    marginTop: theme.spacing[8],
  },
  successContainer: {
    flex: 1,
  },
  iconContainer: {
    alignSelf: 'center',
    marginBottom: theme.spacing[4],
  },
  successTitle: {
    marginBottom: theme.spacing[6],
  },
  infoCard: {
    marginBottom: theme.spacing[6],
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing[3],
  },
  confirmText: {
    marginBottom: theme.spacing[6],
  },
});

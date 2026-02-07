/**
 * Register Step 1 Screen - Student ID Verification
 *
 * First step of student registration.
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
import { Text, Button } from '../../components/ui';
import { FormInput } from '../../components/forms';

type RegisterStep1NavigationProp = StackNavigationProp<AuthStackParamList, 'RegisterStep1'>;

const studentIdSchema = z.object({
  studentId: z
    .string()
    .min(1, strings.errors.required)
    .regex(/^\d{2}-[A-Za-z]-\d{5}$/, strings.errors.invalidStudentId)
    .transform((value) => value.toUpperCase()),
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
    <AuthLayout showBack title={strings.auth.createAccount} subtitle={strings.register.step1Title}>
      <View style={styles.progressSection}>
        <Text variant="caption" color={theme.colors.text.secondary}>
          Step 1 of 4
        </Text>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: '25%' }]} />
        </View>
      </View>

      {!studentInfo ? (
        <View style={styles.section}>
          <Text variant="caption" color={theme.colors.text.secondary} style={styles.helperText}>
            Enter your official student ID to verify your identity.
          </Text>

          <FormInput
            name="studentId"
            control={control}
            label={strings.form.studentId}
            placeholder={strings.register.studentIdPlaceholder}
            leftIcon={<IdCard size={20} color={theme.colors.text.tertiary} />}
            autoCapitalize="characters"
            autoCorrect={false}
          />

          {error ? (
            <View style={styles.errorContainer}>
              <Text variant="bodySmall" color={theme.colors.error}>
                {error}
              </Text>
            </View>
          ) : null}

          <Button
            variant="primary"
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
        <View style={styles.section}>
          <View style={styles.successHeader}>
            <CheckCircle size={22} color={theme.colors.success} />
            <Text variant="body" weight="600" style={styles.successHeaderText}>
              {strings.register.studentFound}
            </Text>
          </View>

          <InfoRow label="Student ID" value={studentInfo.studentId} />
          <InfoRow label="Name" value={`${studentInfo.first_name} ${studentInfo.last_name}`} />
          <InfoRow label="Course" value={studentInfo.course} />
          <InfoRow label="Year & Section" value={`${studentInfo.year} - ${studentInfo.section}`} />
          {studentInfo.email ? <InfoRow label="Email" value={studentInfo.email} /> : null}

          <Text variant="body" color={theme.colors.text.secondary} align="center" style={styles.confirmText}>
            {strings.register.isThisYou}
          </Text>

          <Button variant="primary" size="lg" fullWidth onPress={handleContinue}>
            {strings.register.yesContinue}
          </Button>
        </View>
      )}
    </AuthLayout>
  );
};

const InfoRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <View style={styles.infoRow}>
    <Text variant="bodySmall" color={theme.colors.text.tertiary}>
      {label}
    </Text>
    <Text variant="body" weight="500" style={styles.infoValue}>
      {value}
    </Text>
  </View>
);

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
    marginTop: theme.spacing[1],
  },
  helperText: {
    marginBottom: theme.spacing[4],
  },
  errorContainer: {
    marginBottom: theme.spacing[4],
    padding: theme.spacing[4],
    backgroundColor: theme.colors.errorLight,
    borderRadius: theme.borderRadius.md,
  },
  button: {
    marginTop: theme.spacing[1],
  },
  successHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: theme.spacing[4],
  },
  successHeaderText: {
    marginLeft: theme.spacing[2],
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: theme.spacing[3],
  },
  infoValue: {
    flex: 1,
    textAlign: 'right',
    marginLeft: theme.spacing[4],
  },
  confirmText: {
    marginTop: theme.spacing[4],
    marginBottom: theme.spacing[5],
  },
});

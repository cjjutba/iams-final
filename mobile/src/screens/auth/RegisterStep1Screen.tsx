/**
 * Register Step 1 Screen - Two-Factor Student ID Verification
 *
 * Progressive verification flow (SECURE):
 * 1. Enter Student ID → Client-side validation only
 * 2. Enter Birthdate → API call verifies BOTH together
 * 3. Confirm student info → Proceed to Step 2
 *
 * Security: No API call until both Student ID and Birthdate are provided.
 * This prevents harvesting student IDs to check if they exist.
 */

import React, { useState } from 'react';
import { View, StyleSheet, Animated } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { IdCard, CheckCircle, Calendar, ArrowRight } from 'lucide-react-native';
import { useAuth, useToast } from '../../hooks';
import { theme, strings } from '../../constants';
import type { AuthStackParamList, StudentInfo } from '../../types';
import { AuthLayout } from '../../components/layouts';
import { Text, Button } from '../../components/ui';
import { FormInput } from '../../components/forms';

type RegisterStep1NavigationProp = StackNavigationProp<AuthStackParamList, 'RegisterStep1'>;

// Verification states for progressive disclosure
type VerificationStep = 'student_id' | 'birthdate' | 'confirmed';

// Student ID only schema (step 1a) - client-side validation
const studentIdOnlySchema = z.object({
  studentId: z
    .string()
    .min(1, strings.errors.required)
    .min(5, 'Student ID is too short')
    .transform((value) => value.trim().toUpperCase()),
});

// Birthdate only schema (step 1b) - MMDDYYYY format
const birthdateSchema = z.object({
  birthdate: z
    .string()
    .min(1, 'Birthdate is required')
    .regex(/^\d{8}$/, 'Use format: MMDDYYYY (e.g., 05152003 for May 15, 2003)')
    .refine((val) => {
      // Validate it's a real date
      const month = parseInt(val.substring(0, 2), 10);
      const day = parseInt(val.substring(2, 4), 10);
      const year = parseInt(val.substring(4, 8), 10);

      if (month < 1 || month > 12) return false;
      if (day < 1 || day > 31) return false;
      if (year < 1900 || year > new Date().getFullYear()) return false;

      return true;
    }, 'Invalid date'),
});

type StudentIdOnlyData = z.infer<typeof studentIdOnlySchema>;
type BirthdateData = z.infer<typeof birthdateSchema>;

/**
 * Convert MMDDYYYY to YYYY-MM-DD for backend API
 */
const convertBirthdateToISO = (mmddyyyy: string): string => {
  const month = mmddyyyy.substring(0, 2);
  const day = mmddyyyy.substring(2, 4);
  const year = mmddyyyy.substring(4, 8);
  return `${year}-${month}-${day}`;
};

export const RegisterStep1Screen: React.FC = () => {
  const navigation = useNavigation<RegisterStep1NavigationProp>();
  const { verifyStudentId } = useAuth();
  const { showSuccess, showError } = useToast();

  const [verificationStep, setVerificationStep] = useState<VerificationStep>('student_id');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validatedStudentId, setValidatedStudentId] = useState<string | null>(null);
  const [studentInfo, setStudentInfo] = useState<StudentInfo | null>(null);
  const [slideAnim] = useState(new Animated.Value(0));

  // Student ID form
  const studentIdForm = useForm<StudentIdOnlyData>({
    resolver: zodResolver(studentIdOnlySchema),
    defaultValues: { studentId: '' },
  });

  // Birthdate form
  const birthdateForm = useForm<BirthdateData>({
    resolver: zodResolver(birthdateSchema),
    defaultValues: { birthdate: '' },
  });

  /**
   * Step 1a: Validate Student ID format (client-side only)
   * No API call to prevent ID harvesting
   */
  const handleStudentIdSubmit = async (data: StudentIdOnlyData) => {
    // Student ID format is valid! Save it and show birthdate input
    setValidatedStudentId(data.studentId);
    setVerificationStep('birthdate');

    // Slide in birthdate field with animation
    Animated.spring(slideAnim, {
      toValue: 1,
      useNativeDriver: true,
      tension: 50,
      friction: 7,
    }).start();
  };

  /**
   * Step 1b: Validate BOTH Student ID and Birthdate with API
   * This is where the actual 2FA verification happens
   */
  const handleBirthdateSubmit = async (data: BirthdateData) => {
    if (!validatedStudentId) {
      showError('Please enter Student ID first', 'Missing Information');
      return;
    }

    try {
      setIsSubmitting(true);

      // Convert MMDDYYYY to YYYY-MM-DD
      const isoDate = convertBirthdateToISO(data.birthdate);

      console.log('Verifying:', { studentId: validatedStudentId, birthdate: isoDate });

      // Verify BOTH Student ID and birthdate together
      const response = await verifyStudentId(validatedStudentId, isoDate);

      console.log('Verification response:', response);

      if (response.success && response.data.valid) {
        // Both Student ID and birthdate verified!
        setStudentInfo({
          studentId: validatedStudentId,
          first_name: response.data.first_name || '',
          last_name: response.data.last_name || '',
          course: response.data.course || '',
          year: response.data.year || '',
          section: response.data.section || '',
          email: response.data.email,
          phone: response.data.phone,
        });
        setVerificationStep('confirmed');
        showSuccess('Identity verified successfully!', 'Student ID Verified');
      } else {
        // Show the specific error message from backend
        const errorMsg = response.message || 'Identity verification failed. Please check your Student ID and birthdate.';
        console.error('Verification failed:', errorMsg);
        showError(errorMsg, 'Verification Failed');
      }
    } catch (err: any) {
      console.error('Verification error:', err);
      const errorMessage = err.response?.data?.message || err.message || 'Unable to verify identity. Please try again.';
      showError(errorMessage, 'Verification Failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Step 1c: Navigate to Step 2 with verified student info
   */
  const handleContinue = () => {
    if (!studentInfo) {
      console.error('No student info to navigate with');
      return;
    }

    console.log('Navigating to RegisterStep2 with:', studentInfo);
    navigation.navigate('RegisterStep2', { studentInfo });
  };

  /**
   * Reset verification flow
   */
  const handleReset = () => {
    setVerificationStep('student_id');
    setValidatedStudentId(null);
    setStudentInfo(null);
    studentIdForm.reset();
    birthdateForm.reset();
    slideAnim.setValue(0);
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

      {/* Step 1a: Student ID Input */}
      {verificationStep === 'student_id' && (
        <View style={styles.section}>
          <Text variant="caption" color={theme.colors.text.secondary} style={styles.helperText}>
            Enter your official student ID to begin verification.
          </Text>

          <View style={styles.inputContainer}>
            <FormInput
              name="studentId"
              control={studentIdForm.control}
              label={strings.form.studentId}
              placeholder={strings.register.studentIdPlaceholder}
              leftIcon={<IdCard size={20} color={theme.colors.text.tertiary} />}
              autoCapitalize="characters"
              autoCorrect={false}
              autoFocus
            />
          </View>

          <Button
            variant="primary"
            size="lg"
            fullWidth
            onPress={studentIdForm.handleSubmit(handleStudentIdSubmit, (formErrors) => {
              const firstError = Object.values(formErrors)[0]?.message;
              if (firstError) showError(firstError, 'Validation Error');
            })}
            style={styles.button}
          >
            Next
          </Button>
        </View>
      )}

      {/* Step 1b: Birthdate Input (shown after Student ID entered) */}
      {verificationStep === 'birthdate' && (
        <Animated.View
          style={[
            styles.section,
            {
              opacity: slideAnim,
              transform: [
                {
                  translateY: slideAnim.interpolate({
                    inputRange: [0, 1],
                    outputRange: [20, 0],
                  }),
                },
              ],
            },
          ]}
        >
          <View style={styles.infoBadge}>
            <IdCard size={16} color={theme.colors.primary} />
            <Text variant="bodySmall" color={theme.colors.primary} style={styles.badgeText}>
              Student ID: {validatedStudentId}
            </Text>
          </View>

          <Text variant="caption" color={theme.colors.text.secondary} style={styles.helperText}>
            Enter your birthdate to verify your identity.
          </Text>

          <View style={styles.inputContainer}>
            <FormInput
              name="birthdate"
              control={birthdateForm.control}
              label="Birthdate"
              placeholder="MMDDYYYY (e.g., 05152003)"
              leftIcon={<Calendar size={20} color={theme.colors.text.tertiary} />}
              keyboardType="number-pad"
              maxLength={8}
              autoCapitalize="none"
              autoCorrect={false}
              autoFocus
            />
            <Text variant="caption" color={theme.colors.text.tertiary} style={styles.fieldHelp}>
              Format: Month-Day-Year (e.g., 05152003 for May 15, 2003)
            </Text>
          </View>

          <View style={styles.buttonRow}>
            <Button
              variant="secondary"
              size="lg"
              onPress={handleReset}
              style={styles.narrowButton}
            >
              Back
            </Button>
            <Button
              variant="primary"
              size="lg"
              onPress={birthdateForm.handleSubmit(handleBirthdateSubmit, (formErrors) => {
                const firstError = Object.values(formErrors)[0]?.message;
                if (firstError) showError(firstError, 'Validation Error');
              })}
              loading={isSubmitting}
              style={styles.wideButton}
            >
              Verify Identity
            </Button>
          </View>
        </Animated.View>
      )}

      {/* Step 1c: Confirmation (both verified) */}
      {verificationStep === 'confirmed' && studentInfo && (
        <View style={styles.section}>
          <View style={styles.successHeader}>
            <CheckCircle size={22} color={theme.colors.success} />
            <Text variant="body" weight="600" style={styles.successHeaderText}>
              Identity Verified
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

          <View style={styles.buttonRow}>
            <Button
              variant="secondary"
              size="lg"
              onPress={handleReset}
              style={styles.halfButton}
            >
              No, Go Back
            </Button>
            <Button
              variant="primary"
              size="lg"
              onPress={handleContinue}
              style={styles.halfButton}
            >
              Yes, Continue
            </Button>
          </View>
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
    marginTop: theme.spacing[4],
  },
  helperText: {
    marginBottom: theme.spacing[5],
  },
  inputContainer: {
    marginBottom: theme.spacing[5],
  },
  fieldHelp: {
    marginTop: theme.spacing[1],
  },
  button: {
    marginTop: theme.spacing[2],
  },
  buttonRow: {
    flexDirection: 'row',
    gap: theme.spacing[3],
    marginTop: theme.spacing[2],
  },
  halfButton: {
    flex: 1,
  },
  narrowButton: {
    flex: 1,
  },
  wideButton: {
    flex: 2,
  },
  infoBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.secondary,
    paddingHorizontal: theme.spacing[3],
    paddingVertical: theme.spacing[2],
    borderRadius: theme.borderRadius.md,
    alignSelf: 'flex-start',
    marginBottom: theme.spacing[4],
  },
  badgeText: {
    marginLeft: theme.spacing[2],
  },
  successHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: theme.spacing[6],
  },
  successHeaderText: {
    marginLeft: theme.spacing[2],
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: theme.spacing[4],
  },
  infoValue: {
    flex: 1,
    textAlign: 'right',
    marginLeft: theme.spacing[4],
  },
  confirmText: {
    marginTop: theme.spacing[6],
    marginBottom: theme.spacing[6],
  },
});

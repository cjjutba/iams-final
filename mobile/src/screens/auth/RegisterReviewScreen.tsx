/**
 * Register Review Screen - Final Review and Submit
 *
 * Fourth step of student registration.
 */

import React, { useState } from 'react';
import { View, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import { CheckSquare, Square, CheckCircle } from 'lucide-react-native';
import { useAuth } from '../../hooks';
import { faceService } from '../../services';
import { theme, strings, config } from '../../constants';
import type { AuthStackParamList } from '../../types';
import { AuthLayout } from '../../components/layouts';
import { Text, Button } from '../../components/ui';

type RegisterReviewRouteProp = RouteProp<AuthStackParamList, 'RegisterReview'>;

export const RegisterReviewScreen: React.FC = () => {
  const route = useRoute<RegisterReviewRouteProp>();
  const { register } = useAuth();

  const { studentInfo, accountInfo, faceImages } = route.params;

  const [isAgreed, setIsAgreed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!isAgreed) return;

    try {
      setIsSubmitting(true);
      setError(null);

      // Step 1: Create the account
      await register({
        email: accountInfo.email,
        password: accountInfo.password,
        first_name: studentInfo.first_name,
        last_name: studentInfo.last_name,
        role: 'student' as any,
        student_id: studentInfo.studentId,
        phone: accountInfo.phone,
      });

      // Step 2: Upload face images (user is now authenticated after register)
      if (faceImages.length > 0) {
        try {
          await faceService.registerFace(faceImages);
        } catch (faceErr: any) {
          console.error('Face registration failed:', faceErr);
          // Account was created successfully but face registration failed.
          // The user can re-register their face later from their profile.
        }
      }

      // Navigation happens automatically via RootNavigator auth state change
    } catch (err: any) {
      setError(err.response?.data?.message || strings.errors.generic);
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout showBack title={strings.auth.createAccount} subtitle={strings.register.step4Title}>
      <View style={styles.progressSection}>
        <Text variant="caption" color={theme.colors.text.secondary}>
          Step 4 of 4
        </Text>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: '100%' }]} />
        </View>
      </View>

      <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
        <View style={styles.section}>
          <Text variant="body" weight="600" style={styles.sectionTitle}>
            Student Information
          </Text>
          <InfoRow label="Student ID" value={studentInfo.studentId} />
          <InfoRow label="Name" value={`${studentInfo.first_name} ${studentInfo.last_name}`} />
          <InfoRow label="Course" value={studentInfo.course} />
          <InfoRow label="Year & Section" value={`${studentInfo.year} - ${studentInfo.section}`} />
        </View>

        <View style={styles.section}>
          <Text variant="body" weight="600" style={styles.sectionTitle}>
            Account Information
          </Text>
          <InfoRow label="Email" value={accountInfo.email} />
          <InfoRow label="Phone" value={accountInfo.phone} />
          <InfoRow label="Password" value="********" />
        </View>

        <View style={styles.section}>
          <View style={styles.faceRow}>
            <View style={styles.faceInfo}>
              <Text variant="body" weight="600">
                Face Registration
              </Text>
              <Text variant="bodySmall" color={theme.colors.success} style={styles.faceStatus}>
                {faceImages.length}/{config.REQUIRED_FACE_IMAGES} photos captured
              </Text>
            </View>
            <CheckCircle size={22} color={theme.colors.success} />
          </View>
        </View>

        <View style={styles.section}>
          <TouchableOpacity
            style={styles.checkbox}
            onPress={() => setIsAgreed(!isAgreed)}
            activeOpacity={theme.interaction.activeOpacity}
          >
            {isAgreed ? (
              <CheckSquare size={22} color={theme.colors.primary} />
            ) : (
              <Square size={22} color={theme.colors.text.tertiary} />
            )}
            <Text variant="bodySmall" color={theme.colors.text.secondary} style={styles.agreementText}>
              {strings.register.agreeTerms}
            </Text>
          </TouchableOpacity>
        </View>

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
          onPress={handleSubmit}
          loading={isSubmitting}
          disabled={!isAgreed}
          style={styles.submitButton}
        >
          {strings.auth.createAccount}
        </Button>
      </ScrollView>
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
  container: {
    flex: 1,
  },
  section: {
    marginBottom: theme.spacing[5],
  },
  sectionTitle: {
    marginBottom: theme.spacing[3],
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
  faceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  faceInfo: {
    flex: 1,
  },
  faceStatus: {
    marginTop: theme.spacing[1],
  },
  checkbox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  agreementText: {
    flex: 1,
    marginLeft: theme.spacing[3],
    lineHeight: 20,
  },
  errorContainer: {
    marginBottom: theme.spacing[4],
    padding: theme.spacing[4],
    backgroundColor: theme.colors.errorLight,
    borderRadius: theme.borderRadius.md,
  },
  submitButton: {
    marginBottom: theme.spacing[8],
  },
});

/**
 * Register Review Screen - Final Review and Submit
 *
 * Fourth step of student registration.
 *
 * IMPORTANT: This screen calls authService.register() directly (NOT through
 * authStore) to prevent navigation state changes during registration.
 * The auth state is only updated AFTER both account creation and face
 * registration are complete, preventing the component from unmounting
 * mid-flow.
 */

import React, { useState } from 'react';
import { View, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RouteProp } from '@react-navigation/native';
import { CheckSquare, Square, CheckCircle } from 'lucide-react-native';
import { useToast } from '../../hooks';
import { authService, faceService } from '../../services';
import { useAuthStore } from '../../stores';
import { theme, strings, config } from '../../constants';
import type { AuthStackParamList } from '../../types';
import { AuthLayout } from '../../components/layouts';
import { Text, Button } from '../../components/ui';

type RegisterReviewNavigationProp = StackNavigationProp<AuthStackParamList, 'RegisterReview'>;
type RegisterReviewRouteProp = RouteProp<AuthStackParamList, 'RegisterReview'>;

export const RegisterReviewScreen: React.FC = () => {
  const navigation = useNavigation<RegisterReviewNavigationProp>();
  const route = useRoute<RegisterReviewRouteProp>();
  const { showSuccess, showError, showWarning } = useToast();

  const { studentInfo, accountInfo, faceImages } = route.params;

  const [isAgreed, setIsAgreed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!isAgreed) return;

    try {
      setIsSubmitting(true);

      // Step 1: Create the account via authService directly.
      // We bypass authStore.register() to avoid setting isLoading/isAuthenticated
      // which would trigger RootNavigator to unmount this screen mid-flow.
      const result = await authService.register({
        student_id: studentInfo.studentId,
        email: accountInfo.email,
        password: accountInfo.password,
        first_name: studentInfo.first_name,
        last_name: studentInfo.last_name,
        phone: accountInfo.phone,
      });

      showSuccess('Account created successfully!', 'Welcome to IAMS');

      // Step 2: Upload face images if tokens are available.
      // In Supabase mode: no tokens returned (email verification required first),
      // so face registration will happen after the user verifies email and logs in.
      // In legacy mode: tokens are stored by authService.register(), so face
      // registration can proceed immediately.
      if (faceImages.length > 0 && result.tokens) {
        try {
          await faceService.registerFace(faceImages);
          showSuccess('Face registered successfully!', 'Face Recognition Active');
        } catch (faceErr: any) {
          console.error('Face registration failed:', faceErr);
          showWarning(
            'Account created but face registration failed. You can register your face later from your profile.',
            'Face Registration Incomplete',
          );
        }
      }

      // Step 3: NOW update auth state to trigger navigation.
      if (config.USE_SUPABASE_AUTH) {
        // Supabase mode: email verification required before login.
        // Update auth store and navigate to email verification screen.
        useAuthStore.setState({
          user: result.user || null,
          isAuthenticated: false,
          isLoading: false,
          emailVerificationPending: true,
          pendingVerificationEmail: accountInfo.email,
        });
        navigation.navigate('EmailVerification');
      } else {
        // Legacy mode: user is authenticated immediately.
        // Setting isAuthenticated triggers RootNavigator to switch to Student stack.
        useAuthStore.setState({
          user: result.user || null,
          isAuthenticated: true,
          isLoading: false,
          emailVerificationPending: false,
        });
      }
    } catch (err: any) {
      const errorMsg =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        strings.errors.generic;
      showError(errorMsg, 'Registration Failed');
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
    marginBottom: theme.spacing[6],
  },
  sectionTitle: {
    marginBottom: theme.spacing[4],
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
  faceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  faceInfo: {
    flex: 1,
  },
  faceStatus: {
    marginTop: theme.spacing[2],
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
  submitButton: {
    marginTop: theme.spacing[2],
    marginBottom: theme.spacing[8],
  },
});

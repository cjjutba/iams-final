/**
 * Register Review Screen - Final Review and Submit
 *
 * Fourth and final step of student registration
 * Reviews all information and submits registration
 */

import React, { useState } from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RouteProp } from '@react-navigation/native';
import { CheckSquare, Square, CheckCircle } from 'lucide-react-native';
import { useAuth } from '../../hooks';
import { theme, strings } from '../../constants';
import type { AuthStackParamList } from '../../types';
import { AuthLayout } from '../../components/layouts';
import { Text, Button, Card, Divider } from '../../components/ui';

type RegisterReviewNavigationProp = StackNavigationProp<AuthStackParamList, 'RegisterReview'>;
type RegisterReviewRouteProp = RouteProp<AuthStackParamList, 'RegisterReview'>;

export const RegisterReviewScreen: React.FC = () => {
  const navigation = useNavigation<RegisterReviewNavigationProp>();
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

      await register({
        email: accountInfo.email,
        password: accountInfo.password,
        first_name: studentInfo.first_name,
        last_name: studentInfo.last_name,
        role: 'student' as any,
        student_id: studentInfo.studentId,
        phone: accountInfo.phone,
      });

      // TODO: Upload face images after registration
      // This would typically be done in a separate API call

      // Navigation handled by RootNavigator when auth state changes
    } catch (err: any) {
      setError(err.response?.data?.message || strings.errors.generic);
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout
      showBack
      title={strings.auth.createAccount}
      subtitle={strings.register.step4Title}
    >
      <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
        {/* Progress bar */}
        <View style={styles.progressContainer}>
          <View style={[styles.progressBar, { width: '100%' }]} />
        </View>

        {/* Student Information */}
        <Card variant="outlined" style={styles.card}>
          <Text variant="h4" weight="semibold" style={styles.sectionTitle}>
            Student Information
          </Text>

          <InfoRow label="Student ID" value={studentInfo.studentId} />
          <InfoRow
            label="Name"
            value={`${studentInfo.first_name} ${studentInfo.last_name}`}
          />
          <InfoRow label="Course" value={studentInfo.course} />
          <InfoRow
            label="Year & Section"
            value={`${studentInfo.year} - ${studentInfo.section}`}
          />
        </Card>

        {/* Account Information */}
        <Card variant="outlined" style={styles.card}>
          <Text variant="h4" weight="semibold" style={styles.sectionTitle}>
            Account Information
          </Text>

          <InfoRow label="Email" value={accountInfo.email} />
          <InfoRow label="Phone" value={accountInfo.phone} />
          <InfoRow label="Password" value="••••••••" />
        </Card>

        {/* Face Registration */}
        <Card variant="outlined" style={styles.card}>
          <View style={styles.faceRow}>
            <View style={styles.faceInfo}>
              <Text variant="h4" weight="semibold">
                Face Registration
              </Text>
              <Text variant="bodySmall" color={theme.colors.status.success} style={styles.faceStatus}>
                {strings.register.facePhotosCaptured}
              </Text>
            </View>
            <CheckCircle size={24} color={theme.colors.status.success} />
          </View>
        </Card>

        {/* Terms Agreement */}
        <View style={styles.agreementContainer}>
          <TouchableOpacity
            style={styles.checkbox}
            onPress={() => setIsAgreed(!isAgreed)}
            activeOpacity={theme.interaction.activeOpacity}
          >
            {isAgreed ? (
              <CheckSquare size={24} color={theme.colors.primary} />
            ) : (
              <Square size={24} color={theme.colors.text.tertiary} />
            )}
            <Text variant="bodySmall" color={theme.colors.text.secondary} style={styles.agreementText}>
              {strings.register.agreeTerms}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Error Message */}
        {error && (
          <View style={styles.errorContainer}>
            <Text variant="bodySmall" color={theme.colors.status.error}>
              {error}
            </Text>
          </View>
        )}

        {/* Submit Button */}
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

// InfoRow component
const InfoRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <View style={styles.infoRow}>
    <Text variant="bodySmall" color={theme.colors.text.tertiary}>
      {label}
    </Text>
    <Text variant="body" weight="medium">
      {value}
    </Text>
  </View>
);

import { TouchableOpacity } from 'react-native';

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
  card: {
    marginBottom: theme.spacing[4],
  },
  sectionTitle: {
    marginBottom: theme.spacing[4],
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing[3],
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
  agreementContainer: {
    marginTop: theme.spacing[6],
    marginBottom: theme.spacing[6],
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
    backgroundColor: theme.colors.status.errorLight,
    borderRadius: theme.borderRadius.md,
  },
  submitButton: {
    marginBottom: theme.spacing[8],
  },
});

/**
 * Email Verification Screen
 *
 * Shown after registration when Supabase Auth is enabled.
 * Prompts the user to check their email and verify their account.
 * Provides "Resend" and "Check status" functionality.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { View, StyleSheet } from 'react-native';
import { Mail, CheckCircle, RefreshCw } from 'lucide-react-native';
import { useNavigation } from '@react-navigation/native';
import { useAuthStore } from '../../stores';
import { theme, strings } from '../../constants';
import { AuthLayout } from '../../components/layouts';
import { Text, Button } from '../../components/ui';

export const EmailVerificationScreen: React.FC = () => {
  const navigation = useNavigation();
  const {
    pendingVerificationEmail,
    checkVerificationStatus,
    resendVerification,
    clearVerificationPending,
    isAuthenticated,
  } = useAuthStore();

  const [isChecking, setIsChecking] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [resendSuccess, setResendSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auto-check verification status every 5 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      const verified = await checkVerificationStatus();
      if (verified) {
        clearInterval(interval);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [checkVerificationStatus]);

  // Navigate away when authenticated (email verified)
  useEffect(() => {
    if (isAuthenticated) {
      // Navigation will be handled by the root navigator
      // which switches from Auth to Student/Faculty stack
    }
  }, [isAuthenticated]);

  const handleCheckStatus = useCallback(async () => {
    setIsChecking(true);
    setError(null);

    try {
      const verified = await checkVerificationStatus();
      if (!verified) {
        setError('Email not yet verified. Please check your inbox.');
      }
    } catch {
      setError('Unable to check verification status. Please try again.');
    } finally {
      setIsChecking(false);
    }
  }, [checkVerificationStatus]);

  const handleResend = useCallback(async () => {
    if (!pendingVerificationEmail) return;

    setIsResending(true);
    setError(null);
    setResendSuccess(false);

    try {
      await resendVerification(pendingVerificationEmail);
      setResendSuccess(true);
    } catch {
      setError('Failed to resend verification email. Please try again.');
    } finally {
      setIsResending(false);
    }
  }, [pendingVerificationEmail, resendVerification]);

  const handleBackToLogin = useCallback(() => {
    clearVerificationPending();
    navigation.navigate('Welcome' as never);
  }, [clearVerificationPending, navigation]);

  return (
    <AuthLayout
      showBack
      title="Verify Your Email"
      subtitle="We sent a verification link to your email"
    >
      <View style={styles.container}>
        <View style={styles.iconSection}>
          <View style={styles.iconCircle}>
            <Mail size={40} color={theme.colors.text.primary} />
          </View>
        </View>

        <View style={styles.emailSection}>
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            We sent a verification email to:
          </Text>
          <Text variant="h3" weight="600" align="center" style={styles.emailText}>
            {pendingVerificationEmail || 'your email'}
          </Text>
        </View>

        <View style={styles.instructionsSection}>
          <Text variant="body" color={theme.colors.text.secondary} align="center" style={styles.instructions}>
            Click the link in the email to verify your account. Once verified, you can sign in to IAMS.
          </Text>
          <Text variant="bodySmall" color={theme.colors.text.tertiary} align="center" style={styles.hint}>
            If you do not see the email, check your spam or junk folder.
          </Text>
        </View>

        {resendSuccess ? (
          <View style={styles.successContainer}>
            <CheckCircle size={18} color={theme.colors.success} />
            <Text variant="bodySmall" color={theme.colors.success} style={styles.successText}>
              Verification email resent successfully
            </Text>
          </View>
        ) : null}

        {error ? (
          <View style={styles.errorContainer}>
            <Text variant="bodySmall" color={theme.colors.error}>
              {error}
            </Text>
          </View>
        ) : null}

        <View style={styles.actionsSection}>
          <Button
            variant="primary"
            size="lg"
            fullWidth
            onPress={handleCheckStatus}
            loading={isChecking}
            style={styles.checkButton}
          >
            <View style={styles.buttonContent}>
              <RefreshCw size={18} color="#fff" />
              <Text variant="body" weight="600" color="#fff" style={styles.buttonText}>
                Check Verification Status
              </Text>
            </View>
          </Button>

          <Button
            variant="outline"
            size="lg"
            fullWidth
            onPress={handleResend}
            loading={isResending}
            style={styles.resendButton}
          >
            Resend Verification Email
          </Button>

          <Button
            variant="ghost"
            size="md"
            fullWidth
            onPress={handleBackToLogin}
            style={styles.backButton}
          >
            Back to Login
          </Button>
        </View>
      </View>
    </AuthLayout>
  );
};

const styles = StyleSheet.create({
  container: {
    marginTop: theme.spacing[6],
    alignItems: 'center',
  },
  iconSection: {
    marginBottom: theme.spacing[6],
  },
  iconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: theme.colors.background,
    borderWidth: 2,
    borderColor: theme.colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emailSection: {
    marginBottom: theme.spacing[5],
    paddingHorizontal: theme.spacing[2],
  },
  emailText: {
    marginTop: theme.spacing[2],
  },
  instructionsSection: {
    marginBottom: theme.spacing[6],
    paddingHorizontal: theme.spacing[2],
  },
  instructions: {
    lineHeight: 24,
    marginBottom: theme.spacing[2],
  },
  hint: {
    lineHeight: 20,
  },
  successContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: theme.spacing[4],
    padding: theme.spacing[3],
    backgroundColor: theme.colors.successLight,
    borderRadius: theme.borderRadius.md,
    width: '100%',
  },
  successText: {
    marginLeft: theme.spacing[2],
  },
  errorContainer: {
    marginBottom: theme.spacing[4],
    padding: theme.spacing[4],
    backgroundColor: theme.colors.errorLight,
    borderRadius: theme.borderRadius.md,
    width: '100%',
  },
  actionsSection: {
    width: '100%',
  },
  checkButton: {
    marginBottom: theme.spacing[3],
  },
  buttonContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: {
    marginLeft: theme.spacing[2],
  },
  resendButton: {
    marginBottom: theme.spacing[3],
  },
  backButton: {
    marginTop: theme.spacing[2],
  },
});

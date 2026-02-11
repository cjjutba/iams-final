/**
 * Splash Screen - App Boot & Auth Check
 *
 * Displays IAMS logo while checking authentication state
 * Auto-navigates to appropriate screen after loading
 */

import React, { useEffect } from 'react';
import { View, StyleSheet, Image } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { AuthStackParamList } from '../../types';
import { theme } from '../../constants';
import { Text, Loader } from '../../components/ui';
import { storage } from '../../utils';

type SplashScreenNavigationProp = StackNavigationProp<AuthStackParamList, 'Splash'>;

export const SplashScreen: React.FC = () => {
  const navigation = useNavigation<SplashScreenNavigationProp>();

  useEffect(() => {
    const initializeApp = async () => {
      try {
        // Check if onboarding has been completed
        const onboardingComplete = await storage.getOnboardingComplete();

        // Simulate initial app loading
        await new Promise(resolve => setTimeout(resolve, 2000));

        if (onboardingComplete) {
          // Onboarding complete - check for last user role to determine login screen
          const lastUserRole = await storage.getLastUserRole();

          if (lastUserRole === 'student') {
            navigation.replace('StudentLogin');
          } else if (lastUserRole === 'faculty' || lastUserRole === 'admin') {
            navigation.replace('FacultyLogin');
          } else {
            // No previous role, show Welcome screen for role selection
            navigation.replace('Welcome');
          }
        } else {
          // First time user - show onboarding
          navigation.replace('Onboarding');
        }
      } catch (error) {
        console.error('Error initializing app:', error);
        // Fallback to onboarding on error
        navigation.replace('Onboarding');
      }
    };

    initializeApp();
  }, [navigation]);

  return (
    <View style={styles.container}>
      <View style={styles.logoContainer}>
        {/* Logo placeholder - replace with actual IAMS logo */}
        <View style={styles.logoPlaceholder}>
          <Text variant="h1" weight="700" color={theme.colors.primary}>
            IAMS
          </Text>
        </View>

        <Text variant="h3" weight="600" style={styles.title}>
          Intelligent Attendance
        </Text>
        <Text variant="h3" weight="600" style={styles.title}>
          Monitoring System
        </Text>

        <Text variant="bodySmall" color={theme.colors.text.tertiary} style={styles.subtitle}>
          JRMSU - Main Campus
        </Text>
      </View>

      <View style={styles.loaderContainer}>
        <Loader size="small" />
      </View>

      <Text variant="caption" color={theme.colors.text.tertiary} style={styles.version}>
        Version 1.0.0
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: theme.spacing[6],
  },
  logoContainer: {
    alignItems: 'center',
    marginBottom: theme.spacing[12],
  },
  logoPlaceholder: {
    width: 120,
    height: 120,
    borderRadius: theme.borderRadius.xl,
    backgroundColor: theme.colors.secondary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: theme.spacing[6],
  },
  title: {
    textAlign: 'center',
    marginBottom: theme.spacing[1],
  },
  subtitle: {
    marginTop: theme.spacing[4],
    textAlign: 'center',
  },
  loaderContainer: {
    marginBottom: theme.spacing[8],
  },
  version: {
    position: 'absolute',
    bottom: theme.spacing[8],
  },
});

/**
 * Welcome Screen - Role Selection
 *
 * "I am a..." screen with Student/Faculty role selection
 * Routes to appropriate login screen based on selection
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { AuthStackParamList } from '../../types';
import { theme } from '../../constants';
import { Text, Button } from '../../components/ui';

type WelcomeScreenNavigationProp = StackNavigationProp<AuthStackParamList, 'Welcome'>;

export const WelcomeScreen: React.FC = () => {
  const navigation = useNavigation<WelcomeScreenNavigationProp>();

  const handleStudentPress = () => {
    navigation.navigate('StudentLogin');
  };

  const handleFacultyPress = () => {
    navigation.navigate('FacultyLogin');
  };

  return (
    <View style={styles.container}>
      {/* Logo */}
      <View style={styles.logoContainer}>
        <View style={styles.logoPlaceholder}>
          <Text variant="h1" weight="bold" color={theme.colors.primary}>
            IAMS
          </Text>
        </View>

        <Text variant="h2" weight="bold" align="center" style={styles.title}>
          Welcome to IAMS
        </Text>

        <Text
          variant="body"
          color={theme.colors.text.secondary}
          align="center"
          style={styles.subtitle}
        >
          Intelligent Attendance Monitoring System
        </Text>
      </View>

      {/* Role Selection */}
      <View style={styles.roleContainer}>
        <Text variant="h3" weight="semibold" align="center" style={styles.question}>
          I am a...
        </Text>

        <Button
          variant="primary"
          size="lg"
          fullWidth
          onPress={handleStudentPress}
          style={styles.button}
        >
          Student
        </Button>

        <Button
          variant="outline"
          size="lg"
          fullWidth
          onPress={handleFacultyPress}
          style={styles.button}
        >
          Faculty
        </Button>
      </View>

      {/* Footer */}
      <View style={styles.footer}>
        <Text variant="caption" color={theme.colors.text.tertiary} align="center">
          By continuing, you agree to our Terms of Service
        </Text>
        <Text variant="caption" color={theme.colors.text.tertiary} align="center">
          and Privacy Policy
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
    paddingHorizontal: theme.spacing[6],
    justifyContent: 'space-between',
  },
  logoContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: theme.spacing[12],
  },
  logoPlaceholder: {
    width: 100,
    height: 100,
    borderRadius: theme.borderRadius.xl,
    backgroundColor: theme.colors.secondary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: theme.spacing[6],
  },
  title: {
    marginBottom: theme.spacing[3],
  },
  subtitle: {
    paddingHorizontal: theme.spacing[8],
  },
  roleContainer: {
    marginBottom: theme.spacing[8],
  },
  question: {
    marginBottom: theme.spacing[6],
  },
  button: {
    marginBottom: theme.spacing[4],
  },
  footer: {
    paddingBottom: theme.spacing[8],
  },
});

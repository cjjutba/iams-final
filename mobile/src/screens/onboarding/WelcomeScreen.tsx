/**
 * Welcome Screen - Role Selection
 *
 * Role selection screen for student/faculty entry points.
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { AuthStackParamList } from '../../types';
import { theme, strings } from '../../constants';
import { Text, Button } from '../../components/ui';

type WelcomeScreenNavigationProp = StackNavigationProp<AuthStackParamList, 'Welcome'>;

export const WelcomeScreen: React.FC = () => {
  const navigation = useNavigation<WelcomeScreenNavigationProp>();

  return (
    <View style={styles.container}>
      <View style={styles.logoContainer}>
        <View style={styles.logoPlaceholder}>
          <Text variant="h1" weight="700" color={theme.colors.primary}>
            IAMS
          </Text>
        </View>

        <Text variant="h2" weight="700" align="center" style={styles.title}>
          {strings.auth.welcome}
        </Text>

        <Text variant="body" color={theme.colors.text.secondary} align="center" style={styles.subtitle}>
          {strings.app.fullName}
        </Text>
      </View>

      <View style={styles.roleSection}>
        <Text variant="h3" weight="600" align="center" style={styles.question}>
          {strings.auth.iAmA}
        </Text>

        <Button
          variant="primary"
          size="lg"
          fullWidth
          onPress={() => navigation.navigate('StudentLogin')}
          style={styles.button}
        >
          {strings.auth.student}
        </Button>

        <Button
          variant="outline"
          size="lg"
          fullWidth
          onPress={() => navigation.navigate('FacultyLogin')}
          style={styles.button}
        >
          {strings.auth.faculty}
        </Button>
      </View>

      <View style={styles.footer}>
        <Text variant="caption" color={theme.colors.text.tertiary} align="center">
          {strings.auth.termsAgree}
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
    paddingBottom: theme.spacing[8],
  },
  logoContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: theme.spacing[10],
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
    paddingHorizontal: theme.spacing[6],
  },
  roleSection: {
    paddingHorizontal: theme.spacing[1],
  },
  question: {
    marginBottom: theme.spacing[5],
  },
  button: {
    marginBottom: theme.spacing[3],
  },
  footer: {
    marginTop: theme.spacing[5],
    paddingHorizontal: theme.spacing[2],
  },
});

/**
 * AuthLayout Component
 *
 * Layout wrapper for authentication and onboarding screens.
 * Includes optional back button, title, and subtitle.
 */

import React from 'react';
import {
  View,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { ChevronLeft } from 'lucide-react-native';
import { theme } from '../../constants';
import { Text } from '../ui';

interface AuthLayoutProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  showBack?: boolean;
}

export const AuthLayout: React.FC<AuthLayoutProps> = ({
  children,
  title,
  subtitle,
  showBack = false,
}) => {
  const navigation = useNavigation();

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardAvoid}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {/* Back button */}
          {showBack && (
            <TouchableOpacity
              onPress={() => navigation.goBack()}
              style={styles.backButton}
              activeOpacity={theme.interaction.activeOpacity}
            >
              <ChevronLeft size={24} color={theme.colors.text.primary} />
              <Text variant="body" color={theme.colors.text.primary} style={styles.backText}>
                Back
              </Text>
            </TouchableOpacity>
          )}

          {/* Title */}
          {title && (
            <Text variant="h2" weight="bold" style={styles.title}>
              {title}
            </Text>
          )}

          {/* Subtitle */}
          {subtitle && (
            <Text variant="body" color={theme.colors.text.secondary} style={styles.subtitle}>
              {subtitle}
            </Text>
          )}

          {/* Content */}
          <View style={styles.content}>{children}</View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  keyboardAvoid: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: theme.spacing[6], // 24px
    paddingTop: theme.spacing[4], // 16px
    paddingBottom: theme.spacing[8], // 32px
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: theme.spacing[6], // 24px
    alignSelf: 'flex-start',
  },
  backText: {
    marginLeft: theme.spacing[2], // 8px
  },
  title: {
    marginBottom: theme.spacing[3], // 12px
  },
  subtitle: {
    marginBottom: theme.spacing[8], // 32px
    lineHeight: 24,
  },
  content: {
    flex: 1,
  },
});

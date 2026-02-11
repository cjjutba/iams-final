/**
 * ScreenLayout Component
 *
 * Reusable screen wrapper with safe area, keyboard avoiding, and scroll support.
 * Provides consistent padding and background across screens.
 */

import React from 'react';
import {
  View,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  StatusBar,
  RefreshControlProps,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { theme } from '../../constants';

interface ScreenLayoutProps {
  children: React.ReactNode;
  scrollable?: boolean;
  padded?: boolean;
  safeArea?: boolean;
  keyboardAvoiding?: boolean;
  backgroundColor?: keyof typeof theme.colors;
  refreshControl?: React.ReactElement<RefreshControlProps>;
}

export const ScreenLayout: React.FC<ScreenLayoutProps> = ({
  children,
  scrollable = false,
  padded = true,
  safeArea = true,
  keyboardAvoiding = false,
  backgroundColor = 'background',
  refreshControl,
}) => {
  const bgColor = theme.colors[backgroundColor] as string;

  const containerStyle = [
    styles.container,
    { backgroundColor: bgColor },
    padded && styles.padded,
  ];

  const Container = safeArea ? SafeAreaView : View;

  const content = scrollable ? (
    <ScrollView
      contentContainerStyle={styles.scrollContent}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      refreshControl={refreshControl}
      alwaysBounceVertical={true}
    >
      {children}
    </ScrollView>
  ) : (
    <>{children}</>
  );

  return (
    <>
      <StatusBar barStyle="dark-content" backgroundColor={bgColor} />
      <Container style={containerStyle}>
        {keyboardAvoiding ? (
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={styles.keyboardAvoid}
          >
            {content}
          </KeyboardAvoidingView>
        ) : (
          content
        )}
      </Container>
    </>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  padded: {
    paddingHorizontal: theme.spacing[4], // 16px
  },
  scrollContent: {
    flexGrow: 1,
  },
  keyboardAvoid: {
    flex: 1,
  },
});

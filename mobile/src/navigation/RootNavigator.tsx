/**
 * Root Navigator - Main App Navigation
 *
 * Conditionally renders Auth, Student, or Faculty navigator based on:
 * - Authentication state
 * - User role
 *
 * Flow:
 * 1. Load user from storage on app start
 * 2. If not authenticated -> AuthNavigator
 * 3. If authenticated:
 *    - Student role -> StudentNavigator
 *    - Faculty role -> FacultyNavigator
 */

import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Animated, Easing } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import type { RootStackParamList } from '../types';
import { useAuthStore } from '../stores';
import { UserRole } from '../types';
import { theme } from '../constants';

import { AuthNavigator } from './AuthNavigator';
import { StudentNavigator } from './StudentNavigator';
import { FacultyNavigator } from './FacultyNavigator';

const Stack = createStackNavigator<RootStackParamList>();

export const RootNavigator: React.FC = () => {
  const { isAuthenticated, isLoading, user, loadUser, initializeAuthListener } = useAuthStore();

  // Track whether the initial auth check has completed.
  // Only show the splash screen on the very first load — never again.
  // This prevents pull-to-refresh or other actions that happen to set
  // isLoading=true from unmounting the entire navigation tree.
  const hasInitialized = useRef(false);

  // Load user on app start and initialize auth listener
  useEffect(() => {
    loadUser();

    // Initialize Supabase auth listener to handle token refresh and session changes
    const unsubscribe = initializeAuthListener();

    // Cleanup: unsubscribe from auth listener on unmount
    return () => {
      unsubscribe();
    };
  }, []);

  // Mark initialization complete once the first load finishes
  useEffect(() => {
    if (!isLoading && !hasInitialized.current) {
      hasInitialized.current = true;
    }
  }, [isLoading]);

  // Breathing animation for loading state
  const scaleAnim = useRef(new Animated.Value(1)).current;
  const opacityAnim = useRef(new Animated.Value(0.85)).current;

  const showSplash = isLoading && !hasInitialized.current;

  useEffect(() => {
    if (!showSplash) return;
    const breathing = Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(scaleAnim, { toValue: 1.06, duration: 2000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
          Animated.timing(opacityAnim, { toValue: 1, duration: 2000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        ]),
        Animated.parallel([
          Animated.timing(scaleAnim, { toValue: 1, duration: 2000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
          Animated.timing(opacityAnim, { toValue: 0.85, duration: 2000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        ]),
      ]),
    );
    breathing.start();
    return () => breathing.stop();
  }, [showSplash, scaleAnim, opacityAnim]);

  // Show splash screen ONLY during initial app load
  if (showSplash) {
    return (
      <View style={loadingStyles.container}>
        <Animated.Image
          source={require('../../assets/iams-icon.png')}
          style={[loadingStyles.icon, { transform: [{ scale: scaleAnim }], opacity: opacityAnim }]}
          resizeMode="contain"
        />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {!isAuthenticated ? (
          // Not authenticated -> Auth flow
          <Stack.Screen name="Auth" component={AuthNavigator} />
        ) : user?.role === UserRole.STUDENT ? (
          // Student -> Student app
          <Stack.Screen name="Student" component={StudentNavigator} />
        ) : user?.role === UserRole.FACULTY ? (
          // Faculty -> Faculty app
          <Stack.Screen name="Faculty" component={FacultyNavigator} />
        ) : (
          // Fallback to auth if role is unknown
          <Stack.Screen name="Auth" component={AuthNavigator} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
};

const loadingStyles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
  icon: {
    width: 140,
    height: 140,
  },
});

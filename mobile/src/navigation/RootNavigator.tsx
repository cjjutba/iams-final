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

import React, { useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import type { RootStackParamList } from '../types';
import { useAuthStore } from '../stores';
import { UserRole } from '../types';
import { Loader } from '../components/ui';

import { AuthNavigator } from './AuthNavigator';
import { StudentNavigator } from './StudentNavigator';
import { FacultyNavigator } from './FacultyNavigator';

const Stack = createStackNavigator<RootStackParamList>();

export const RootNavigator: React.FC = () => {
  const { isAuthenticated, isLoading, user, loadUser } = useAuthStore();

  // Load user on app start
  useEffect(() => {
    loadUser();
  }, []);

  // Show loading screen while checking auth status
  if (isLoading) {
    return <Loader fullScreen message="Loading..." />;
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

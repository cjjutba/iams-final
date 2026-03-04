/**
 * Auth Navigator - Authentication Flow
 *
 * Stack navigator for unauthenticated users:
 * - Splash screen
 * - Onboarding (4 slides)
 * - Welcome (role selection)
 * - Student/Faculty login
 * - Student registration (4 steps)
 * - Email verification (Supabase Auth)
 * - Password reset (Supabase Auth deep link)
 */

import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import type { AuthStackParamList } from '../types';

// Import screens
import {
  SplashScreen,
  OnboardingScreen,
  WelcomeScreen,
  StudentLoginScreen,
  FacultyLoginScreen,
  ForgotPasswordScreen,
  EmailVerificationScreen,
  ResetPasswordScreen,
  RegisterStep1Screen,
  RegisterStep2Screen,
  RegisterStep3Screen,
  RegisterReviewScreen,
} from '../screens';

const Stack = createStackNavigator<AuthStackParamList>();

export const AuthNavigator: React.FC = () => {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
        gestureEnabled: false,
      }}
    >
      <Stack.Screen name="Splash" component={SplashScreen} />
      <Stack.Screen name="Onboarding" component={OnboardingScreen} />
      <Stack.Screen name="Welcome" component={WelcomeScreen} />
      <Stack.Screen name="StudentLogin" component={StudentLoginScreen} />
      <Stack.Screen name="FacultyLogin" component={FacultyLoginScreen} />
      <Stack.Screen name="ForgotPassword" component={ForgotPasswordScreen} />
      <Stack.Screen name="EmailVerification" component={EmailVerificationScreen} />
      <Stack.Screen name="ResetPassword" component={ResetPasswordScreen} />
      <Stack.Screen name="RegisterStep1" component={RegisterStep1Screen} />
      <Stack.Screen name="RegisterStep2" component={RegisterStep2Screen} />
      <Stack.Screen name="RegisterStep3" component={RegisterStep3Screen} />
      <Stack.Screen name="RegisterReview" component={RegisterReviewScreen} />
    </Stack.Navigator>
  );
};

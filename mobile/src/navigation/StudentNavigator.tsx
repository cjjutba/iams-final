/**
 * Student Navigator - Student App Stack
 *
 * Stack navigator for authenticated students:
 * - Bottom tabs (main navigation)
 * - Modal screens (attendance detail, edit profile, etc.)
 */

import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import type { StudentStackParamList } from '../types';
import { StudentTabNavigator } from './StudentTabNavigator';
import {
  StudentAttendanceDetailScreen,
  StudentEditProfileScreen,
  StudentFaceRegisterScreen,
  StudentNotificationsScreen,
  SettingsScreen,
} from '../screens';

const Stack = createStackNavigator<StudentStackParamList>();

export const StudentNavigator: React.FC = () => {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen name="StudentTabs" component={StudentTabNavigator} />
      <Stack.Screen
        name="AttendanceDetail"
        component={StudentAttendanceDetailScreen}
        options={{
          presentation: 'modal',
        }}
      />
      <Stack.Screen name="EditProfile" component={StudentEditProfileScreen} />
      <Stack.Screen name="FaceRegister" component={StudentFaceRegisterScreen} />
      <Stack.Screen name="Notifications" component={StudentNotificationsScreen} />
      <Stack.Screen name="Settings" component={SettingsScreen} />
    </Stack.Navigator>
  );
};

/**
 * Faculty Navigator - Faculty App Stack
 *
 * Stack navigator for authenticated faculty:
 * - Bottom tabs (main navigation)
 * - Modal screens (live attendance, class detail, etc.)
 */

import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import type { FacultyStackParamList } from '../types';
import { FacultyTabNavigator } from './FacultyTabNavigator';
import {
  FacultyLiveAttendanceScreen,
  FacultyLiveFeedScreen,
  FacultyClassDetailScreen,
  FacultyStudentDetailScreen,
  FacultyManualEntryScreen,
  FacultyReportsScreen,
  StudentEditProfileScreen,
  FacultyNotificationsScreen,
  SettingsScreen,
} from '../screens';

const Stack = createStackNavigator<FacultyStackParamList>();

export const FacultyNavigator: React.FC = () => {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
      }}
    >
      <Stack.Screen name="FacultyTabs" component={FacultyTabNavigator} />
      <Stack.Screen
        name="LiveAttendance"
        component={FacultyLiveAttendanceScreen}
        options={{
          presentation: 'modal',
        }}
      />
      <Stack.Screen name="LiveFeed" component={FacultyLiveFeedScreen} />
      <Stack.Screen name="ClassDetail" component={FacultyClassDetailScreen} />
      <Stack.Screen name="StudentDetail" component={FacultyStudentDetailScreen} />
      <Stack.Screen name="ManualEntry" component={FacultyManualEntryScreen} />
      <Stack.Screen name="Reports" component={FacultyReportsScreen} />
      <Stack.Screen name="EditProfile" component={StudentEditProfileScreen} />
      <Stack.Screen name="Notifications" component={FacultyNotificationsScreen} />
      <Stack.Screen name="Settings" component={SettingsScreen} />
    </Stack.Navigator>
  );
};

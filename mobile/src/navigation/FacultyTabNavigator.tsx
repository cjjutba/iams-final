/**
 * Faculty Tab Navigator - Bottom Tabs for Faculty
 *
 * Bottom tab navigation with 5 tabs:
 * - Home
 * - Schedule
 * - Analytics
 * - Alerts
 * - Profile
 */

import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Home, Calendar, BarChart3, Bell, User } from 'lucide-react-native';
import type { FacultyTabParamList } from '../types';
import { theme } from '../constants';
import {
  FacultyHomeScreen,
  FacultyScheduleScreen,
  FacultyAnalyticsDashboardScreen,
  FacultyAlertsScreen,
  FacultyProfileScreen,
} from '../screens';

const Tab = createBottomTabNavigator<FacultyTabParamList>();

export const FacultyTabNavigator: React.FC = () => {
  const insets = useSafeAreaInsets();

  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: theme.colors.primary,
        tabBarInactiveTintColor: theme.colors.text.tertiary,
        tabBarStyle: {
          backgroundColor: theme.colors.background,
          borderTopColor: theme.colors.border,
          borderTopWidth: 1,
          height: theme.layout.tabBarHeight + insets.bottom,
          paddingBottom: insets.bottom + 8,
          paddingTop: 8,
        },
        tabBarLabelStyle: {
          fontSize: theme.typography.fontSize.xs,
          fontWeight: theme.typography.fontWeight.medium,
        },
      }}
    >
      <Tab.Screen
        name="FacultyHome"
        component={FacultyHomeScreen}
        options={{
          tabBarLabel: 'Home',
          tabBarIcon: ({ color, size }) => <Home size={size} color={color} />,
        }}
      />
      <Tab.Screen
        name="FacultySchedule"
        component={FacultyScheduleScreen}
        options={{
          tabBarLabel: 'Schedule',
          tabBarIcon: ({ color, size }) => <Calendar size={size} color={color} />,
        }}
      />
      <Tab.Screen
        name="FacultyAnalytics"
        component={FacultyAnalyticsDashboardScreen}
        options={{
          tabBarLabel: 'Analytics',
          tabBarIcon: ({ color, size }) => <BarChart3 size={size} color={color} />,
        }}
      />
      <Tab.Screen
        name="FacultyAlerts"
        component={FacultyAlertsScreen}
        options={{
          tabBarLabel: 'Alerts',
          tabBarIcon: ({ color, size }) => <Bell size={size} color={color} />,
        }}
      />
      <Tab.Screen
        name="FacultyProfile"
        component={FacultyProfileScreen}
        options={{
          tabBarLabel: 'Profile',
          tabBarIcon: ({ color, size }) => <User size={size} color={color} />,
        }}
      />
    </Tab.Navigator>
  );
};

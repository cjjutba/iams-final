/**
 * IAMS Mobile App - Main Entry Point
 *
 * Intelligent Attendance Monitoring System
 * React Native mobile app for students and faculty
 */

import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { RootNavigator } from './src/navigation';

export default function App() {
  return (
    <>
      <RootNavigator />
      <StatusBar style="dark" />
    </>
  );
}

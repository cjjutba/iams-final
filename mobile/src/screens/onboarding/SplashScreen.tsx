/**
 * Splash Screen - App Boot & Auth Check
 *
 * Displays IAMS icon with a slow breathing animation while
 * checking authentication state, then navigates accordingly.
 */

import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Image, Animated, Easing } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { AuthStackParamList } from '../../types';
import { theme } from '../../constants';
import { storage } from '../../utils';

type SplashScreenNavigationProp = StackNavigationProp<AuthStackParamList, 'Splash'>;

export const SplashScreen: React.FC = () => {
  const navigation = useNavigation<SplashScreenNavigationProp>();
  const scaleAnim = useRef(new Animated.Value(1)).current;
  const opacityAnim = useRef(new Animated.Value(0.85)).current;

  // Slow breathing animation
  useEffect(() => {
    const breathing = Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(scaleAnim, {
            toValue: 1.06,
            duration: 2000,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true,
          }),
          Animated.timing(opacityAnim, {
            toValue: 1,
            duration: 2000,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true,
          }),
        ]),
        Animated.parallel([
          Animated.timing(scaleAnim, {
            toValue: 1,
            duration: 2000,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true,
          }),
          Animated.timing(opacityAnim, {
            toValue: 0.85,
            duration: 2000,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true,
          }),
        ]),
      ]),
    );
    breathing.start();
    return () => breathing.stop();
  }, [scaleAnim, opacityAnim]);

  // Navigation logic
  useEffect(() => {
    const initializeApp = async () => {
      try {
        const onboardingComplete = await storage.getOnboardingComplete();

        // Wait for at least one breathing cycle
        await new Promise(resolve => setTimeout(resolve, 2000));

        if (onboardingComplete) {
          const lastUserRole = await storage.getLastUserRole();

          if (lastUserRole === 'student') {
            navigation.replace('StudentLogin');
          } else if (lastUserRole === 'faculty' || lastUserRole === 'admin') {
            navigation.replace('FacultyLogin');
          } else {
            navigation.replace('Welcome');
          }
        } else {
          navigation.replace('Onboarding');
        }
      } catch (error) {
        console.error('Error initializing app:', error);
        navigation.replace('Onboarding');
      }
    };

    initializeApp();
  }, [navigation]);

  return (
    <View style={styles.container}>
      <Animated.Image
        source={require('../../../assets/iams-icon.png')}
        style={[
          styles.icon,
          {
            transform: [{ scale: scaleAnim }],
            opacity: opacityAnim,
          },
        ]}
        resizeMode="contain"
      />
    </View>
  );
};

const styles = StyleSheet.create({
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

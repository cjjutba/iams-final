/**
 * Onboarding Screen - 4 Swipeable Slides
 *
 * Introduces app features:
 * 1. Automated Attendance
 * 2. Real-time Monitoring
 * 3. Face Recognition
 * 4. Easy Access
 */

import React, { useRef, useState } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  Dimensions,
  NativeSyntheticEvent,
  NativeScrollEvent,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { AuthStackParamList } from '../../types';
import { theme } from '../../constants';
import { Text, Button } from '../../components/ui';

type OnboardingScreenNavigationProp = StackNavigationProp<AuthStackParamList, 'Onboarding'>;

const { width } = Dimensions.get('window');

interface Slide {
  title: string;
  description: string;
  icon: string;
}

const slides: Slide[] = [
  {
    title: 'Automated Attendance',
    description: 'No more manual roll calls. Our AI-powered system automatically tracks your attendance using facial recognition.',
    icon: '📋',
  },
  {
    title: 'Real-time Monitoring',
    description: 'Stay updated with live attendance status. Faculty can monitor classes in real-time, students can check their records instantly.',
    icon: '⏱️',
  },
  {
    title: 'Face Recognition',
    description: 'Secure and accurate identification using advanced face recognition technology. Your face is your attendance card.',
    icon: '👤',
  },
  {
    title: 'Easy Access',
    description: 'View your schedule, attendance history, and presence scores all in one place. Simple, fast, and reliable.',
    icon: '📱',
  },
];

export const OnboardingScreen: React.FC = () => {
  const navigation = useNavigation<OnboardingScreenNavigationProp>();
  const scrollViewRef = useRef<ScrollView>(null);
  const [currentIndex, setCurrentIndex] = useState(0);

  const handleScroll = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const contentOffsetX = event.nativeEvent.contentOffset.x;
    const index = Math.round(contentOffsetX / width);
    setCurrentIndex(index);
  };

  const handleNext = () => {
    if (currentIndex < slides.length - 1) {
      scrollViewRef.current?.scrollTo({
        x: width * (currentIndex + 1),
        animated: true,
      });
    } else {
      navigation.replace('Welcome');
    }
  };

  const handleSkip = () => {
    navigation.replace('Welcome');
  };

  return (
    <View style={styles.container}>
      {/* Skip button */}
      <View style={styles.header}>
        <Button variant="ghost" onPress={handleSkip}>
          Skip
        </Button>
      </View>

      {/* Slides */}
      <ScrollView
        ref={scrollViewRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onScroll={handleScroll}
        scrollEventThrottle={16}
        style={styles.scrollView}
      >
        {slides.map((slide, index) => (
          <View key={index} style={styles.slide}>
            <View style={styles.iconContainer}>
              <Text variant="h1" style={styles.icon}>
                {slide.icon}
              </Text>
            </View>

            <Text variant="h2" weight="bold" align="center" style={styles.title}>
              {slide.title}
            </Text>

            <Text
              variant="body"
              color={theme.colors.text.secondary}
              align="center"
              style={styles.description}
            >
              {slide.description}
            </Text>
          </View>
        ))}
      </ScrollView>

      {/* Pagination dots */}
      <View style={styles.pagination}>
        {slides.map((_, index) => (
          <View
            key={index}
            style={[
              styles.dot,
              index === currentIndex && styles.dotActive,
            ]}
          />
        ))}
      </View>

      {/* Next/Get Started button */}
      <View style={styles.footer}>
        <Button
          variant="primary"
          size="lg"
          fullWidth
          onPress={handleNext}
        >
          {currentIndex === slides.length - 1 ? 'Get Started' : 'Next'}
        </Button>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  header: {
    paddingHorizontal: theme.spacing[6],
    paddingTop: theme.spacing[8],
    alignItems: 'flex-end',
  },
  scrollView: {
    flex: 1,
  },
  slide: {
    width,
    paddingHorizontal: theme.spacing[6],
    justifyContent: 'center',
    alignItems: 'center',
  },
  iconContainer: {
    width: 120,
    height: 120,
    borderRadius: theme.borderRadius.xl,
    backgroundColor: theme.colors.secondary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: theme.spacing[8],
  },
  icon: {
    fontSize: 60,
  },
  title: {
    marginBottom: theme.spacing[4],
    paddingHorizontal: theme.spacing[4],
  },
  description: {
    paddingHorizontal: theme.spacing[8],
    lineHeight: 24,
  },
  pagination: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: theme.spacing[8],
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.border,
    marginHorizontal: theme.spacing[1],
  },
  dotActive: {
    backgroundColor: theme.colors.primary,
    width: 24,
  },
  footer: {
    paddingHorizontal: theme.spacing[6],
    paddingBottom: theme.spacing[8],
  },
});

/**
 * Register Step 3 Screen - Face Registration
 *
 * Third step of student registration.
 */

import React, { useState, useRef } from 'react';
import { View, StyleSheet, TouchableOpacity } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RouteProp } from '@react-navigation/native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Image } from 'expo-image';
import { Camera } from 'lucide-react-native';
import { theme, strings, config } from '../../constants';
import type { AuthStackParamList } from '../../types';
import { AuthLayout } from '../../components/layouts';
import { Text, Button } from '../../components/ui';

type RegisterStep3NavigationProp = StackNavigationProp<AuthStackParamList, 'RegisterStep3'>;
type RegisterStep3RouteProp = RouteProp<AuthStackParamList, 'RegisterStep3'>;

const REQUIRED_IMAGES = config.REQUIRED_FACE_IMAGES;

const INSTRUCTIONS = [
  strings.register.faceInstructions.straight,
  strings.register.faceInstructions.left,
  strings.register.faceInstructions.right,
  strings.register.faceInstructions.up,
  strings.register.faceInstructions.down,
];

export const RegisterStep3Screen: React.FC = () => {
  const navigation = useNavigation<RegisterStep3NavigationProp>();
  const route = useRoute<RegisterStep3RouteProp>();
  const cameraRef = useRef<CameraView>(null);

  const { studentInfo, accountInfo } = route.params;

  const [permission, requestPermission] = useCameraPermissions();
  const [capturedImages, setCapturedImages] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  const handleCapture = async () => {
    if (!cameraRef.current) return;

    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: config.FACE_IMAGE_QUALITY,
        base64: true,
      });

      if (photo?.uri) {
        const newImages = [...capturedImages, photo.uri];
        setCapturedImages(newImages);

        if (newImages.length < REQUIRED_IMAGES) {
          setCurrentIndex(newImages.length);
        }
      }
    } catch (error) {
      console.error('Error capturing photo:', error);
    }
  };

  const handleRemoveImage = (index: number) => {
    const newImages = capturedImages.filter((_, i) => i !== index);
    setCapturedImages(newImages);
    setCurrentIndex(newImages.length);
  };

  const handleNext = () => {
    navigation.navigate('RegisterReview', {
      studentInfo,
      accountInfo,
      faceImages: capturedImages,
    });
  };

  if (!permission || !permission.granted) {
    return (
      <AuthLayout showBack title={strings.auth.createAccount} subtitle={strings.register.step3Title}>
        <View style={styles.progressSection}>
          <Text variant="caption" color={theme.colors.text.secondary}>
            Step 3 of 4
          </Text>
          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: '75%' }]} />
          </View>
        </View>

        <View style={styles.section}>
          <Text variant="body" align="center" color={theme.colors.text.secondary} style={styles.permissionText}>
            {permission ? 'Camera permission is required to register your face.' : 'Loading camera permissions...'}
          </Text>
          {permission ? (
            <Button variant="primary" onPress={requestPermission}>
              Grant Permission
            </Button>
          ) : null}
        </View>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout showBack title={strings.auth.createAccount} subtitle={strings.register.step3Title}>
      <View style={styles.progressSection}>
        <Text variant="caption" color={theme.colors.text.secondary}>
          Step 3 of 4
        </Text>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: '75%' }]} />
        </View>
      </View>

      <View style={styles.section}>
        <Text variant="body" weight="600" align="center" style={styles.instruction}>
          {INSTRUCTIONS[currentIndex] || INSTRUCTIONS[INSTRUCTIONS.length - 1]}
        </Text>

        <View style={styles.cameraContainer}>
          <CameraView ref={cameraRef} style={styles.camera} facing="front">
            <View style={styles.overlay}>
              <View style={styles.faceGuide} />
            </View>
          </CameraView>
        </View>

        <View style={styles.thumbnailRow}>
          {Array.from({ length: REQUIRED_IMAGES }).map((_, index) => (
            <TouchableOpacity
              key={index}
              style={styles.thumbnailContainer}
              onPress={() => capturedImages[index] && handleRemoveImage(index)}
              disabled={!capturedImages[index]}
              activeOpacity={theme.interaction.activeOpacity}
            >
              {capturedImages[index] ? (
                <Image source={{ uri: capturedImages[index] }} style={styles.thumbnail} />
              ) : (
                <View style={styles.thumbnailPlaceholder}>
                  <Text variant="caption" color={theme.colors.text.tertiary}>
                    {index + 1}
                  </Text>
                </View>
              )}
            </TouchableOpacity>
          ))}
        </View>

        <Text variant="bodySmall" color={theme.colors.text.secondary} align="center" style={styles.progressText}>
          Captured: {capturedImages.length}/{REQUIRED_IMAGES}
        </Text>

        {capturedImages.length < REQUIRED_IMAGES ? (
          <TouchableOpacity
            style={styles.captureButton}
            onPress={handleCapture}
            activeOpacity={theme.interaction.activeOpacity}
          >
            <Camera size={30} color={theme.colors.background} />
          </TouchableOpacity>
        ) : (
          <Button variant="primary" size="lg" fullWidth onPress={handleNext} style={styles.nextButton}>
            {strings.common.next}
          </Button>
        )}
      </View>
    </AuthLayout>
  );
};

const styles = StyleSheet.create({
  progressSection: {
    marginTop: theme.spacing[2],
    marginBottom: theme.spacing[5],
    gap: theme.spacing[2],
  },
  progressTrack: {
    height: 6,
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.border,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.primary,
  },
  section: {
    marginTop: theme.spacing[4],
  },
  permissionText: {
    marginBottom: theme.spacing[6],
    lineHeight: 22,
  },
  instruction: {
    marginBottom: theme.spacing[5],
  },
  cameraContainer: {
    aspectRatio: 3 / 4,
    borderRadius: theme.borderRadius.lg,
    overflow: 'hidden',
    marginBottom: theme.spacing[6],
  },
  camera: {
    flex: 1,
  },
  overlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  faceGuide: {
    width: 200,
    height: 280,
    borderWidth: 2,
    borderColor: theme.colors.background,
    borderRadius: 100,
    backgroundColor: 'transparent',
  },
  thumbnailRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: theme.spacing[5],
  },
  thumbnailContainer: {
    marginHorizontal: theme.spacing[1],
  },
  thumbnail: {
    width: 56,
    height: 56,
    borderRadius: theme.borderRadius.md,
  },
  thumbnailPlaceholder: {
    width: 56,
    height: 56,
    borderRadius: theme.borderRadius.md,
    backgroundColor: theme.colors.secondary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  progressText: {
    marginBottom: theme.spacing[6],
  },
  captureButton: {
    width: 70,
    height: 70,
    borderRadius: 35,
    backgroundColor: theme.colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    alignSelf: 'center',
    ...theme.shadows.sm,
  },
  nextButton: {
    marginTop: theme.spacing[2],
  },
});

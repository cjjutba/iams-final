/**
 * Register Step 3 Screen - Face Registration
 *
 * Third step of student registration
 * Captures 5 face images from different angles using camera
 */

import React, { useState, useRef } from 'react';
import { View, StyleSheet, TouchableOpacity } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RouteProp } from '@react-navigation/native';
import { CameraView, CameraType, useCameraPermissions } from 'expo-camera';
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

      if (photo && photo.uri) {
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

  if (!permission) {
    return (
      <AuthLayout
        showBack
        title={strings.auth.createAccount}
        subtitle={strings.register.step3Title}
      >
        <View style={styles.permissionContainer}>
          <Text variant="body" align="center">
            Loading camera...
          </Text>
        </View>
      </AuthLayout>
    );
  }

  if (!permission.granted) {
    return (
      <AuthLayout
        showBack
        title={strings.auth.createAccount}
        subtitle={strings.register.step3Title}
      >
        <View style={styles.permissionContainer}>
          <Text variant="body" align="center" style={styles.permissionText}>
            Camera permission is required to register your face
          </Text>
          <Button variant="primary" onPress={requestPermission}>
            Grant Permission
          </Button>
        </View>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      showBack
      title={strings.auth.createAccount}
      subtitle={strings.register.step3Title}
    >
      <View style={styles.container}>
        {/* Progress bar */}
        <View style={styles.progressContainer}>
          <View style={[styles.progressBar, { width: '75%' }]} />
        </View>

        {/* Instruction */}
        <Text variant="body" weight="semibold" align="center" style={styles.instruction}>
          {INSTRUCTIONS[currentIndex] || INSTRUCTIONS[INSTRUCTIONS.length - 1]}
        </Text>

        {/* Camera preview */}
        <View style={styles.cameraContainer}>
          <CameraView
            ref={cameraRef}
            style={styles.camera}
            facing="front"
          >
            {/* Face oval overlay */}
            <View style={styles.overlay}>
              <View style={styles.faceGuide} />
            </View>
          </CameraView>
        </View>

        {/* Captured images thumbnails */}
        <View style={styles.thumbnailRow}>
          {Array.from({ length: REQUIRED_IMAGES }).map((_, index) => (
            <TouchableOpacity
              key={index}
              style={styles.thumbnailContainer}
              onPress={() => capturedImages[index] && handleRemoveImage(index)}
              disabled={!capturedImages[index]}
            >
              {capturedImages[index] ? (
                <Image
                  source={{ uri: capturedImages[index] }}
                  style={styles.thumbnail}
                />
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

        {/* Progress text */}
        <Text variant="bodySmall" color={theme.colors.text.secondary} align="center" style={styles.progressText}>
          Captured: {capturedImages.length}/{REQUIRED_IMAGES}
        </Text>

        {/* Capture button */}
        {capturedImages.length < REQUIRED_IMAGES && (
          <TouchableOpacity
            style={styles.captureButton}
            onPress={handleCapture}
            activeOpacity={theme.interaction.activeOpacity}
          >
            <Camera size={32} color={theme.colors.background} />
          </TouchableOpacity>
        )}

        {/* Next button */}
        {capturedImages.length === REQUIRED_IMAGES && (
          <Button
            variant="primary"
            size="lg"
            fullWidth
            onPress={handleNext}
            style={styles.nextButton}
          >
            {strings.common.next}
          </Button>
        )}
      </View>
    </AuthLayout>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  progressContainer: {
    height: 4,
    backgroundColor: theme.colors.backgroundSecondary,
    borderRadius: 2,
    marginBottom: theme.spacing[8],
  },
  progressBar: {
    height: '100%',
    backgroundColor: theme.colors.primary,
    borderRadius: 2,
  },
  instruction: {
    marginBottom: theme.spacing[6],
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
    borderWidth: 3,
    borderColor: theme.colors.background,
    borderRadius: 100,
    backgroundColor: 'transparent',
  },
  thumbnailRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: theme.spacing[4],
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
    backgroundColor: theme.colors.backgroundSecondary,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  progressText: {
    marginBottom: theme.spacing[6],
  },
  captureButton: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: theme.colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    alignSelf: 'center',
    ...theme.shadows.md,
  },
  nextButton: {
    marginTop: theme.spacing[6],
  },
  permissionContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  permissionText: {
    marginBottom: theme.spacing[6],
  },
});

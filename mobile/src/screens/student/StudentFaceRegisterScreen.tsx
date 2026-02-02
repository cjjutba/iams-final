/**
 * Student Face Register Screen
 *
 * Allows students to re-register their face
 * Same capture process as registration
 */

import React, { useState, useRef } from 'react';
import { View, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Image } from 'expo-image';
import { Camera, AlertTriangle } from 'lucide-react-native';
import { faceService } from '../../services';
import { theme, strings, config } from '../../constants';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Button, Card } from '../../components/ui';

const REQUIRED_IMAGES = config.REQUIRED_FACE_IMAGES;

const INSTRUCTIONS = [
  strings.register.faceInstructions.straight,
  strings.register.faceInstructions.left,
  strings.register.faceInstructions.right,
  strings.register.faceInstructions.up,
  strings.register.faceInstructions.down,
];

export const StudentFaceRegisterScreen: React.FC = () => {
  const navigation = useNavigation();
  const cameraRef = useRef<CameraView>(null);

  const [permission, requestPermission] = useCameraPermissions();
  const [capturedImages, setCapturedImages] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  const handleSubmit = async () => {
    Alert.alert(
      'Re-register Face',
      'This will replace your existing face registration. Continue?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Continue',
          onPress: async () => {
            try {
              setIsSubmitting(true);
              await faceService.reregisterFace(capturedImages);

              Alert.alert('Success', 'Face re-registered successfully', [
                { text: 'OK', onPress: () => navigation.goBack() },
              ]);
            } catch (error: any) {
              Alert.alert('Error', error.response?.data?.message || strings.errors.generic);
            } finally {
              setIsSubmitting(false);
            }
          },
        },
      ]
    );
  };

  if (!permission) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title={strings.student.reregisterFace} />
        <View style={styles.permissionContainer}>
          <Text variant="body" align="center">
            Loading camera...
          </Text>
        </View>
      </ScreenLayout>
    );
  }

  if (!permission.granted) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title={strings.student.reregisterFace} />
        <View style={styles.permissionContainer}>
          <Text variant="body" align="center" style={styles.permissionText}>
            Camera permission is required to register your face
          </Text>
          <Button variant="primary" onPress={requestPermission}>
            Grant Permission
          </Button>
        </View>
      </ScreenLayout>
    );
  }

  return (
    <ScreenLayout safeArea scrollable>
      <Header showBack title={strings.student.reregisterFace} />

      <View style={styles.container}>
        {/* Warning */}
        <Card variant="outlined" style={styles.warningCard}>
          <View style={styles.warningHeader}>
            <AlertTriangle size={20} color={theme.colors.status.warning} />
            <Text variant="body" weight="semibold" style={styles.warningTitle}>
              {strings.student.faceReregistrationWarning}
            </Text>
          </View>
        </Card>

        {/* Instruction */}
        <Text variant="body" weight="semibold" align="center" style={styles.instruction}>
          {INSTRUCTIONS[currentIndex] || INSTRUCTIONS[INSTRUCTIONS.length - 1]}
        </Text>

        {/* Camera preview */}
        <View style={styles.cameraContainer}>
          <CameraView ref={cameraRef} style={styles.camera} facing="front">
            <View style={styles.overlay}>
              <View style={styles.faceGuide} />
            </View>
          </CameraView>
        </View>

        {/* Thumbnails */}
        <View style={styles.thumbnailRow}>
          {Array.from({ length: REQUIRED_IMAGES }).map((_, index) => (
            <TouchableOpacity
              key={index}
              style={styles.thumbnailContainer}
              onPress={() => capturedImages[index] && handleRemoveImage(index)}
              disabled={!capturedImages[index]}
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

        {/* Progress */}
        <Text
          variant="bodySmall"
          color={theme.colors.text.secondary}
          align="center"
          style={styles.progressText}
        >
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

        {/* Submit button */}
        {capturedImages.length === REQUIRED_IMAGES && (
          <Button
            variant="primary"
            size="lg"
            fullWidth
            onPress={handleSubmit}
            loading={isSubmitting}
            style={styles.submitButton}
          >
            {strings.common.save}
          </Button>
        )}
      </View>
    </ScreenLayout>
  );
};

const styles = StyleSheet.create({
  container: {
    padding: theme.spacing[4],
  },
  warningCard: {
    marginBottom: theme.spacing[6],
  },
  warningHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  warningTitle: {
    marginLeft: theme.spacing[2],
    flex: 1,
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
  submitButton: {
    marginTop: theme.spacing[6],
  },
  permissionContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing[4],
  },
  permissionText: {
    marginBottom: theme.spacing[6],
  },
});

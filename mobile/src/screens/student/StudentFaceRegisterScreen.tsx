/**
 * Student Face Register Screen
 *
 * Allows students to register or re-register their face:
 * - Camera capture with face guide overlay
 * - Captures required number of images (5) at different angles
 * - Thumbnail preview with ability to retake
 * - Submits to POST /face/register or /face/reregister based on mode
 * - Shows progress, success/error/loading feedback
 */

import React, { useState, useRef, useCallback } from 'react';
import { View, StyleSheet, TouchableOpacity, Alert, ActivityIndicator } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Image } from 'expo-image';
import { Camera, AlertTriangle } from 'lucide-react-native';
import { faceService } from '../../services';
import { theme, strings, config } from '../../constants';
import { getErrorMessage } from '../../utils';
import type { StudentStackParamList } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Button, Card } from '../../components/ui';

type FaceRegisterRouteProp = RouteProp<StudentStackParamList, 'FaceRegister'>;

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
  const route = useRoute<FaceRegisterRouteProp>();
  const mode = route.params?.mode || 'reregister';

  const cameraRef = useRef<CameraView>(null);

  const [permission, requestPermission] = useCameraPermissions();
  const [capturedImages, setCapturedImages] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);

  // ---------- capture photo ----------

  const handleCapture = useCallback(async () => {
    if (!cameraRef.current || isCapturing) return;

    try {
      setIsCapturing(true);
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
      Alert.alert('Error', 'Failed to capture photo. Please try again.');
    } finally {
      setIsCapturing(false);
    }
  }, [capturedImages, isCapturing]);

  // ---------- remove image ----------

  const handleRemoveImage = useCallback(
    (index: number) => {
      Alert.alert('Remove Photo', 'Remove this photo and retake?', [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: () => {
            const newImages = capturedImages.filter((_, i) => i !== index);
            setCapturedImages(newImages);
            setCurrentIndex(newImages.length);
          },
        },
      ]);
    },
    [capturedImages]
  );

  // ---------- submit images ----------

  const handleSubmit = useCallback(async () => {
    const confirmTitle = mode === 'register' ? 'Register Face' : 'Re-register Face';
    const confirmMessage =
      mode === 'register'
        ? 'Submit your face photos for registration?'
        : 'This will replace your existing face registration. Continue?';

    Alert.alert(confirmTitle, confirmMessage, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Continue',
        onPress: async () => {
          try {
            setIsSubmitting(true);

            if (mode === 'register') {
              await faceService.registerFace(capturedImages);
            } else {
              await faceService.reregisterFace(capturedImages);
            }

            Alert.alert(
              'Success',
              mode === 'register'
                ? 'Face registered successfully'
                : 'Face re-registered successfully',
              [{ text: 'OK', onPress: () => navigation.goBack() }]
            );
          } catch (error: unknown) {
            const message = getErrorMessage(error);
            Alert.alert('Error', message);
          } finally {
            setIsSubmitting(false);
          }
        },
      },
    ]);
  }, [mode, capturedImages, navigation]);

  // ---------- permission loading ----------

  if (!permission) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title={strings.student.reregisterFace} />
        <View style={styles.permissionContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text
            variant="bodySmall"
            color={theme.colors.text.secondary}
            align="center"
            style={styles.permissionText}
          >
            Loading camera...
          </Text>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- permission denied ----------

  if (!permission.granted) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title={strings.student.reregisterFace} />
        <View style={styles.permissionContainer}>
          <Camera size={48} color={theme.colors.text.tertiary} style={styles.permissionIcon} />
          <Text
            variant="body"
            align="center"
            style={styles.permissionText}
          >
            Camera permission is required to register your face
          </Text>
          <Text
            variant="bodySmall"
            color={theme.colors.text.secondary}
            align="center"
            style={styles.permissionSubtext}
          >
            We need access to your camera to capture face photos for attendance recognition
          </Text>
          <Button variant="primary" onPress={requestPermission} style={styles.permissionButton}>
            Grant Camera Permission
          </Button>
        </View>
      </ScreenLayout>
    );
  }

  // ---------- screen title ----------

  const screenTitle =
    mode === 'register' ? 'Register Face' : strings.student.reregisterFace;

  // ---------- main render ----------

  return (
    <ScreenLayout safeArea scrollable>
      <Header showBack title={screenTitle} />

      <View style={styles.container}>
        {/* Warning (only for re-registration) */}
        {mode === 'reregister' && (
          <Card variant="outlined" style={styles.warningCard}>
            <View style={styles.warningHeader}>
              <AlertTriangle size={20} color={theme.colors.warning} />
              <Text variant="body" weight="600" style={styles.warningTitle}>
                {strings.student.faceReregistrationWarning}
              </Text>
            </View>
          </Card>
        )}

        {/* Instruction */}
        <Text variant="body" weight="600" align="center" style={styles.instruction}>
          {INSTRUCTIONS[currentIndex] || INSTRUCTIONS[INSTRUCTIONS.length - 1]}
        </Text>

        {/* Camera preview */}
        {capturedImages.length < REQUIRED_IMAGES && (
          <View style={styles.cameraContainer}>
            <CameraView ref={cameraRef} style={styles.camera} facing="front">
              <View style={styles.overlay}>
                <View style={styles.faceGuide} />
              </View>
            </CameraView>
          </View>
        )}

        {/* All captured message */}
        {capturedImages.length >= REQUIRED_IMAGES && (
          <View style={styles.completedContainer}>
            <Text variant="h3" weight="700" align="center" style={styles.completedTitle}>
              All photos captured
            </Text>
            <Text
              variant="bodySmall"
              color={theme.colors.text.secondary}
              align="center"
              style={styles.completedSubtext}
            >
              Review your photos below. Tap any photo to remove and retake it.
            </Text>
          </View>
        )}

        {/* Thumbnails */}
        <View style={styles.thumbnailRow}>
          {Array.from({ length: REQUIRED_IMAGES }).map((_, index) => (
            <TouchableOpacity
              key={index}
              style={[
                styles.thumbnailContainer,
                index === currentIndex &&
                  capturedImages.length < REQUIRED_IMAGES &&
                  styles.thumbnailActive,
              ]}
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
            style={[styles.captureButton, isCapturing && styles.captureButtonDisabled]}
            onPress={handleCapture}
            activeOpacity={theme.interaction.activeOpacity}
            disabled={isCapturing}
          >
            {isCapturing ? (
              <ActivityIndicator size="small" color={theme.colors.primaryForeground} />
            ) : (
              <Camera size={32} color={theme.colors.primaryForeground} />
            )}
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
            {mode === 'register' ? 'Register Face' : 'Re-register Face'}
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
  completedContainer: {
    paddingVertical: theme.spacing[8],
    marginBottom: theme.spacing[6],
  },
  completedTitle: {
    marginBottom: theme.spacing[2],
  },
  completedSubtext: {
    // no additional style needed
  },
  thumbnailRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: theme.spacing[4],
  },
  thumbnailContainer: {
    marginHorizontal: theme.spacing[1],
    borderRadius: theme.borderRadius.md,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  thumbnailActive: {
    borderColor: theme.colors.primary,
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
  captureButtonDisabled: {
    opacity: theme.interaction.disabledOpacity,
  },
  submitButton: {
    marginTop: theme.spacing[6],
  },
  permissionContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing[6],
  },
  permissionIcon: {
    marginBottom: theme.spacing[4],
  },
  permissionText: {
    marginBottom: theme.spacing[3],
  },
  permissionSubtext: {
    marginBottom: theme.spacing[6],
  },
  permissionButton: {
    // no additional style
  },
});

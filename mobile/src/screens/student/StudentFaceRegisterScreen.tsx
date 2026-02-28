/**
 * Student Face Register Screen
 *
 * Allows students to register or re-register their face from their profile.
 * Uses the shared FaceScanCamera for iPhone Face ID-style continuous capture.
 */

import React, { useState, useCallback } from 'react';
import { View, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import { useCameraPermissions } from 'expo-camera';
import { Camera } from 'lucide-react-native';
import { faceService } from '../../services';
import { theme, strings } from '../../constants';
import { getErrorMessage } from '../../utils';
import type { StudentStackParamList } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Button } from '../../components/ui';
import { FaceScanCamera } from '../../components/face';

type FaceRegisterRouteProp = RouteProp<StudentStackParamList, 'FaceRegister'>;

export const StudentFaceRegisterScreen: React.FC = () => {
  const navigation = useNavigation();
  const route = useRoute<FaceRegisterRouteProp>();
  const mode = route.params?.mode || 'reregister';

  const [permission, requestPermission] = useCameraPermissions();
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ── Handle scan complete ───────────────────────────────────

  const handleScanComplete = useCallback(async (images: string[]) => {
    try {
      setIsSubmitting(true);

      if (mode === 'register') {
        await faceService.registerFace(images);
      } else {
        await faceService.reregisterFace(images);
      }

      Alert.alert(
        'Success',
        mode === 'register'
          ? 'Face registered successfully'
          : 'Face re-registered successfully',
        [{ text: 'OK', onPress: () => navigation.goBack() }],
      );
    } catch (error: unknown) {
      const message = getErrorMessage(error);
      Alert.alert('Error', message, [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } finally {
      setIsSubmitting(false);
    }
  }, [mode, navigation]);

  // ── Permission loading ─────────────────────────────────────

  if (!permission) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title={strings.student.reregisterFace} />
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text
            variant="bodySmall"
            color={theme.colors.text.secondary}
            align="center"
            style={styles.centerText}
          >
            Loading camera...
          </Text>
        </View>
      </ScreenLayout>
    );
  }

  // ── Permission denied ──────────────────────────────────────

  if (!permission.granted) {
    return (
      <ScreenLayout safeArea>
        <Header showBack title={strings.student.reregisterFace} />
        <View style={styles.centerContainer}>
          <Camera size={48} color={theme.colors.text.tertiary} style={styles.icon} />
          <Text variant="body" align="center" style={styles.centerText}>
            Camera permission is required to register your face
          </Text>
          <Text
            variant="bodySmall"
            color={theme.colors.text.secondary}
            align="center"
            style={styles.subtext}
          >
            We need access to your camera to capture face photos for attendance recognition
          </Text>
          <Button variant="primary" onPress={requestPermission}>
            Grant Camera Permission
          </Button>
        </View>
      </ScreenLayout>
    );
  }

  // ── Submitting overlay ─────────────────────────────────────

  if (isSubmitting) {
    return (
      <View style={styles.submittingRoot}>
        <ActivityIndicator size="large" color="#FFFFFF" />
        <Text variant="body" color="#FFFFFF" align="center" style={styles.centerText}>
          Processing your face data...
        </Text>
      </View>
    );
  }

  // ── Main: FaceScanCamera ───────────────────────────────────

  return <FaceScanCamera onComplete={handleScanComplete} />;
};

const styles = StyleSheet.create({
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing[6],
  },
  centerText: {
    marginTop: theme.spacing[3],
    marginBottom: theme.spacing[3],
  },
  subtext: {
    marginBottom: theme.spacing[6],
  },
  icon: {
    marginBottom: theme.spacing[4],
  },
  submittingRoot: {
    flex: 1,
    backgroundColor: '#000',
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing[6],
  },
});

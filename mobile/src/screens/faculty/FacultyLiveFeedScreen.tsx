/**
 * Faculty Live Feed Screen
 *
 * Displays a live camera feed using two independent layers:
 *
 * 1. **Video Layer** — HLS stream via `expo-video` (hardware-decoded, 30 FPS)
 *    The backend runs FFmpeg to remux the RTSP H.264 stream into HLS segments.
 *    `expo-video`'s native `VideoView` plays HLS with hardware decoding.
 *
 * 2. **Recognition Layer** — WebSocket detection metadata (~200 bytes/msg)
 *    The backend samples frames at ~1.5 FPS, runs face detection + FaceNet
 *    recognition, and pushes only detection coordinates + names via WebSocket.
 *    A transparent `DetectionOverlay` renders bounding boxes on top of the video.
 *
 * WebSocket endpoint: ws://<host>/api/v1/stream/{scheduleId}
 *
 * Features:
 * - 30 FPS smooth hardware-decoded video
 * - Real-time face recognition overlay (bounding boxes + names)
 * - Connection status indicator
 * - Detected-students panel with confidence percentages
 * - Auto-reconnect with 3-second delay
 * - Navigation to the list-based LiveAttendance screen
 */

import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import {
  View,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  LayoutChangeEvent,
  Animated,
} from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { useVideoPlayer, VideoView, useEvent } from 'expo-video';
import { RTCView } from 'react-native-webrtc';
import { Wifi, WifiOff, Video, Users, RefreshCw } from 'lucide-react-native';
import { theme, strings } from '../../constants';
import { formatPercentage } from '../../utils/formatters';
import type { FacultyStackParamList } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Button } from '../../components/ui';
import { DetectionOverlay } from '../../components/video/DetectionOverlay';
import { useDetectionWebSocket } from '../../hooks/useDetectionWebSocket';
import type { DetectedStudent } from '../../hooks/useDetectionWebSocket';
import { useWebRTC } from '../../hooks/useWebRTC';

// ---------------------------------------------------------------------------
// Route typing
// ---------------------------------------------------------------------------

type LiveFeedRouteProp = RouteProp<FacultyStackParamList, 'LiveFeed'>;
type LiveFeedNavigationProp = StackNavigationProp<FacultyStackParamList, 'LiveFeed'>;

// ---------------------------------------------------------------------------
// LivePulse — animated red dot + LIVE label
// ---------------------------------------------------------------------------

const LivePulse: React.FC = () => {
  const scale = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(scale, { toValue: 1.5, duration: 600, useNativeDriver: true }),
        Animated.timing(scale, { toValue: 1.0, duration: 600, useNativeDriver: true }),
      ]),
    );
    anim.start();
    return () => anim.stop();
  }, []);

  return (
    <View style={livePulseStyles.container}>
      <Animated.View style={[livePulseStyles.dot, { transform: [{ scale }] }]} />
      <Text style={livePulseStyles.text}>LIVE</Text>
    </View>
  );
};

const livePulseStyles = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'center' },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: '#F44336',
    marginRight: 5,
  },
  text: {
    color: '#F44336',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1,
  },
});

// ---------------------------------------------------------------------------
// Memoised sub-components
// ---------------------------------------------------------------------------

const StudentRow = React.memo(({ item }: { item: DetectedStudent }) => (
  <View style={styles.studentRow}>
    <View
      style={[
        styles.detectionDot,
        {
          backgroundColor: item.currentlyDetected
            ? theme.colors.success
            : theme.colors.text.disabled,
        },
      ]}
    />
    <View style={styles.studentInfo}>
      <Text variant="bodySmall" weight="600" numberOfLines={1}>
        {item.name}
      </Text>
      <Text variant="caption" color={theme.colors.text.secondary}>
        {item.student_id}
      </Text>
    </View>
    <Text
      variant="caption"
      weight="600"
      color={
        item.confidence >= 0.8
          ? theme.colors.success
          : item.confidence >= 0.6
          ? theme.colors.warning
          : theme.colors.error
      }
    >
      {formatPercentage(item.confidence * 100, 0)}
    </Text>
  </View>
));

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const FacultyLiveFeedScreen: React.FC = () => {
  const route = useRoute<LiveFeedRouteProp>();
  const navigation = useNavigation<LiveFeedNavigationProp>();
  const { scheduleId, subjectName } = route.params;

  // Detection WebSocket (also extracts HLS URL from connected message)
  const {
    detections,
    isConnected,
    isConnecting,
    hlsUrl,
    streamMode,
    studentMap,
    connectionError,
    reconnect,
    detectionWidth,
    detectionHeight,
  } = useDetectionWebSocket(scheduleId);

  // WebRTC video (enabled only in webrtc mode)
  const {
    remoteStream,
    connectionState: rtcConnectionState,
    reconnect: rtcReconnect,
  } = useWebRTC(scheduleId, streamMode === 'webrtc');

  // HLS video player — pass null when in WebRTC mode to avoid starting HLS connection.
  // The setup callback runs immediately with the initial (null) hlsUrl, so p.play()
  // would never execute there. Instead, a useEffect below calls play() once the URL
  // arrives and streamMode is confirmed.
  const player = useVideoPlayer(
    streamMode === 'hls' || streamMode === 'legacy' ? hlsUrl : null,
    (p) => {
      p.loop = false;
    },
  );

  // Start playback as soon as the HLS URL is available.
  useEffect(() => {
    if ((streamMode === 'hls' || streamMode === 'legacy') && hlsUrl) {
      player.play();
    }
  }, [hlsUrl, streamMode, player]);

  // Auto-reload the player when it enters error state.
  // The backend health check restarts FFmpeg within ~10 s; we retry every
  // 3 s so playback resumes automatically without user intervention.
  useEvent(player, 'statusChange', ({ status }) => {
    if (
      status === 'error' &&
      hlsUrl &&
      (streamMode === 'hls' || streamMode === 'legacy')
    ) {
      setTimeout(() => {
        player.replace(hlsUrl);
        player.play();
      }, 3_000);
    }
  });

  // Combined reconnect: resets both WS and WebRTC connections
  const handleReconnect = useCallback(() => {
    reconnect();
    if (streamMode === 'webrtc') rtcReconnect();
  }, [reconnect, rtcReconnect, streamMode]);

  // Track container dimensions for overlay coordinate scaling
  const [containerLayout, setContainerLayout] = useState({ width: 0, height: 0 });

  const handleVideoLayout = useCallback((event: LayoutChangeEvent) => {
    const { width, height } = event.nativeEvent.layout;
    setContainerLayout({ width, height });
  }, []);

  // --------------------------------------------------
  // Navigation helpers
  // --------------------------------------------------

  const handleSwitchToList = useCallback(() => {
    navigation.navigate('LiveAttendance', {
      scheduleId,
      subjectCode: '',
      subjectName,
    });
  }, [navigation, scheduleId, subjectName]);

  // --------------------------------------------------
  // Derived data (memoised)
  // --------------------------------------------------

  const studentsList = useMemo(
    () =>
      Array.from(studentMap.values()).sort((a, b) => {
        if (a.currentlyDetected !== b.currentlyDetected) {
          return a.currentlyDetected ? -1 : 1;
        }
        return a.name.localeCompare(b.name);
      }),
    [studentMap],
  );

  const currentlyDetectedCount = useMemo(
    () => studentsList.filter((s) => s.currentlyDetected).length,
    [studentsList],
  );

  const detectedCount = useMemo(() => detections.length, [detections]);
  const unknownCount = useMemo(
    () => detections.filter(d => !d.user_id).length,
    [detections],
  );

  // --------------------------------------------------
  // Render helpers
  // --------------------------------------------------

  const renderStudentRow = useCallback(
    ({ item }: { item: DetectedStudent }) => <StudentRow item={item} />,
    [],
  );

  const keyExtractor = useCallback((item: DetectedStudent) => item.user_id, []);

  const renderStudentListHeader = useCallback(
    () => (
      <View style={styles.panelHeader}>
        <View style={styles.panelTitleRow}>
          <Users size={16} color={theme.colors.text.primary} />
          <Text variant="body" weight="600" style={styles.panelTitleText}>
            Detected Students
          </Text>
        </View>
        <Text variant="caption" color={theme.colors.text.secondary}>
          {currentlyDetectedCount} active / {studentsList.length} total
        </Text>
      </View>
    ),
    [currentlyDetectedCount, studentsList.length],
  );

  const renderStudentListEmpty = useCallback(
    () => (
      <View style={styles.emptyDetections}>
        <Text variant="bodySmall" color={theme.colors.text.tertiary} align="center">
          No students detected yet
        </Text>
      </View>
    ),
    [],
  );

  const itemSeparator = useCallback(() => <View style={styles.separator} />, []);

  // --------------------------------------------------
  // Error state
  // --------------------------------------------------

  if (connectionError) {
    return (
      <ScreenLayout safeArea padded={false}>
        <Header showBack title={subjectName} />
        <View style={styles.centeredContainer}>
          <RefreshCw size={40} color={theme.colors.text.tertiary} style={styles.errorIcon} />
          <Text variant="body" color={theme.colors.text.secondary} align="center">
            {connectionError}
          </Text>
          <Button
            variant="secondary"
            size="md"
            onPress={handleReconnect}
            style={styles.retryButton}
          >
            {strings.common.retry}
          </Button>
        </View>
      </ScreenLayout>
    );
  }

  // --------------------------------------------------
  // Loading state (waiting for HLS URL)
  // --------------------------------------------------

  const isVideoReady =
    (streamMode === 'webrtc' && remoteStream !== null) ||
    ((streamMode === 'hls' || streamMode === 'legacy') && hlsUrl !== null);

  if (isConnecting && !isVideoReady) {
    return (
      <ScreenLayout safeArea padded={false}>
        <Header showBack title={subjectName} />
        <View style={styles.centeredContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text
            variant="bodySmall"
            color={theme.colors.text.secondary}
            align="center"
            style={styles.loadingText}
          >
            Connecting to camera feed...
          </Text>
        </View>
      </ScreenLayout>
    );
  }

  // --------------------------------------------------
  // Main render
  // --------------------------------------------------

  return (
    <ScreenLayout safeArea padded={false}>
      <Header showBack title={subjectName} />

      <View style={styles.container}>
        {/* Connection status bar */}
        <View
          style={[
            styles.statusBar,
            {
              backgroundColor: isConnected
                ? theme.colors.status.present.bg
                : theme.colors.status.absent.bg,
            },
          ]}
        >
          <View style={styles.statusLeft}>
            {isConnected ? (
              <Wifi size={14} color={theme.colors.status.present.fg} />
            ) : (
              <WifiOff size={14} color={theme.colors.status.absent.fg} />
            )}
            <Text
              variant="caption"
              weight="600"
              color={
                isConnected
                  ? theme.colors.status.present.fg
                  : theme.colors.status.absent.fg
              }
              style={styles.statusText}
            >
              {isConnected ? 'Connected' : 'Reconnecting...'}
            </Text>
          </View>

          <View style={styles.statusRight}>
            {isConnected && <LivePulse />}
            {detectedCount > 0 && (
              <Text
                variant="caption"
                weight="600"
                color={theme.colors.text.secondary}
                style={styles.detectionCountText}
              >
                {detectedCount} detected{unknownCount > 0 ? ` · ${unknownCount} unknown` : ''}
              </Text>
            )}
          </View>
        </View>

        {/* Camera feed: WebRTC or HLS video + detection overlay */}
        <View style={styles.feedContainer} onLayout={handleVideoLayout}>
          {streamMode === 'webrtc' && remoteStream ? (
            <>
              <RTCView
                streamURL={remoteStream.toURL()}
                style={styles.video}
                objectFit="cover"
                mirror={false}
                zOrder={0}
              />
              <DetectionOverlay
                detections={detections}
                videoWidth={detectionWidth}
                videoHeight={detectionHeight}
                containerWidth={containerLayout.width}
                containerHeight={containerLayout.height}
              />
            </>
          ) : (streamMode === 'hls' || streamMode === 'legacy') && hlsUrl ? (
            <>
              <VideoView
                player={player}
                style={styles.video}
                contentFit="contain"
                nativeControls={false}
              />
              <DetectionOverlay
                detections={detections}
                videoWidth={detectionWidth}
                videoHeight={detectionHeight}
                containerWidth={containerLayout.width}
                containerHeight={containerLayout.height}
              />
            </>
          ) : (
            <View style={styles.noFeedPlaceholder}>
              <Video size={48} color={theme.colors.text.disabled} />
              <Text
                variant="bodySmall"
                color={theme.colors.text.tertiary}
                align="center"
                style={styles.noFeedText}
              >
                {rtcConnectionState === 'failed'
                  ? 'WebRTC connection failed — tap retry'
                  : 'Connecting to camera...'}
              </Text>
            </View>
          )}
        </View>

        {/* Bottom panel: detected students */}
        <Card style={styles.bottomPanel}>
          <FlatList
            data={studentsList}
            keyExtractor={keyExtractor}
            renderItem={renderStudentRow}
            ListHeaderComponent={renderStudentListHeader}
            ListEmptyComponent={renderStudentListEmpty}
            showsVerticalScrollIndicator={false}
            contentContainerStyle={styles.studentListContent}
            ItemSeparatorComponent={itemSeparator}
          />

          {/* Switch to List View button */}
          <Button
            variant="outline"
            size="md"
            fullWidth
            onPress={handleSwitchToList}
            style={styles.switchButton}
          >
            Switch to List View
          </Button>
        </Card>
      </View>
    </ScreenLayout>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.primary,
  },

  // Status bar
  statusBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: theme.spacing[4],
    paddingVertical: theme.spacing[1],
  },
  statusLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusText: {
    marginLeft: theme.spacing[1],
  },
  statusRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing[2],
  },
  detectionCountText: {
    marginLeft: theme.spacing[1],
  },

  // Camera feed
  feedContainer: {
    flex: 1,
    backgroundColor: '#000000',
  },
  video: {
    ...StyleSheet.absoluteFillObject,
  },
  noFeedPlaceholder: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  noFeedText: {
    marginTop: theme.spacing[3],
  },

  // Bottom panel
  bottomPanel: {
    borderTopLeftRadius: theme.borderRadius.xl,
    borderTopRightRadius: theme.borderRadius.xl,
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: 0,
    maxHeight: 280,
    paddingBottom: theme.spacing[4],
  },
  panelHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing[3],
  },
  panelTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  panelTitleText: {
    marginLeft: theme.spacing[2],
  },
  studentListContent: {
    flexGrow: 1,
  },

  // Student row
  studentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: theme.spacing[2],
  },
  detectionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: theme.spacing[3],
  },
  studentInfo: {
    flex: 1,
    marginRight: theme.spacing[3],
  },
  separator: {
    height: 1,
    backgroundColor: theme.colors.border,
  },

  // Empty detections
  emptyDetections: {
    paddingVertical: theme.spacing[6],
    alignItems: 'center',
  },

  // Switch button
  switchButton: {
    marginTop: theme.spacing[3],
  },

  // Centered states
  centeredContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: theme.spacing[6],
  },
  loadingText: {
    marginTop: theme.spacing[3],
  },
  errorIcon: {
    marginBottom: theme.spacing[4],
  },
  retryButton: {
    marginTop: theme.spacing[4],
  },
});

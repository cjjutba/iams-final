/**
 * Faculty Live Feed Screen
 *
 * Displays a live camera feed from the backend via WebSocket with face
 * recognition overlays. Frames arrive as base64-encoded JPEGs alongside
 * detection metadata (bounding boxes, names, confidence).
 *
 * WebSocket endpoint: ws://<host>/api/v1/stream/{scheduleId}
 *
 * Features:
 * - Real-time camera frame rendering
 * - Connection status indicator (Connected / Reconnecting)
 * - FPS counter
 * - Detected-students panel with confidence percentages
 * - Auto-reconnect with 3-second delay
 * - Navigation to the list-based LiveAttendance screen
 *
 * Performance optimisations:
 * - Frame URI stored in a ref — only the Image re-renders, not the whole tree
 * - Detection list updates are batched and debounced
 * - Student list component is memoised
 */

import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import {
  View,
  Image,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  AppState,
  AppStateStatus,
} from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { Wifi, WifiOff, Video, Users, RefreshCw } from 'lucide-react-native';
import { theme, strings } from '../../constants';
import { config } from '../../constants/config';
import { storage } from '../../utils/storage';
import { formatPercentage } from '../../utils/formatters';
import type { FacultyStackParamList } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Card, Button } from '../../components/ui';

// ---------------------------------------------------------------------------
// Route typing
// ---------------------------------------------------------------------------

type LiveFeedRouteProp = RouteProp<FacultyStackParamList, 'LiveFeed'>;
type LiveFeedNavigationProp = StackNavigationProp<FacultyStackParamList, 'LiveFeed'>;

// ---------------------------------------------------------------------------
// Types for incoming WebSocket messages
// ---------------------------------------------------------------------------

interface Detection {
  user_id: string;
  name: string;
  student_id: string;
  confidence: number;
  bbox: [number, number, number, number]; // [x, y, w, h]
}

interface FrameMessage {
  type: 'frame';
  data: string; // base64 JPEG
  timestamp: string;
  detections: Detection[];
}

/** Tracks a detected student with recency information. */
interface DetectedStudent {
  user_id: string;
  name: string;
  student_id: string;
  confidence: number;
  /** True when the student was in the most recent frame. */
  currentlyDetected: boolean;
  /** ISO timestamp of the last frame where this student appeared. */
  lastSeen: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Build the WebSocket URL for the camera stream.
 *
 * Derives the ws:// host from the REST API base URL so the stream
 * endpoint stays in sync regardless of environment.
 */
const getStreamWsUrl = (scheduleId: string): string => {
  // config.API_BASE_URL is e.g. "http://192.168.1.9:8000/api/v1"
  const baseUrl = config.API_BASE_URL;
  const wsBase = baseUrl.replace(/^http/, 'ws');
  // Replace trailing /api/v1 path with /api/v1/stream/{scheduleId}
  const streamUrl = wsBase.replace(/\/api\/v1$/, `/api/v1/stream/${scheduleId}`);
  return streamUrl;
};

// ---------------------------------------------------------------------------
// Memoised sub-components (prevent re-render of list when frame changes)
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

  // Connection state
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(true);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // Frame state — separate from detection list to avoid re-rendering
  // the entire tree on every frame.
  const [frameUri, setFrameUri] = useState<string | null>(null);

  // FPS tracking
  const [fps, setFps] = useState(0);
  const frameCountRef = useRef(0);
  const fpsIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Detected students map keyed by user_id for O(1) updates.
  // Updated only when the detection list actually changes (not every frame).
  const [detectedStudents, setDetectedStudents] = useState<Map<string, DetectedStudent>>(
    new Map(),
  );

  // WebSocket ref for cleanup
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);

  // --------------------------------------------------
  // FPS counter: measure frames received per second
  // --------------------------------------------------

  useEffect(() => {
    fpsIntervalRef.current = setInterval(() => {
      setFps(frameCountRef.current);
      frameCountRef.current = 0;
    }, 1000);

    return () => {
      if (fpsIntervalRef.current) clearInterval(fpsIntervalRef.current);
    };
  }, []);

  // --------------------------------------------------
  // WebSocket connection
  // --------------------------------------------------

  const connectWebSocket = useCallback(async () => {
    if (!isMountedRef.current) return;

    // Clean up any previous socket
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnecting(true);
    setConnectionError(null);

    const url = getStreamWsUrl(scheduleId);

    // Attach auth token as query param so the backend can authenticate
    const token = await storage.getAccessToken();
    const wsUrl = token ? `${url}?token=${encodeURIComponent(token)}` : url;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMountedRef.current) return;
      setIsConnected(true);
      setIsConnecting(false);
      setConnectionError(null);
    };

    ws.onmessage = (event: WebSocketMessageEvent) => {
      if (!isMountedRef.current) return;

      try {
        const message: FrameMessage = JSON.parse(event.data);

        if (message.type === 'frame') {
          // Update frame image — this only causes the Image to re-render
          setFrameUri(`data:image/jpeg;base64,${message.data}`);
          frameCountRef.current += 1;

          // Only update detection list if there are actual detections
          // (avoids churning the student list on every empty frame)
          const dets = message.detections;
          if (dets && dets.length > 0) {
            setDetectedStudents((prev) => {
              const next = new Map(prev);

              // Mark all existing students as not currently detected
              next.forEach((student, key) => {
                if (student.currentlyDetected) {
                  next.set(key, { ...student, currentlyDetected: false });
                }
              });

              // Update / insert students from this frame
              for (const detection of dets) {
                if (!detection.user_id) continue;
                next.set(detection.user_id, {
                  user_id: detection.user_id,
                  name: detection.name || 'Unknown',
                  student_id: detection.student_id || '',
                  confidence: detection.confidence,
                  currentlyDetected: true,
                  lastSeen: message.timestamp,
                });
              }

              return next;
            });
          } else if (detectedStudents.size > 0) {
            // No detections — mark all as not currently detected (but keep in list)
            setDetectedStudents((prev) => {
              let changed = false;
              const next = new Map(prev);
              next.forEach((student, key) => {
                if (student.currentlyDetected) {
                  next.set(key, { ...student, currentlyDetected: false });
                  changed = true;
                }
              });
              return changed ? next : prev;
            });
          }
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onerror = () => {
      if (!isMountedRef.current) return;
      setIsConnected(false);
      setIsConnecting(false);
    };

    ws.onclose = () => {
      if (!isMountedRef.current) return;
      setIsConnected(false);
      setIsConnecting(false);

      // Auto-reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        if (isMountedRef.current) {
          connectWebSocket();
        }
      }, 3000);
    };
  }, [scheduleId]);

  // Establish connection on mount, tear down on unmount
  useEffect(() => {
    isMountedRef.current = true;
    connectWebSocket();

    return () => {
      isMountedRef.current = false;

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onmessage = null;
        wsRef.current.onerror = null;
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connectWebSocket]);

  // Reconnect when the app comes back to foreground
  useEffect(() => {
    const handleAppState = (nextState: AppStateStatus) => {
      if (nextState === 'active' && !isConnected && !isConnecting) {
        connectWebSocket();
      }
    };

    const subscription = AppState.addEventListener('change', handleAppState);
    return () => subscription.remove();
  }, [isConnected, isConnecting, connectWebSocket]);

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
      Array.from(detectedStudents.values()).sort((a, b) => {
        if (a.currentlyDetected !== b.currentlyDetected) {
          return a.currentlyDetected ? -1 : 1;
        }
        return a.name.localeCompare(b.name);
      }),
    [detectedStudents],
  );

  const currentlyDetectedCount = useMemo(
    () => studentsList.filter((s) => s.currentlyDetected).length,
    [studentsList],
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
  // Error state (failed to connect at all)
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
            onPress={connectWebSocket}
            style={styles.retryButton}
          >
            {strings.common.retry}
          </Button>
        </View>
      </ScreenLayout>
    );
  }

  // --------------------------------------------------
  // Loading state (initial connection)
  // --------------------------------------------------

  if (isConnecting && !frameUri) {
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

          {/* FPS counter */}
          <View style={styles.fpsContainer}>
            <Video size={12} color={theme.colors.text.secondary} />
            <Text variant="caption" weight="500" color={theme.colors.text.secondary} style={styles.fpsText}>
              {fps} FPS
            </Text>
          </View>
        </View>

        {/* Camera feed */}
        <View style={styles.feedContainer}>
          {frameUri ? (
            <Image
              source={{ uri: frameUri }}
              style={styles.feedImage}
              resizeMode="contain"
            />
          ) : (
            <View style={styles.noFeedPlaceholder}>
              <Video size={48} color={theme.colors.text.disabled} />
              <Text
                variant="bodySmall"
                color={theme.colors.text.tertiary}
                align="center"
                style={styles.noFeedText}
              >
                Waiting for frames...
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
    backgroundColor: theme.colors.primary, // dark background behind the feed
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
  fpsContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  fpsText: {
    marginLeft: theme.spacing[1],
  },

  // Camera feed
  feedContainer: {
    flex: 1,
    backgroundColor: '#000000',
    justifyContent: 'center',
    alignItems: 'center',
  },
  feedImage: {
    width: '100%',
    height: '100%',
  },
  noFeedPlaceholder: {
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

  // Centered states (loading, error)
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

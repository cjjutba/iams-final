/**
 * useNotificationWebSocket Hook
 *
 * Sits at the navigator level to subscribe to all WebSocket events
 * and dispatch toast notifications + update unread badge count.
 *
 * This hook should be called once in each navigator (StudentNavigator, FacultyNavigator)
 * so it runs for the entire authenticated session.
 */

import { useWebSocket } from './useWebSocket';
import { useToast } from './useToast';
import { useNotificationStore } from '../stores/notificationStore';
import { useAuth } from './useAuth';

export const useNotificationWebSocket = () => {
  const { showSuccess, showWarning, showInfo, showError } = useToast();
  const incrementUnreadCount = useNotificationStore(
    (s) => s.incrementUnreadCount,
  );
  const { user } = useAuth();
  const isFaculty = user?.role === 'faculty';

  useWebSocket({
    onAttendanceUpdate: (msg) => {
      if (isFaculty) {
        showInfo(
          `${msg.data?.student_name ?? 'Student'} marked ${msg.data?.status ?? 'present'}`,
          'Attendance Update',
        );
      }
    },

    onEarlyLeave: (msg) => {
      incrementUnreadCount();
      if (isFaculty) {
        showWarning(
          `${msg.data?.student_name ?? 'Student'} left ${msg.data?.subject_code ?? 'class'} early`,
          'Early Leave Detected',
        );
      }
    },

    onSessionStart: (msg) => {
      showInfo(
        `${msg.data?.subject_name ?? 'Class'} has started`,
        'Session Started',
      );
    },

    onSessionEnd: (msg) => {
      showInfo(
        `${msg.data?.subject_name ?? 'Class'} has ended`,
        'Session Ended',
      );
    },

    onPresenceWarning: (msg) => {
      if (!isFaculty) {
        showWarning(
          msg.data?.message || 'Your presence was not detected',
          'Presence Warning',
        );
      }
    },

    onStudentCheckedIn: () => {
      if (!isFaculty) {
        incrementUnreadCount();
        showSuccess('Your attendance has been recorded', 'Checked In');
      }
    },
  });
};

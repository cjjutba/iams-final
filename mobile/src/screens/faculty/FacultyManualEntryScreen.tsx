/**
 * Faculty Manual Entry Screen
 *
 * Allows faculty to manually mark student attendance.
 * Uses form validation via react-hook-form + zod.
 * Submits to POST /attendance/manual via attendanceService.
 */

import React, { useState } from 'react';
import { View, StyleSheet, Alert } from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { attendanceService } from '../../services';
import { theme, strings } from '../../constants';
import { getErrorMessage } from '../../utils';
import { AttendanceStatus } from '../../types';
import type { FacultyStackParamList } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Button } from '../../components/ui';
import { FormInput, FormSelect } from '../../components/forms';

type ManualEntryRouteProp = RouteProp<FacultyStackParamList, 'ManualEntry'>;

const manualEntrySchema = z.object({
  studentId: z.string().min(1, 'Student ID is required'),
  status: z.nativeEnum(AttendanceStatus, {
    errorMap: () => ({ message: 'Please select a status' }),
  }),
  remarks: z.string().optional(),
});

type ManualEntryData = z.infer<typeof manualEntrySchema>;

const STATUS_OPTIONS = [
  { label: 'Present', value: AttendanceStatus.PRESENT },
  { label: 'Late', value: AttendanceStatus.LATE },
  { label: 'Absent', value: AttendanceStatus.ABSENT },
];

export const FacultyManualEntryScreen: React.FC = () => {
  const route = useRoute<ManualEntryRouteProp>();
  const navigation = useNavigation();

  const { scheduleId } = route.params;

  const [isSubmitting, setIsSubmitting] = useState(false);

  const { control, handleSubmit, reset } = useForm<ManualEntryData>({
    resolver: zodResolver(manualEntrySchema),
    defaultValues: {
      studentId: '',
      status: AttendanceStatus.PRESENT,
      remarks: '',
    },
  });

  const onSubmit = async (data: ManualEntryData) => {
    try {
      setIsSubmitting(true);
      await attendanceService.createManualEntry({
        schedule_id: scheduleId,
        student_id: data.studentId,
        date: new Date().toISOString().split('T')[0],
        status: data.status,
        remarks: data.remarks,
      });

      Alert.alert('Success', 'Attendance recorded successfully', [
        {
          text: 'Add Another',
          onPress: () => reset(),
        },
        {
          text: 'Done',
          onPress: () => navigation.goBack(),
        },
      ]);
    } catch (error: unknown) {
      const errMsg = getErrorMessage(error);
      Alert.alert('Error', errMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ScreenLayout safeArea keyboardAvoiding>
      <Header showBack title={strings.faculty.manualEntry} />

      <View style={styles.container}>
        <Text
          variant="bodySmall"
          color={theme.colors.text.secondary}
          style={styles.description}
        >
          Manually record attendance for a student. Enter their student ID
          and select the appropriate status.
        </Text>

        <FormInput
          name="studentId"
          control={control}
          label={strings.form.studentId}
          placeholder="e.g. 21-A-02177"
          autoCapitalize="characters"
        />

        <FormSelect
          name="status"
          control={control}
          label={strings.form.status}
          options={STATUS_OPTIONS}
          placeholder="Select status"
        />

        <FormInput
          name="remarks"
          control={control}
          label={strings.form.remarks}
          placeholder="Optional remarks (e.g., reason for manual entry)"
          multiline
          numberOfLines={3}
        />

        <Button
          variant="primary"
          size="lg"
          fullWidth
          onPress={handleSubmit(onSubmit)}
          loading={isSubmitting}
          style={styles.submitButton}
        >
          {strings.faculty.markAttendance}
        </Button>
      </View>
    </ScreenLayout>
  );
};

const styles = StyleSheet.create({
  container: {
    padding: theme.spacing[4],
  },
  description: {
    marginBottom: theme.spacing[6],
    lineHeight: 20,
  },
  submitButton: {
    marginTop: theme.spacing[6],
  },
});

/**
 * Faculty Manual Entry Screen
 *
 * Allows faculty to manually mark student attendance
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
import type { FacultyStackParamList } from '../../types';
import { ScreenLayout, Header } from '../../components/layouts';
import { Button } from '../../components/ui';
import { FormInput, FormSelect } from '../../components/forms';

type ManualEntryRouteProp = RouteProp<FacultyStackParamList, 'ManualEntry'>;

const manualEntrySchema = z.object({
  studentId: z.string().min(1, strings.errors.required),
  status: z.enum(['present', 'late', 'absent']),
  remarks: z.string().optional(),
});

type ManualEntryData = z.infer<typeof manualEntrySchema>;

const STATUS_OPTIONS = [
  { label: 'Present', value: 'present' },
  { label: 'Late', value: 'late' },
  { label: 'Absent', value: 'absent' },
];

export const FacultyManualEntryScreen: React.FC = () => {
  const route = useRoute<ManualEntryRouteProp>();
  const navigation = useNavigation();

  const { scheduleId } = route.params;

  const [isSubmitting, setIsSubmitting] = useState(false);

  const { control, handleSubmit } = useForm<ManualEntryData>({
    resolver: zodResolver(manualEntrySchema),
    defaultValues: {
      studentId: '',
      status: 'present',
      remarks: '',
    },
  });

  const onSubmit = async (data: ManualEntryData) => {
    try {
      setIsSubmitting(true);
      await attendanceService.createManualEntry({
        scheduleId,
        studentId: data.studentId,
        status: data.status,
        remarks: data.remarks,
      });

      Alert.alert('Success', 'Attendance recorded successfully', [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.message || strings.errors.generic);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ScreenLayout safeArea keyboardAvoiding>
      <Header showBack title={strings.faculty.manualEntry} />

      <View style={styles.container}>
        <FormInput
          name="studentId"
          control={control}
          label={strings.form.studentId}
          placeholder="Enter student ID"
          autoCapitalize="none"
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
          placeholder="Optional remarks"
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
  submitButton: {
    marginTop: theme.spacing[6],
  },
});

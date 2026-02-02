/**
 * Faculty Reports Screen
 *
 * Generate and export attendance reports
 */

import React, { useState } from 'react';
import { View, StyleSheet, Alert } from 'react-native';
import { useForm } from 'react-hook-form';
import { Download } from 'lucide-react-native';
import { theme, strings } from '../../constants';
import { ScreenLayout, Header } from '../../components/layouts';
import { Text, Button, Card } from '../../components/ui';
import { FormSelect } from '../../components/forms';

// Mock data
const CLASS_OPTIONS = [
  { label: 'CS101 - Computer Science 1', value: 'cs101' },
  { label: 'MATH101 - Mathematics 1', value: 'math101' },
  { label: 'ENG101 - English 1', value: 'eng101' },
];

const REPORT_TYPE_OPTIONS = [
  { label: 'Summary Report', value: 'summary' },
  { label: 'Detailed Report', value: 'detailed' },
];

export const FacultyReportsScreen: React.FC = () => {
  const [isGenerating, setIsGenerating] = useState(false);

  const { control, handleSubmit } = useForm({
    defaultValues: {
      class: '',
      reportType: 'summary',
    },
  });

  const onGenerate = async (data: any) => {
    setIsGenerating(true);

    // Simulate report generation
    setTimeout(() => {
      setIsGenerating(false);
      Alert.alert('Success', 'Report generated successfully');
    }, 2000);
  };

  const handleExportCSV = () => {
    Alert.alert('Export CSV', 'CSV export functionality coming soon');
  };

  const handleExportPDF = () => {
    Alert.alert('Export PDF', 'PDF export functionality coming soon');
  };

  return (
    <ScreenLayout safeArea scrollable>
      <Header showBack title={strings.faculty.reports} />

      <View style={styles.container}>
        <Card>
          <Text variant="h4" weight="semibold" style={styles.cardTitle}>
            Generate Report
          </Text>

          <FormSelect
            name="class"
            control={control}
            label="Select Class"
            options={CLASS_OPTIONS}
            placeholder="Choose a class"
          />

          <FormSelect
            name="reportType"
            control={control}
            label="Report Type"
            options={REPORT_TYPE_OPTIONS}
            placeholder="Select report type"
          />

          <Button
            variant="primary"
            size="lg"
            fullWidth
            onPress={handleSubmit(onGenerate)}
            loading={isGenerating}
            style={styles.generateButton}
          >
            {strings.faculty.generateReport}
          </Button>
        </Card>

        {/* Export options */}
        <Card style={styles.exportCard}>
          <Text variant="h4" weight="semibold" style={styles.cardTitle}>
            Export Options
          </Text>

          <Button
            variant="outline"
            size="md"
            fullWidth
            onPress={handleExportCSV}
            leftIcon={<Download size={20} color={theme.colors.primary} />}
            style={styles.exportButton}
          >
            {strings.faculty.exportCsv}
          </Button>

          <Button
            variant="outline"
            size="md"
            fullWidth
            onPress={handleExportPDF}
            leftIcon={<Download size={20} color={theme.colors.primary} />}
          >
            {strings.faculty.exportPdf}
          </Button>
        </Card>
      </View>
    </ScreenLayout>
  );
};

const styles = StyleSheet.create({
  container: {
    padding: theme.spacing[4],
  },
  cardTitle: {
    marginBottom: theme.spacing[4],
  },
  generateButton: {
    marginTop: theme.spacing[4],
  },
  exportCard: {
    marginTop: theme.spacing[4],
  },
  exportButton: {
    marginBottom: theme.spacing[3],
  },
});

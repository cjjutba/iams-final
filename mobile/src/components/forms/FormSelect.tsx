/**
 * FormSelect Component
 *
 * Select/dropdown component integrated with react-hook-form.
 * Shows a modal with options when tapped.
 */

import React, { useState } from 'react';
import {
  View,
  TouchableOpacity,
  Modal,
  FlatList,
  StyleSheet,
  Platform,
} from 'react-native';
import { Controller, Control, FieldValues, Path } from 'react-hook-form';
import { ChevronDown } from 'lucide-react-native';
import { theme } from '../../constants';
import { Text, Button } from '../ui';

interface SelectOption {
  label: string;
  value: string | number;
}

interface FormSelectProps<T extends FieldValues> {
  name: Path<T>;
  control: Control<T>;
  label: string;
  options: SelectOption[];
  placeholder?: string;
}

export function FormSelect<T extends FieldValues>({
  name,
  control,
  label,
  options,
  placeholder = 'Select an option',
}: FormSelectProps<T>) {
  const [modalVisible, setModalVisible] = useState(false);

  return (
    <Controller
      control={control}
      name={name}
      render={({ field: { onChange, value }, fieldState: { error } }) => {
        const selectedOption = options.find((opt) => opt.value === value);
        const displayValue = selectedOption?.label || placeholder;
        const hasValue = !!selectedOption;

        return (
          <View style={styles.container}>
            {/* Label */}
            <Text variant="label" color={theme.colors.text.secondary} style={styles.label}>
              {label}
            </Text>

            {/* Select trigger */}
            <TouchableOpacity
              style={[styles.trigger, error && styles.triggerError]}
              onPress={() => setModalVisible(true)}
              activeOpacity={theme.interaction.activeOpacity}
            >
              <Text
                variant="body"
                color={hasValue ? theme.colors.text.primary : theme.colors.text.tertiary}
                style={styles.triggerText}
              >
                {displayValue}
              </Text>
              <ChevronDown size={20} color={theme.colors.text.tertiary} />
            </TouchableOpacity>

            {/* Error */}
            {error && (
              <Text variant="caption" color={theme.colors.error} style={styles.error}>
                {error.message}
              </Text>
            )}

            {/* Options modal */}
            <Modal
              visible={modalVisible}
              transparent
              animationType="slide"
              onRequestClose={() => setModalVisible(false)}
            >
              <View style={styles.modalOverlay}>
                <View style={styles.modalContent}>
                  {/* Header */}
                  <View style={styles.modalHeader}>
                    <Text variant="h3" weight="600">
                      {label}
                    </Text>
                    <Button variant="ghost" onPress={() => setModalVisible(false)}>
                      Close
                    </Button>
                  </View>

                  {/* Options list */}
                  <FlatList
                    data={options}
                    keyExtractor={(item) => String(item.value)}
                    renderItem={({ item }) => (
                      <TouchableOpacity
                        style={[
                          styles.option,
                          item.value === value && styles.optionSelected,
                        ]}
                        onPress={() => {
                          onChange(item.value);
                          setModalVisible(false);
                        }}
                        activeOpacity={theme.interaction.activeOpacity}
                      >
                        <Text
                          variant="body"
                          weight={item.value === value ? '600' : '400'}
                          color={
                            item.value === value
                              ? theme.colors.primary
                              : theme.colors.text.primary
                          }
                        >
                          {item.label}
                        </Text>
                      </TouchableOpacity>
                    )}
                  />
                </View>
              </View>
            </Modal>
          </View>
        );
      }}
    />
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: theme.spacing[4], // 16px
  },
  label: {
    marginBottom: theme.spacing[2], // 8px
  },
  trigger: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: theme.colors.secondary,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.borderRadius.md,
    paddingHorizontal: theme.spacing[4], // 16px
    paddingVertical: theme.spacing[3], // 12px
    minHeight: theme.layout.inputHeight.md,
  },
  triggerError: {
    borderColor: theme.colors.error,
  },
  triggerText: {
    flex: 1,
  },
  error: {
    marginTop: theme.spacing[2], // 8px
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: theme.colors.background,
    borderTopLeftRadius: theme.borderRadius.lg,
    borderTopRightRadius: theme.borderRadius.lg,
    maxHeight: '70%',
    paddingBottom: Platform.OS === 'ios' ? theme.spacing[8] : theme.spacing[6],
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: theme.spacing[6], // 24px
    paddingVertical: theme.spacing[4], // 16px
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  option: {
    paddingHorizontal: theme.spacing[6], // 24px
    paddingVertical: theme.spacing[4], // 16px
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  optionSelected: {
    backgroundColor: theme.colors.secondary,
  },
});

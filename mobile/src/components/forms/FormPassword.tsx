/**
 * FormPassword Component
 *
 * Password input component integrated with react-hook-form.
 * Automatically includes password toggle functionality.
 */

import React from 'react';
import { Controller, Control, FieldValues, Path } from 'react-hook-form';
import { TextInputProps } from 'react-native';
import { Input } from '../ui';

interface FormPasswordProps<T extends FieldValues> extends Omit<TextInputProps, 'value' | 'onChangeText' | 'secureTextEntry'> {
  name: Path<T>;
  control: Control<T>;
  label: string;
  leftIcon?: React.ReactNode;
}

export function FormPassword<T extends FieldValues>({
  name,
  control,
  label,
  leftIcon,
  ...inputProps
}: FormPasswordProps<T>) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field: { onChange, onBlur, value }, fieldState: { error } }) => (
        <Input
          label={label}
          value={value}
          onChangeText={onChange}
          onBlur={onBlur}
          error={error?.message}
          leftIcon={leftIcon}
          secureTextEntry
          {...inputProps}
        />
      )}
    />
  );
}

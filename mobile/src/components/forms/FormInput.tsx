/**
 * FormInput Component
 *
 * Input component integrated with react-hook-form.
 * Handles field value, onChange, onBlur, and error display automatically.
 */

import React from 'react';
import { Controller, Control, FieldValues, Path } from 'react-hook-form';
import { TextInputProps } from 'react-native';
import { Input } from '../ui';

interface FormInputProps<T extends FieldValues> extends Omit<TextInputProps, 'value' | 'onChangeText'> {
  name: Path<T>;
  control: Control<T>;
  label: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  isPassword?: boolean;
}

export function FormInput<T extends FieldValues>({
  name,
  control,
  label,
  leftIcon,
  rightIcon,
  isPassword,
  ...inputProps
}: FormInputProps<T>) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field: { onChange, onBlur, value } }) => (
        <Input
          label={label}
          value={value}
          onChangeText={onChange}
          onBlur={onBlur}
          leftIcon={leftIcon}
          rightIcon={rightIcon}
          isPassword={isPassword}
          {...inputProps}
        />
      )}
    />
  );
}

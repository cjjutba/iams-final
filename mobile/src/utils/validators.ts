/**
 * Validators - Zod Validation Schemas
 *
 * Reusable validation schemas for forms using Zod.
 * Provides type-safe form validation throughout the app.
 */

import { z } from 'zod';

// Email schema
export const emailSchema = z
  .string()
  .min(1, 'Email is required')
  .email('Invalid email format')
  .toLowerCase();

// Password schema
export const passwordSchema = z
  .string()
  .min(8, 'Password must be at least 8 characters')
  .regex(/[a-zA-Z]/, 'Password must contain at least one letter')
  .regex(/[0-9]/, 'Password must contain at least one number');

// Student ID schema (format: 21-A-012345)
export const studentIdPattern = /^\d{2}-[A-Za-z]-\d{5}$/;

export const studentIdSchema = z
  .string()
  .min(1, 'Student ID is required')
  .trim()
  .regex(studentIdPattern, 'Student ID must be in format 21-A-012345')
  .transform((value) => value.toUpperCase());

// Phone number schema (format: 09XXXXXXXXX)
export const phoneSchema = z
  .string()
  .min(1, 'Phone number is required')
  .regex(/^09\d{9}$/, 'Phone number must be in format 09XXXXXXXXX');

// Name schema
export const nameSchema = z
  .string()
  .min(1, 'This field is required')
  .min(2, 'Must be at least 2 characters')
  .max(50, 'Must be less than 50 characters');

// Login schemas
export const studentLoginSchema = z.object({
  student_id: studentIdSchema,
  password: passwordSchema,
});

export const facultyLoginSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
});

// Forgot password schema
export const forgotPasswordSchema = z.object({
  email: emailSchema,
});

// Register Step 1 schema (Student ID verification)
export const registerStep1Schema = z.object({
  student_id: studentIdSchema,
});

// Register Step 2 schema (Account setup)
export const registerStep2Schema = z
  .object({
    email: emailSchema,
    phone: phoneSchema,
    password: passwordSchema,
    confirmPassword: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

// Edit profile schema
export const editProfileSchema = z.object({
  first_name: nameSchema,
  last_name: nameSchema,
  email: emailSchema,
  phone: phoneSchema.optional(),
});

// Change password schema
export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, 'Current password is required'),
    new_password: passwordSchema,
    confirm_new_password: z.string().min(1, 'Please confirm your new password'),
  })
  .refine((data) => data.new_password === data.confirm_new_password, {
    message: 'Passwords do not match',
    path: ['confirm_new_password'],
  });

// Manual attendance entry schema
export const manualAttendanceSchema = z.object({
  student_id: z.string().min(1, 'Student is required'),
  schedule_id: z.string().min(1, 'Schedule is required'),
  date: z.string().min(1, 'Date is required'),
  status: z.enum(['present', 'late', 'absent', 'early_leave'], {
    errorMap: () => ({ message: 'Invalid status' }),
  }),
  remarks: z.string().optional(),
});

// Type exports for TypeScript
export type StudentLoginFormData = z.infer<typeof studentLoginSchema>;
export type FacultyLoginFormData = z.infer<typeof facultyLoginSchema>;
export type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>;
export type RegisterStep1FormData = z.infer<typeof registerStep1Schema>;
export type RegisterStep2FormData = z.infer<typeof registerStep2Schema>;
export type EditProfileFormData = z.infer<typeof editProfileSchema>;
export type ChangePasswordFormData = z.infer<typeof changePasswordSchema>;
export type ManualAttendanceFormData = z.infer<typeof manualAttendanceSchema>;

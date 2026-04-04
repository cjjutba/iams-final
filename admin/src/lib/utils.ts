import { clsx, type ClassValue } from "clsx"
import { format } from "date-fns"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function safeFormat(value: string | null | undefined, fmt: string, fallback = '\u2014'): string {
  if (!value) return fallback
  const date = new Date(value)
  return isNaN(date.getTime()) ? fallback : format(date, fmt)
}

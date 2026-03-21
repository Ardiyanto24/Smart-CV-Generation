import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Utility function untuk menggabungkan Tailwind CSS class names.
 *
 * - clsx: menangani conditional class logic
 *   contoh: cn("base", isActive && "active", { hidden: !isVisible })
 *
 * - twMerge: menyelesaikan conflict antar Tailwind class
 *   contoh: cn("px-2 px-4") → "px-4" (bukan "px-2 px-4")
 */
export function cn(...inputs: ClassValue[]): string {
    return twMerge(clsx(inputs));
}
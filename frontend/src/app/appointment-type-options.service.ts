import { Injectable } from '@angular/core';

export interface AppointmentTypeOption {
  id?: number;
  appointment_type: string;
  duration_minutes: number;
}

/**
 * Fetches the list of available appointment types from the backend and caches
 * the result for the lifetime of the page so booking screens don't refetch on
 * every navigation. Concurrent callers share a single in-flight request.
 */
@Injectable({ providedIn: 'root' })
export class AppointmentTypeOptionsService {
  // Cache the last successful result so repeat visits do not refetch the same options.
  private appointmentTypes: AppointmentTypeOption[] | null = null;
  // Reuse an in-flight request so concurrent callers share one network round trip.
  private pendingRequest: Promise<AppointmentTypeOption[]> | null = null;

  /** Return the cached list if present, otherwise trigger (or reuse) a fetch. */
  async getAppointmentTypes(): Promise<AppointmentTypeOption[]> {
    if (this.appointmentTypes) {
      return this.appointmentTypes;
    }

    if (!this.pendingRequest) {
      this.pendingRequest = this.fetchAppointmentTypes();
    }

    return this.pendingRequest;
  }

  /** Fire-and-forget prefetch so the next caller finds the list already cached. */
  prefetchAppointmentTypes(): void {
    void this.getAppointmentTypes();
  }

  /** Drop the cached list so the next call refetches from the backend. */
  clearCache(): void {
    this.appointmentTypes = null;
    this.pendingRequest = null;
  }

  private async fetchAppointmentTypes(): Promise<AppointmentTypeOption[]> {
    try {
      const response = await fetch('/api/availability/appointment-types', {
        cache: 'no-store'
      });

      if (!response.ok) {
        // Treat a failed lookup as "no options" so booking screens can still render safely.
        this.appointmentTypes = [];
        return [];
      }

      this.appointmentTypes = await response.json() as AppointmentTypeOption[];
      return this.appointmentTypes;
    } catch {
      this.appointmentTypes = [];
      return [];
    } finally {
      this.pendingRequest = null;
    }
  }
}

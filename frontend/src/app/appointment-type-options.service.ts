import { Injectable } from '@angular/core';

export interface AppointmentTypeOption {
  appointment_type: string;
  duration_minutes: number;
}

@Injectable({ providedIn: 'root' })
export class AppointmentTypeOptionsService {
  private appointmentTypes: AppointmentTypeOption[] | null = null;
  private pendingRequest: Promise<AppointmentTypeOption[]> | null = null;

  async getAppointmentTypes(): Promise<AppointmentTypeOption[]> {
    if (this.appointmentTypes) {
      return this.appointmentTypes;
    }

    if (!this.pendingRequest) {
      this.pendingRequest = this.fetchAppointmentTypes();
    }

    return this.pendingRequest;
  }

  prefetchAppointmentTypes(): void {
    void this.getAppointmentTypes();
  }

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

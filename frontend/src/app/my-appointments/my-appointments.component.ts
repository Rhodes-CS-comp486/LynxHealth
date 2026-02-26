import { DatePipe, NgFor, NgIf } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';

interface BookedAppointment {
  id: number;
  student_email: string;
  appointment_type: string;
  duration_minutes: number;
  start_time: string;
  end_time: string;
  status: string;
  notes: string | null;
}

@Component({
  selector: 'app-my-appointments',
  standalone: true,
  imports: [RouterLink, NgIf, NgFor, DatePipe],
  templateUrl: './my-appointments.component.html',
  styleUrl: './my-appointments.component.css'
})
export class MyAppointmentsComponent implements OnInit {
  readonly sessionEmail = this.getSessionEmail();
  appointments: BookedAppointment[] = [];
  isLoading = true;
  error = '';

  ngOnInit(): void {
    this.loadAppointments();
  }

  formatAppointmentType(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  private async loadAppointments(): Promise<void> {
    if (!this.sessionEmail) {
      this.error = 'Please log in before viewing appointments.';
      this.isLoading = false;
      return;
    }

    try {
      const response = await fetch(`/api/availability/appointments/mine?student_email=${encodeURIComponent(this.sessionEmail)}`, {
        cache: 'no-store'
      });

      if (!response.ok) {
        const detail = await this.tryReadError(response);
        throw new Error(detail || `Unable to load appointments (HTTP ${response.status}).`);
      }

      this.appointments = await response.json() as BookedAppointment[];
    } catch (error) {
      if (error instanceof Error) {
        this.error = error.message;
      } else {
        this.error = 'Unable to load appointments right now.';
      }
    } finally {
      this.isLoading = false;
    }
  }

  private async tryReadError(response: Response): Promise<string | null> {
    try {
      const payload = await response.json() as { detail?: string };
      return payload.detail || null;
    } catch {
      return null;
    }
  }

  private getSessionEmail(): string {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return '';
    }

    try {
      const data = localStorage.getItem('lynxSession');
      if (!data) {
        return '';
      }

      const parsed = JSON.parse(data) as { email?: string };
      return parsed.email || '';
    } catch {
      return '';
    }
  }
}

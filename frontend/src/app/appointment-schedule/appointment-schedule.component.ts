import { DatePipe, NgFor, NgIf } from '@angular/common';
import { ChangeDetectorRef, Component, OnDestroy, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { getClientSession } from '../session';

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
  selector: 'app-appointment-schedule',
  standalone: true,
  imports: [RouterLink, NgIf, NgFor, DatePipe],
  templateUrl: './appointment-schedule.component.html',
  styleUrl: './appointment-schedule.component.css'
})
export class AppointmentScheduleComponent implements OnInit, OnDestroy {
  private readonly autoRefreshIntervalMs = 10000;
  private autoRefreshTimer: number | null = null;

  readonly session = getClientSession();
  readonly role = this.session.role;
  readonly sessionEmail = this.session.requestEmail;

  appointments: BookedAppointment[] = [];
  isLoading = false;
  error = '';

  constructor(private readonly cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    if (this.role !== 'admin') {
      this.error = 'Only admins can view the appointment schedule.';
      return;
    }

    void this.loadAppointments();
    this.startAutoRefresh();
  }

  ngOnDestroy(): void {
    if (this.autoRefreshTimer !== null && typeof window !== 'undefined') {
      window.clearInterval(this.autoRefreshTimer);
      this.autoRefreshTimer = null;
    }
  }

  async loadAppointments(): Promise<void> {
    this.isLoading = true;
    this.error = '';

    try {
      const response = await fetch(
        `/api/availability/appointments?admin_email=${encodeURIComponent(this.sessionEmail)}&ts=${Date.now()}`,
        { cache: 'no-store' }
      );

      if (!response.ok) {
        throw new Error('Unable to load upcoming student appointments.');
      }

      const allAppointments = await response.json() as BookedAppointment[];
      const now = new Date();
      this.appointments = allAppointments
        .filter((appointment) => new Date(appointment.start_time) >= now)
        .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
    } catch (error) {
      this.appointments = [];
      this.error = error instanceof Error ? error.message : 'Unable to load upcoming student appointments.';
    } finally {
      this.isLoading = false;
      this.cdr.detectChanges();
    }
  }

  formatAppointmentType(value: string): string {
    return value
      .split('_')
      .map((segment) => segment
        .split('-')
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join('-'))
      .join(' ');
  }

  private startAutoRefresh(): void {
    if (typeof window === 'undefined') {
      return;
    }

    this.autoRefreshTimer = window.setInterval(() => {
      void this.loadAppointments();
    }, this.autoRefreshIntervalMs);
  }
}

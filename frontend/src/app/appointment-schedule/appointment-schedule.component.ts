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

interface DailyHours {
  day_of_week: number;
  day_name: string;
  is_open: boolean;
  open_time: string | null;
  close_time: string | null;
}

interface Holiday {
  holiday_date: string;
  name: string;
}

interface ClinicHoursResponse {
  daily_hours: DailyHours[];
  holidays: Holiday[];
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
  clinicDailyHours = new Map<number, DailyHours>();
  holidayDates = new Set<string>();
  isLoading = false;
  error = '';

  constructor(private readonly cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    if (this.role !== 'admin') {
      this.error = 'Only admins can view the appointment schedule.';
      return;
    }

    this.setDefaultClinicHours();
    void this.loadClinicHours();
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

  async loadClinicHours(): Promise<void> {
    try {
      const response = await fetch('/api/availability/clinic-hours', { cache: 'no-store' });
      if (!response.ok) {
        throw new Error('Unable to load clinic hours.');
      }

      const payload = await response.json() as ClinicHoursResponse;
      this.clinicDailyHours = new Map<number, DailyHours>();
      this.holidayDates = new Set<string>();

      for (const day of payload.daily_hours) {
        this.clinicDailyHours.set(day.day_of_week, day);
      }

      for (const holiday of payload.holidays) {
        this.holidayDates.add(holiday.holiday_date);
      }
    } catch {
      this.setDefaultClinicHours();
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

  isAppointmentOutsideCurrentRules(appointment: BookedAppointment): boolean {
    const start = new Date(appointment.start_time);
    const end = new Date(appointment.end_time);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
      return false;
    }

    const dayKey = this.formatDateKey(start);
    if (this.holidayDates.has(dayKey)) {
      return true;
    }

    const dayHours = this.clinicDailyHours.get(start.getDay() === 0 ? 6 : start.getDay() - 1);
    if (!dayHours?.is_open || !dayHours.open_time || !dayHours.close_time) {
      return true;
    }

    const dayOpen = this.toMinutes(dayHours.open_time);
    const dayClose = this.toMinutes(dayHours.close_time);
    const startMinutes = (start.getHours() * 60) + start.getMinutes();
    const endMinutes = (end.getHours() * 60) + end.getMinutes();

    if (dayOpen === null || dayClose === null) {
      return true;
    }

    if (startMinutes < dayOpen || endMinutes > dayClose) {
      return true;
    }

    const lunchStart = 12 * 60;
    const lunchEnd = 13 * 60;
    return startMinutes < lunchEnd && endMinutes > lunchStart;
  }

  private startAutoRefresh(): void {
    if (typeof window === 'undefined') {
      return;
    }

    this.autoRefreshTimer = window.setInterval(() => {
      void this.loadClinicHours();
      void this.loadAppointments();
    }, this.autoRefreshIntervalMs);
  }

  private formatDateKey(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  private toMinutes(value: string): number | null {
    const [hourRaw, minuteRaw] = value.split(':');
    const hour = Number(hourRaw);
    const minute = Number(minuteRaw);

    if (Number.isNaN(hour) || Number.isNaN(minute)) {
      return null;
    }

    return (hour * 60) + minute;
  }

  private setDefaultClinicHours(): void {
    this.clinicDailyHours = new Map<number, DailyHours>();
    this.holidayDates = new Set<string>();

    for (let dayIndex = 0; dayIndex < 5; dayIndex += 1) {
      this.clinicDailyHours.set(dayIndex, {
        day_of_week: dayIndex,
        day_name: '',
        is_open: true,
        open_time: '09:00:00',
        close_time: '16:00:00'
      });
    }

    this.clinicDailyHours.set(5, {
      day_of_week: 5,
      day_name: '',
      is_open: false,
      open_time: null,
      close_time: null
    });

    this.clinicDailyHours.set(6, {
      day_of_week: 6,
      day_name: '',
      is_open: false,
      open_time: null,
      close_time: null
    });
  }
}

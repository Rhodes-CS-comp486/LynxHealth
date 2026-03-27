import { NgFor, NgIf } from '@angular/common';
import { ChangeDetectorRef, Component, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { getClientSession, SessionRole } from '../session';

interface DailyHours {
  day_of_week: number;
  day_name: string;
  is_open: boolean;
  open_time: string | null;
  close_time: string | null;
}

interface Holiday {
  id?: number;
  holiday_date: string;
  name: string;
  is_annual?: boolean;
}

interface ClinicHoursResponse {
  daily_hours: DailyHours[];
  holidays: Holiday[];
}

@Component({
  selector: 'app-hours',
  standalone: true,
  imports: [RouterLink, NgIf, NgFor, FormsModule],
  templateUrl: './hours.component.html',
  styleUrl: './hours.component.css'
})
export class HoursComponent implements OnInit, OnDestroy {
  private refreshTimer: number | null = null;
  private saveStateTimer: number | null = null;

  readonly session = getClientSession();
  readonly role: SessionRole = this.session.role;
  readonly sessionEmail = this.session.requestEmail;

  dailyHours: DailyHours[] = this.getDefaultDailyHours();
  holidays: Holiday[] = [];

  isLoading = false;
  isSaving = false;
  saveState: 'idle' | 'saving' = 'idle';
  hasUnsavedChanges = false;
  error = '';
  message = '';

  newHolidayDate = '';
  newHolidayName = '';
  newHolidayIsAnnual = false;

  get weekdayHours(): DailyHours[] {
    return this.dailyHours.filter((day) => day.day_of_week < 5);
  }

  get saveButtonLabel(): string {
    if (this.saveState === 'saving') {
      return 'Saving!';
    }
    return 'Save Hours & Closures';
  }

  ngOnInit(): void {
    this.loadCachedClinicHours();
    this.loadClinicHours();
    this.startAutoRefresh();
  }

  constructor(private readonly cdr: ChangeDetectorRef) {}

  ngOnDestroy(): void {
    if (this.refreshTimer !== null && typeof window !== 'undefined') {
      window.clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
    if (this.saveStateTimer !== null && typeof window !== 'undefined') {
      window.clearTimeout(this.saveStateTimer);
      this.saveStateTimer = null;
    }
  }

  async loadClinicHours(): Promise<void> {
    this.isLoading = true;
    this.error = '';

    try {
      const response = await fetch('/api/availability/clinic-hours', { cache: 'no-store' });
      if (!response.ok) {
        throw new Error('Unable to load clinic hours right now.');
      }

      const payload = await response.json() as ClinicHoursResponse;
      const normalizedHolidays = payload.holidays
        .map((holiday) => ({ ...holiday, is_annual: !!holiday.is_annual }))
        .sort((a, b) => this.compareHolidays(a, b));
      if (this.hasUnsavedChanges) {
        return;
      }
      this.holidays = normalizedHolidays;
      this.dailyHours = payload.daily_hours.sort((a, b) => a.day_of_week - b.day_of_week);
      this.saveCachedClinicHours(payload);
    } catch (error) {
      if (error instanceof Error) {
        this.error = error.message;
      } else {
        this.error = 'Unable to load clinic hours right now.';
      }
    } finally {
      this.isLoading = false;
    }
  }

  getDisplayHours(day: DailyHours): string {
    if (!day.is_open || !day.open_time || !day.close_time) {
      return 'Closed';
    }

    return `${this.formatTime(day.open_time)} - ${this.formatTime(day.close_time)}`;
  }

  addHoliday(): void {
    this.message = '';
    this.error = '';

    const normalizedName = this.newHolidayName.trim();
    if (!this.newHolidayDate || !normalizedName) {
      this.error = 'Enter both a holiday date and holiday name.';
      return;
    }

    if (this.holidays.some((holiday) => holiday.holiday_date === this.newHolidayDate)) {
      this.error = 'That date is already blocked as a holiday.';
      return;
    }

    this.holidays = [
      ...this.holidays,
      {
        holiday_date: this.newHolidayDate,
        name: normalizedName,
        is_annual: this.newHolidayIsAnnual
      }
    ].sort((a, b) => this.compareHolidays(a, b));

    this.newHolidayDate = '';
    this.newHolidayName = '';
    this.newHolidayIsAnnual = false;
    this.hasUnsavedChanges = true;
  }

  removeHoliday(index: number): void {
    this.holidays = this.holidays.filter((_, itemIndex) => itemIndex !== index);
    this.hasUnsavedChanges = true;
  }

  async saveHours(): Promise<void> {
    if (this.role !== 'admin') {
      return;
    }

    this.message = '';
    this.error = '';

    for (const day of this.dailyHours) {
      if (day.is_open && (!day.open_time || !day.close_time || day.close_time <= day.open_time)) {
        this.error = `Please provide valid opening and closing times for ${day.day_name}.`;
        this.isSaving = false;
        this.saveState = 'idle';
        return;
      }
    }

    this.isSaving = true;
    this.saveState = 'saving';
    this.queueSaveStateReset();
    this.cdr.detectChanges();

    try {
      const response = await fetch('/api/availability/clinic-hours', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          admin_email: this.sessionEmail,
          daily_hours: this.dailyHours,
          holidays: this.holidays
        })
      });

      if (!response.ok) {
        const detail = await this.tryReadError(response);
        throw new Error(detail || `Unable to save clinic hours (HTTP ${response.status}).`);
      }

      const payload = await response.json() as ClinicHoursResponse;
      this.dailyHours = payload.daily_hours.sort((a, b) => a.day_of_week - b.day_of_week);
      this.holidays = payload.holidays
        .map((holiday) => ({ ...holiday, is_annual: !!holiday.is_annual }))
        .sort((a, b) => this.compareHolidays(a, b));
      this.saveCachedClinicHours(payload);
      this.message = 'Clinic hours and holidays were updated.';
      this.hasUnsavedChanges = false;
      this.cdr.detectChanges();
    } catch (error) {
      if (error instanceof Error) {
        this.error = error.message;
      } else {
        this.error = 'Unable to save clinic hours.';
      }
      this.cdr.detectChanges();
    }
  }

  private formatTime(value: string): string {
    const [hourRaw, minute] = value.split(':');
    const hour = Number(hourRaw);
    const suffix = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour % 12 === 0 ? 12 : hour % 12;
    return `${displayHour}:${minute} ${suffix}`;
  }

  private async tryReadError(response: Response): Promise<string | null> {
    try {
      const payload = await response.json() as { detail?: string };
      return payload.detail ?? null;
    } catch {
      return null;
    }
  }

  private startAutoRefresh(): void {
    if (typeof window === 'undefined') {
      return;
    }

    this.refreshTimer = window.setInterval(() => {
      if (!this.hasUnsavedChanges) {
        void this.loadClinicHours();
      }
    }, 15000);
  }

  private loadCachedClinicHours(): void {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return;
    }

    const cached = localStorage.getItem('lynxClinicHours');
    if (!cached) {
      return;
    }

    try {
      const payload = JSON.parse(cached) as ClinicHoursResponse;
      if (Array.isArray(payload.daily_hours) && Array.isArray(payload.holidays)) {
        this.dailyHours = payload.daily_hours.sort((a, b) => a.day_of_week - b.day_of_week);
        this.holidays = payload.holidays
          .map((holiday) => ({ ...holiday, is_annual: !!holiday.is_annual }))
          .sort((a, b) => this.compareHolidays(a, b));
      }
    } catch {
      // ignore invalid cache
    }
  }

  private saveCachedClinicHours(payload: ClinicHoursResponse): void {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return;
    }

    localStorage.setItem('lynxClinicHours', JSON.stringify(payload));
  }

  markDirty(): void {
    this.hasUnsavedChanges = true;
  }

  private queueSaveStateReset(): void {
    if (typeof window === 'undefined') {
      this.saveState = 'idle';
      this.isSaving = false;
      this.cdr.detectChanges();
      return;
    }
    if (this.saveStateTimer !== null) {
      window.clearTimeout(this.saveStateTimer);
    }
    this.saveStateTimer = window.setTimeout(() => {
      this.saveState = 'idle';
      this.isSaving = false;
      this.saveStateTimer = null;
      this.cdr.detectChanges();
    }, 1000);
  }

  private compareHolidays(left: Holiday, right: Holiday): number {
    const [leftYear, leftMonth, leftDay] = left.holiday_date.split('-').map(Number);
    const [rightYear, rightMonth, rightDay] = right.holiday_date.split('-').map(Number);

    if (leftMonth !== rightMonth) {
      return leftMonth - rightMonth;
    }
    if (leftDay !== rightDay) {
      return leftDay - rightDay;
    }
    return leftYear - rightYear;
  }

  private getDefaultDailyHours(): DailyHours[] {
    const names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    return names.map((day_name, day_of_week) => ({
      day_of_week,
      day_name,
      is_open: day_of_week < 5,
      open_time: day_of_week < 5 ? '09:00' : null,
      close_time: day_of_week < 5 ? '16:00' : null
    }));
  }

}

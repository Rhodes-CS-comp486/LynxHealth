import { NgFor, NgIf } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

type SessionRole = 'admin' | 'user';

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
export class HoursComponent implements OnInit {
  readonly role: SessionRole = this.getRole();
  readonly sessionEmail = this.getSessionEmail();

  dailyHours: DailyHours[] = this.getDefaultDailyHours();
  holidays: Holiday[] = [];

  isLoading = false;
  isSaving = false;
  error = '';
  message = '';

  newHolidayDate = '';
  newHolidayName = '';

  ngOnInit(): void {
    this.loadClinicHours();
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
      this.dailyHours = payload.daily_hours.sort((a, b) => a.day_of_week - b.day_of_week);
      this.holidays = payload.holidays.sort((a, b) => a.holiday_date.localeCompare(b.holiday_date));
    } catch (error) {
      if (error instanceof Error) {
        this.error = error.message;
      } else {
        this.error = 'Unable to load clinic hours right now.';
      }
      this.dailyHours = this.getDefaultDailyHours();
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
        name: normalizedName
      }
    ].sort((a, b) => a.holiday_date.localeCompare(b.holiday_date));

    this.newHolidayDate = '';
    this.newHolidayName = '';
  }

  removeHoliday(index: number): void {
    this.holidays = this.holidays.filter((_, itemIndex) => itemIndex !== index);
  }

  async saveHours(): Promise<void> {
    if (this.role !== 'admin') {
      return;
    }

    this.isSaving = true;
    this.message = '';
    this.error = '';

    for (const day of this.dailyHours) {
      if (day.is_open && (!day.open_time || !day.close_time || day.close_time <= day.open_time)) {
        this.error = `Please provide valid opening and closing times for ${day.day_name}.`;
        this.isSaving = false;
        return;
      }
    }

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
      this.holidays = payload.holidays.sort((a, b) => a.holiday_date.localeCompare(b.holiday_date));
      this.message = 'Clinic hours and holidays were updated.';
    } catch (error) {
      if (error instanceof Error) {
        this.error = error.message;
      } else {
        this.error = 'Unable to save clinic hours.';
      }
    } finally {
      this.isSaving = false;
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

  private getRole(): SessionRole {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return 'user';
    }

    const data = localStorage.getItem('lynxSession');
    if (!data) {
      return 'user';
    }

    try {
      const parsed = JSON.parse(data) as { role?: string };
      return parsed.role === 'admin' ? 'admin' : 'user';
    } catch {
      return 'user';
    }
  }

  private getSessionEmail(): string {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return '';
    }

    const data = localStorage.getItem('lynxSession');
    if (!data) {
      return '';
    }

    try {
      const parsed = JSON.parse(data) as { email?: string };
      return typeof parsed.email === 'string' ? parsed.email : '';
    } catch {
      return '';
    }
  }
}

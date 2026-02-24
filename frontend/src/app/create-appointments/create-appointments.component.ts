import { DatePipe, NgClass, NgFor, NgIf } from '@angular/common';
import { ChangeDetectorRef, Component, OnDestroy, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';

interface BlockedTime {
  id: number;
  start_time: string;
}

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

interface CalendarDay {
  date: Date;
  key: string;
  label: string;
}

interface TimeCell {
  key: string;
  timeLabel: string;
  hourLabel: string;
  date: string;
  time: string;
  blockedId?: number;
  isBooked: boolean;
  isLunchBreak: boolean;
  isPast: boolean;
}

@Component({
  selector: 'app-create-appointments',
  standalone: true,
  imports: [RouterLink, NgIf, NgFor, DatePipe, NgClass],
  templateUrl: './create-appointments.component.html',
  styleUrl: './create-appointments.component.css'
})
export class CreateAppointmentsComponent implements OnInit, OnDestroy {
  private readonly autoRefreshIntervalMs = 5000;
  private autoRefreshTimer: number | null = null;
  private isDestroyed = false;

  readonly role = this.getRole();
  readonly sessionEmail = this.getSessionEmail();

  readonly timeSlots = this.buildTimeSlots();

  weekStart = this.getWeekStart(new Date());
  calendarDays: CalendarDay[] = [];
  calendarRows: TimeCell[][] = [];

  blockedTimes: BlockedTime[] = [];
  blockedMap = new Map<string, number>();
  bookedAppointments: BookedAppointment[] = [];
  bookedSlotKeys = new Set<string>();

  adminMessage = '';
  adminError = '';
  isSaving = false;

  constructor(private readonly cdr: ChangeDetectorRef) {}

  get bookedAppointmentsForVisibleWeek(): BookedAppointment[] {
    const weekStart = this.getStartOfDay(this.weekStart);
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekEnd.getDate() + 7);

    return this.bookedAppointments.filter((appointment) => {
      const appointmentStart = new Date(appointment.start_time);
      return (
        !Number.isNaN(appointmentStart.getTime())
        && appointmentStart >= weekStart
        && appointmentStart < weekEnd
      );
    });
  }

  ngOnInit(): void {
    this.buildCalendar();
    this.loadBlockedTimes();
    this.loadBookedAppointments();
    this.startAutoRefresh();

    if (this.role !== 'admin') {
      this.adminError = 'Only admins can block appointment times.';
    }
  }

  ngOnDestroy(): void {
    this.isDestroyed = true;
    this.stopAutoRefresh();
  }

  previousWeek(): void {
    const next = new Date(this.weekStart);
    next.setDate(next.getDate() - 7);
    this.weekStart = this.getWeekStart(next);
    this.buildCalendar();
  }

  nextWeek(): void {
    const next = new Date(this.weekStart);
    next.setDate(next.getDate() + 7);
    this.weekStart = this.getWeekStart(next);
    this.buildCalendar();
  }

  async toggleBlocked(cell: TimeCell): Promise<void> {
    if (this.role !== 'admin') {
      this.adminError = 'Only admins can block appointment times.';
      return;
    }

    if (cell.isPast) {
      this.adminMessage = '';
      this.adminError = 'Past time slots cannot be updated.';
      return;
    }

    if (cell.isBooked) {
      this.adminMessage = '';
      this.adminError = 'Booked appointment times cannot be blocked.';
      return;
    }

    if (cell.isLunchBreak) {
      this.adminMessage = '';
      this.adminError = '12:00 PM to 1:00 PM is reserved for lunch and is always blocked.';
      return;
    }

    this.isSaving = true;
    this.adminError = '';
    this.adminMessage = '';

    try {
      if (cell.blockedId) {
        await this.unblockTime(cell.blockedId);
        this.blockedMap.delete(cell.key);
        this.adminMessage = `${cell.timeLabel} on ${new Date(cell.date).toLocaleDateString()} is now available.`;
      } else {
        const blockedId = await this.blockTime(cell.date, cell.time);
        this.blockedMap.set(cell.key, blockedId);
        this.adminMessage = `${cell.timeLabel} on ${new Date(cell.date).toLocaleDateString()} has been blocked.`;
      }

      this.buildCalendar();
      await this.loadBlockedTimes();
      await this.loadBookedAppointments();
    } catch (error) {
      if (error instanceof Error) {
        this.adminError = error.message;
      } else {
        this.adminError = 'Unable to update blocked time.';
      }
    } finally {
      this.isSaving = false;
    }
  }

  private async blockTime(date: string, time: string): Promise<number> {
    const response = await fetch('http://localhost:8000/availability/slots', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        admin_email: this.sessionEmail,
        date,
        time
      })
    });

    if (!response.ok) {
      const payload = await this.tryReadError(response);
      throw new Error(payload || `Unable to block time (HTTP ${response.status}).`);
    }

    const payload = await response.json() as { id: number };
    return payload.id;
  }

  private async unblockTime(id: number): Promise<void> {
    const response = await fetch(`http://localhost:8000/availability/slots/${id}?admin_email=${encodeURIComponent(this.sessionEmail)}`, {
      method: 'DELETE'
    });

    if (!response.ok) {
      const payload = await this.tryReadError(response);
      throw new Error(payload || `Unable to unblock time (HTTP ${response.status}).`);
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

  private async loadBlockedTimes(): Promise<void> {
    try {
      const response = await fetch(`http://localhost:8000/availability/blocked-times?ts=${Date.now()}`, {
        cache: 'no-store'
      });
      if (!response.ok) {
        this.blockedTimes = [];
        this.blockedMap = new Map<string, number>();
        this.buildCalendar();
        this.refreshView();
        return;
      }

      this.blockedTimes = await response.json() as BlockedTime[];
      this.blockedMap = new Map<string, number>();
      for (const blocked of this.blockedTimes) {
        this.blockedMap.set(this.getSlotKey(new Date(blocked.start_time)), blocked.id);
      }

      this.buildCalendar();
      this.refreshView();
    } catch {
      this.blockedTimes = [];
      this.blockedMap = new Map<string, number>();
      this.buildCalendar();
      this.refreshView();
    }
  }

  private async loadBookedAppointments(): Promise<void> {
    if (this.role !== 'admin') {
      this.bookedAppointments = [];
      this.bookedSlotKeys = new Set<string>();
      this.buildCalendar();
      this.refreshView();
      return;
    }

    try {
      const response = await fetch(
        `http://localhost:8000/availability/appointments?admin_email=${encodeURIComponent(this.sessionEmail)}&ts=${Date.now()}`,
        {
          cache: 'no-store'
        }
      );

      if (!response.ok) {
        this.bookedAppointments = [];
        this.bookedSlotKeys = new Set<string>();
        this.buildCalendar();
        this.refreshView();
        return;
      }

      this.bookedAppointments = await response.json() as BookedAppointment[];
      this.bookedSlotKeys = new Set<string>();

      for (const appointment of this.bookedAppointments) {
        const start = new Date(appointment.start_time);
        const end = new Date(appointment.end_time);

        if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
          continue;
        }

        for (const slotKey of this.getSlotKeysInRange(start, end)) {
          this.bookedSlotKeys.add(slotKey);
        }
      }

      this.buildCalendar();
      this.refreshView();
    } catch {
      this.bookedAppointments = [];
      this.bookedSlotKeys = new Set<string>();
      this.buildCalendar();
      this.refreshView();
    }
  }

  private startAutoRefresh(): void {
    if (this.role !== 'admin' || typeof window === 'undefined') {
      return;
    }

    this.stopAutoRefresh();
    this.autoRefreshTimer = window.setInterval(() => {
      void this.loadBookedAppointments();
    }, this.autoRefreshIntervalMs);
  }

  private stopAutoRefresh(): void {
    if (this.autoRefreshTimer !== null && typeof window !== 'undefined') {
      window.clearInterval(this.autoRefreshTimer);
      this.autoRefreshTimer = null;
    }
  }

  private refreshView(): void {
    if (!this.isDestroyed) {
      this.cdr.detectChanges();
    }
  }

  private buildCalendar(): void {
    this.calendarDays = [];

    const now = new Date();
    const today = new Date(now);
    today.setHours(0, 0, 0, 0);

    for (let i = 0; i < 5; i += 1) {
      const dayDate = new Date(this.weekStart);
      dayDate.setDate(this.weekStart.getDate() + i);
      dayDate.setHours(0, 0, 0, 0);

      if (dayDate < today) {
        continue;
      }

      this.calendarDays.push({
        date: dayDate,
        key: this.formatDateKey(dayDate),
        label: dayDate.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
      });
    }

    this.calendarRows = this.timeSlots.map((slot) =>
      this.calendarDays.map((day) => {
        const key = `${day.key}T${slot}`;
        const blockedId = this.blockedMap.get(key);
        const isBooked = this.bookedSlotKeys.has(key);
        const isLunchBreak = this.isLunchBreakSlot(slot);
        const slotDateTime = new Date(`${day.key}T${slot}`);
        const isPast = slotDateTime < now;

        return {
          key,
          timeLabel: this.formatTime(slot),
          hourLabel: slot.endsWith(':00') ? this.formatTime(slot) : '',
          date: day.key,
          time: slot,
          blockedId: isLunchBreak ? -1 : blockedId,
          isBooked,
          isLunchBreak,
          isPast
        };
      })
    ).filter((row) => row.some((cell) => !cell.isPast));
  }

  private getWeekStart(date: Date): Date {
    const start = this.getStartOfDay(date);

    const day = start.getDay();
    const offset = day === 0 ? -6 : 1 - day;
    start.setDate(start.getDate() + offset);

    return start;
  }

  private buildTimeSlots(): string[] {
    const slots: string[] = [];
    const current = new Date(2000, 0, 1, 9, 0, 0, 0);
    const end = new Date(2000, 0, 1, 15, 45, 0, 0);

    while (current <= end) {
      slots.push(`${String(current.getHours()).padStart(2, '0')}:${String(current.getMinutes()).padStart(2, '0')}:00`);
      current.setMinutes(current.getMinutes() + 15);
    }

    return slots;
  }


  private isLunchBreakSlot(slot: string): boolean {
    const [hourString] = slot.split(':');
    const hour = Number(hourString);
    return hour === 12;
  }

  private formatTime(value: string): string {
    const [hourString, minuteString] = value.split(':');
    const hour = Number(hourString);
    const minute = Number(minuteString);
    const suffix = hour >= 12 ? 'PM' : 'AM';
    const normalizedHour = hour % 12 || 12;
    return `${normalizedHour}:${String(minute).padStart(2, '0')} ${suffix}`;
  }

  private getSlotKey(date: Date): string {
    const dateKey = this.formatDateKey(date);
    const timeKey = `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:00`;
    return `${dateKey}T${timeKey}`;
  }

  private getSlotKeysInRange(start: Date, end: Date): string[] {
    const keys: string[] = [];
    const cursor = new Date(start);
    cursor.setSeconds(0, 0);

    while (cursor < end) {
      keys.push(this.getSlotKey(cursor));
      cursor.setMinutes(cursor.getMinutes() + 15);
    }

    return keys;
  }

  private formatDateKey(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  private getStartOfDay(date: Date): Date {
    const start = new Date(date);
    start.setHours(0, 0, 0, 0);
    return start;
  }

  private getRole(): 'admin' | 'user' {
    const data = this.getSessionStorageItem();

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
    const data = this.getSessionStorageItem();

    if (!data) {
      return 'user@lynxhealth.local';
    }

    try {
      const parsed = JSON.parse(data) as { email?: string };
      return parsed.email?.trim().toLowerCase() || 'user@lynxhealth.local';
    } catch {
      return 'user@lynxhealth.local';
    }
  }

  private getSessionStorageItem(): string | null {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return null;
    }

    return localStorage.getItem('lynxSession');
  }
}

import { DatePipe, NgFor, NgIf } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

type SlotStatus = 'available' | 'blocked' | 'booked';
type SessionRole = 'admin' | 'user';
type TimeOfDayFilter = 'all' | 'morning' | 'afternoon';

interface AppointmentTypeOption {
  appointment_type: string;
  duration_minutes: number;
}

interface CalendarSlot {
  date: string;
  time: string;
  duration_minutes: number;
  appointment_type: string;
  start_time: string;
  end_time: string;
  status: SlotStatus;
  is_available: boolean;
  is_blocked: boolean;
  is_booked: boolean;
}

interface CalendarDay {
  key: string;
  date: Date;
  label: string;
}

@Component({
  selector: 'app-availability-calendar',
  standalone: true,
  imports: [RouterLink, NgIf, NgFor, DatePipe, FormsModule],
  templateUrl: './availability-calendar.component.html',
  styleUrl: './availability-calendar.component.css'
})
export class AvailabilityCalendarComponent implements OnInit {
  readonly role = this.getRole();
  readonly currentWeekStart = this.getStartOfWeek(new Date());

  slots: CalendarSlot[] = [];
  filteredSlots: CalendarSlot[] = [];
  visibleWeekDays: CalendarDay[] = [];
  visibleWeekSlotsByDay = new Map<string, CalendarSlot[]>();
  appointmentTypeOptions: AppointmentTypeOption[] = [];
  error = '';
  weekIndex = 0;

  selectedTimeOfDay: TimeOfDayFilter = 'all';
  selectedAppointmentType = '';

  ngOnInit(): void {
    this.loadAppointmentTypes();
  }

  get weekRangeLabel(): string {
    if (this.visibleWeekDays.length === 0) {
      return '';
    }

    const first = this.visibleWeekDays[0].date;
    const last = this.visibleWeekDays[this.visibleWeekDays.length - 1].date;
    return `${first.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} - ${last.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`;
  }

  get canShowNextWeek(): boolean {
    return this.weekIndex === 0;
  }

  get canShowCurrentWeek(): boolean {
    return this.weekIndex === 1;
  }

  async onAppointmentTypeChange(): Promise<void> {
    this.weekIndex = 0;
    await this.loadCalendar();
  }

  onTimeOfDayChange(): void {
    this.updateFilteredSlots();
  }

  showNextWeek(): void {
    if (!this.canShowNextWeek) {
      return;
    }

    this.weekIndex = 1;
    this.updateWeekView();
  }

  showCurrentWeek(): void {
    if (!this.canShowCurrentWeek) {
      return;
    }

    this.weekIndex = 0;
    this.updateWeekView();
  }

  formatAppointmentType(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  private async loadAppointmentTypes(): Promise<void> {
    this.error = '';

    try {
      const response = await fetch('http://localhost:8000/availability/appointment-types', {
        cache: 'no-store'
      });

      if (!response.ok) {
        this.error = 'Unable to load appointment types right now.';
        return;
      }

      this.appointmentTypeOptions = await response.json() as AppointmentTypeOption[];
    } catch {
      this.error = 'Unable to load appointment types right now.';
    }
  }

  private async loadCalendar(): Promise<void> {
    this.error = '';
    this.slots = [];
    this.filteredSlots = [];
    this.visibleWeekDays = [];
    this.visibleWeekSlotsByDay = new Map<string, CalendarSlot[]>();

    if (!this.selectedAppointmentType) {
      return;
    }

    try {
      const response = await fetch(
        `http://localhost:8000/availability/calendar?days=14&appointment_type=${encodeURIComponent(this.selectedAppointmentType)}`,
        {
          cache: 'no-store'
        }
      );

      if (!response.ok) {
        this.error = 'Unable to load available slots right now.';
        this.resetCalendar();
        return;
      }

      this.slots = (await response.json() as CalendarSlot[])
        .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
      this.updateFilteredSlots();
    } catch {
      this.error = 'Unable to load available slots right now.';
      this.resetCalendar();
    }
  }

  private resetCalendar(): void {
    this.slots = [];
    this.filteredSlots = [];
    this.visibleWeekDays = [];
    this.visibleWeekSlotsByDay = new Map<string, CalendarSlot[]>();
  }

  private matchesCriteria(slot: CalendarSlot): boolean {
    if (slot.appointment_type !== this.selectedAppointmentType) {
      return false;
    }

    if (this.selectedTimeOfDay === 'all') {
      return true;
    }

    const hour = Number(slot.time.split(':')[0]);
    if (this.selectedTimeOfDay === 'morning') {
      return hour < 12;
    }

    return hour >= 12;
  }

  private updateFilteredSlots(): void {
    if (!this.selectedAppointmentType) {
      this.filteredSlots = [];
      this.visibleWeekDays = [];
      this.visibleWeekSlotsByDay = new Map<string, CalendarSlot[]>();
      return;
    }

    this.filteredSlots = this.slots.filter((slot) => slot.is_available && this.matchesCriteria(slot));
    this.updateWeekView();
  }

  private updateWeekView(): void {
    const start = new Date(this.currentWeekStart);
    start.setDate(start.getDate() + (this.weekIndex * 7));

    this.visibleWeekDays = [];
    this.visibleWeekSlotsByDay = new Map<string, CalendarSlot[]>();

    for (let offset = 0; offset < 7; offset += 1) {
      const dayDate = new Date(start);
      dayDate.setDate(start.getDate() + offset);
      const dayKey = this.formatDateKey(dayDate);

      const daySlots = this.filteredSlots.filter((slot) => slot.date === dayKey);
      this.visibleWeekDays.push({
        key: dayKey,
        date: dayDate,
        label: dayDate.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
      });
      this.visibleWeekSlotsByDay.set(dayKey, daySlots);
    }
  }

  slotsForDay(dayKey: string): CalendarSlot[] {
    return this.visibleWeekSlotsByDay.get(dayKey) ?? [];
  }

  private formatDateKey(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  private getStartOfDay(input: Date): Date {
    const date = new Date(input);
    date.setHours(0, 0, 0, 0);
    return date;
  }

  private getStartOfWeek(input: Date): Date {
    const date = this.getStartOfDay(input);
    const day = date.getDay();
    const diffToMonday = day === 0 ? -6 : 1 - day;
    date.setDate(date.getDate() + diffToMonday);
    return date;
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

}

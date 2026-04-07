import { DatePipe, NgFor, NgIf } from '@angular/common';
import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AppointmentTypeOption, AppointmentTypeOptionsService } from '../appointment-type-options.service';
import { getClientSession } from '../session';

type SlotStatus = 'available' | 'blocked' | 'booked';
type TimeOfDayFilter = 'all' | 'morning' | 'afternoon';

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

interface AppointmentBookingResponse {
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
  selector: 'app-availability-calendar',
  standalone: true,
  imports: [RouterLink, NgIf, NgFor, DatePipe, FormsModule],
  templateUrl: './availability-calendar.component.html',
  styleUrl: './availability-calendar.component.css'
})
export class AvailabilityCalendarComponent implements OnInit {
  readonly session = getClientSession();
  readonly role = this.session.role;
  readonly sessionEmail = this.session.requestEmail;
  readonly currentWeekStart = this.getStartOfWeek(new Date());

  slots: CalendarSlot[] = [];
  filteredSlots: CalendarSlot[] = [];
  visibleWeekDays: CalendarDay[] = [];
  visibleWeekSlotsByDay = new Map<string, CalendarSlot[]>();
  appointmentTypeOptions: AppointmentTypeOption[] = [];
  error = '';
  weekIndex = 0;

  selectedTimeOfDay: TimeOfDayFilter = 'all';
  selectedAppointmentType = 'checkup';
  selectedBookingSlot: CalendarSlot | null = null;
  bookingNotes = '';
  bookingError = '';
  confirmedBooking: AppointmentBookingResponse | null = null;
  isBooking = false;
  private isBootstrapping = true;

  constructor(
    private cdr: ChangeDetectorRef,
    private readonly appointmentTypeOptionsService: AppointmentTypeOptionsService,
  ) {}

  ngOnInit(): void {
    void this.loadCalendar({ suppressErrors: true });
    void this.loadAppointmentTypes();
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

  async onAppointmentTypeChange(value?: string): Promise<void> {
    if (typeof value === 'string') {
      this.selectedAppointmentType = value;
    }
    this.weekIndex = 0;
    this.clearBookingState();
    await this.loadCalendar();
  }

  onTimeOfDayChange(): void {
    this.updateFilteredSlots();
  }

  setTimeOfDay(value: TimeOfDayFilter): void {
    if (this.selectedTimeOfDay === value) {
      return;
    }

    this.selectedTimeOfDay = value;
    this.onTimeOfDayChange();
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
    return value
      .split('_')
      .map((segment) => segment
        .split('-')
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join('-'))
      .join(' ');
  }

  private getCalendarSummary(appointment: AppointmentBookingResponse): string {
    return `Health Center Appointment: ${this.formatAppointmentType(appointment.appointment_type)}`;
  }

  private toUtcCalendarTimestamp(value: string): string {
    const parsed = new Date(value);
    return parsed.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
  }

  getGoogleCalendarUrl(appointment: AppointmentBookingResponse): string {
    const params = new URLSearchParams({
      action: 'TEMPLATE',
      text: this.getCalendarSummary(appointment),
      dates: `${this.toUtcCalendarTimestamp(appointment.start_time)}/${this.toUtcCalendarTimestamp(appointment.end_time)}`,
      details: appointment.notes || 'No notes provided.'
    });

    return `https://calendar.google.com/calendar/render?${params.toString()}`;
  }

  getOutlookCalendarUrl(appointment: AppointmentBookingResponse): string {
    const params = new URLSearchParams({
      subject: this.getCalendarSummary(appointment),
      startdt: new Date(appointment.start_time).toISOString(),
      enddt: new Date(appointment.end_time).toISOString(),
      body: appointment.notes || 'No notes provided.'
    });
    return `https://outlook.office.com/calendar/0/deeplink/compose?${params.toString()}`;
  }

  getAppleCalendarDownloadUrl(appointment: AppointmentBookingResponse): string {
    return `/api/availability/appointments/${appointment.id}/ics?student_email=${encodeURIComponent(this.sessionEmail)}`;
  }

  beginBooking(slot: CalendarSlot): void {
    if (this.role !== 'user') {
      return;
    }

    this.selectedBookingSlot = slot;
    this.bookingNotes = '';
    this.bookingError = '';
    this.confirmedBooking = null;
  }

  cancelBooking(): void {
    this.selectedBookingSlot = null;
    this.bookingNotes = '';
    this.bookingError = '';
  }

  closeBookingDrawer(): void {
    this.selectedBookingSlot = null;
    this.confirmedBooking = null;
    this.bookingNotes = '';
    this.bookingError = '';
  }

  async submitBooking(): Promise<void> {
    if (!this.selectedBookingSlot || !this.selectedAppointmentType) {
      return;
    }

    this.isBooking = true;
    this.bookingError = '';
    this.confirmedBooking = null;

    try {
      const response = await fetch('/api/availability/appointments', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          student_email: this.sessionEmail,
          appointment_type: this.selectedAppointmentType,
          start_time: this.selectedBookingSlot.start_time,
          notes: this.bookingNotes.trim() || null
        })
      });

      if (!response.ok) {
        const detail = await this.tryReadError(response);
        throw new Error(detail || `Unable to book appointment (HTTP ${response.status}).`);
      }

      const appointment = await response.json() as AppointmentBookingResponse;
      const currentWeekIndex = this.weekIndex;
      await this.loadCalendar();
      this.weekIndex = currentWeekIndex;
      this.updateWeekView();
      this.confirmedBooking = appointment;
      this.cancelBooking();
      this.cdr.detectChanges();
    } catch (error) {
      if (error instanceof Error) {
        this.bookingError = error.message;
      } else {
        this.bookingError = 'Unable to book appointment right now.';
      }
    } finally {
      this.isBooking = false;
    }
  }

  private async loadAppointmentTypes(): Promise<void> {
    this.appointmentTypeOptions = await this.appointmentTypeOptionsService.getAppointmentTypes();
    const defaultType = this.getDefaultAppointmentType();
    const currentType = this.selectedAppointmentType.trim().toLowerCase();
    const hasCurrentType = this.appointmentTypeOptions.some(
      (option) => option.appointment_type.trim().toLowerCase() === currentType
    );

    if (!hasCurrentType) {
      this.selectedAppointmentType = defaultType ?? '';
      if (this.selectedAppointmentType) {
        await this.onAppointmentTypeChange();
      } else {
        this.resetCalendar();
      }
    }

    this.isBootstrapping = false;
    this.cdr.detectChanges();
  }

  private getDefaultAppointmentType(): string | null {
    if (this.appointmentTypeOptions.length === 0) {
      return null;
    }

    const normalizeType = (value: string) => value.toLowerCase().replace(/[^a-z]/g, '');
    const preferred = this.appointmentTypeOptions.find(
      (option) => normalizeType(option.appointment_type) === 'checkup'
    );
    return preferred?.appointment_type ?? this.appointmentTypeOptions[0]?.appointment_type ?? null;
  }

  private async loadCalendar(options: { suppressErrors?: boolean } = {}): Promise<void> {
    const { suppressErrors = false } = options;
    this.error = '';
    this.slots = [];
    this.filteredSlots = [];
    //this.visibleWeekDays = [];
    //this.visibleWeekSlotsByDay = new Map<string, CalendarSlot[]>();

    if (!this.selectedAppointmentType) {
      this.resetCalendar();
      return;
    }

    try {
      const response = await fetch(
        `/api/availability/calendar?days=14&appointment_type=${encodeURIComponent(this.selectedAppointmentType)}`,
        {
          cache: 'no-store'
        }
      );

      if (!response.ok) {
        if (!suppressErrors && !this.isBootstrapping) {
          this.error = 'Unable to load available slots right now.';
        }
        this.resetCalendar();
        return;
      }

      this.slots = (await response.json() as CalendarSlot[])
        .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
      this.updateFilteredSlots();
    } catch {
      if (!suppressErrors && !this.isBootstrapping) {
        this.error = 'Unable to load available slots right now.';
      }
      this.resetCalendar();
    } finally {
      this.cdr.detectChanges();
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
    if (
      this.selectedBookingSlot
      && !this.filteredSlots.some((slot) => slot.start_time === this.selectedBookingSlot?.start_time)
    ) {
      this.selectedBookingSlot = null;
      this.bookingNotes = '';
    }
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
      const dayOfWeek = dayDate.getDay();
      if (dayOfWeek === 0 || dayOfWeek === 6) {
        continue;
      }

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

  private clearBookingState(): void {
    this.selectedBookingSlot = null;
    this.bookingNotes = '';
    this.bookingError = '';
    this.confirmedBooking = null;
  }


  private async tryReadError(response: Response): Promise<string | null> {
    try {
      const payload = await response.json() as { detail?: string };
      return payload.detail || null;
    } catch {
      return null;
    }
  }
}

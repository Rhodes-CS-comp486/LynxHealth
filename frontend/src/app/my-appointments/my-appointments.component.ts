import { DatePipe, NgFor, NgIf } from '@angular/common';
import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AppointmentTypeOptionsService } from '../appointment-type-options.service';
import { getClientSession } from '../session';

type RescheduleViewMode = 'quick' | 'card';

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

interface CalendarSlot {
  date: string;
  time: string;
  duration_minutes: number;
  appointment_type: string;
  start_time: string;
  end_time: string;
  status: string;
  is_available: boolean;
  is_blocked: boolean;
  is_booked: boolean;
}

interface RescheduleDayGroup {
  dateKey: string;
  slots: CalendarSlot[];
}

@Component({
  selector: 'app-my-appointments',
  standalone: true,
  imports: [RouterLink, NgIf, NgFor, DatePipe],
  templateUrl: './my-appointments.component.html',
  styleUrl: './my-appointments.component.css'
})
export class MyAppointmentsComponent implements OnInit {
  constructor(
    private readonly cdr: ChangeDetectorRef,
    private readonly appointmentTypeOptionsService: AppointmentTypeOptionsService,
  ) {}
  readonly session = getClientSession();
  readonly sessionEmail = this.session.requestEmail;
  readonly role = this.session.role;

  appointments: BookedAppointment[] = [];
  isLoading = true;
  cancelingAppointmentId: number | null = null;
  pendingCancelAppointmentId: number | null = null;
  calendarPanelAppointmentId: number | null = null;
  reschedulingAppointmentId: number | null = null;
  reschedulePanelAppointmentId: number | null = null;
  isLoadingRescheduleOptions = false;
  rescheduleOptions: RescheduleDayGroup[] = [];
  rescheduleWeekKeys: string[] = [];
  rescheduleWeekIndex = 0;
  selectedRescheduleStartTime: string | null = null;
  rescheduleViewMode: RescheduleViewMode = 'quick';
  successMessage = '';
  error = '';
  saveError = '';
  saveSuccess = '';
  editingAppointmentId: number | null = null;
  savingAppointmentId: number | null = null;
  draftNotesById: Record<number, string> = {};

  ngOnInit(): void {
    if (this.role === 'user') {
      this.appointmentTypeOptionsService.prefetchAppointmentTypes();
    }

    this.loadAppointments();
  }

  prefetchAppointmentTypes(): void {
    if (this.role !== 'user') {
      return;
    }

    this.appointmentTypeOptionsService.prefetchAppointmentTypes();
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

  private getCalendarSummary(appointment: BookedAppointment): string {
    return `Health Center Appointment: ${this.formatAppointmentType(appointment.appointment_type)}`;
  }

  private toUtcCalendarTimestamp(value: string): string {
    const parsed = new Date(value);
    return parsed.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
  }

  getGoogleCalendarUrl(appointment: BookedAppointment): string {
    const params = new URLSearchParams({
      action: 'TEMPLATE',
      text: this.getCalendarSummary(appointment),
      dates: `${this.toUtcCalendarTimestamp(appointment.start_time)}/${this.toUtcCalendarTimestamp(appointment.end_time)}`,
      details: appointment.notes || 'No notes provided.'
    });
    return `https://calendar.google.com/calendar/render?${params.toString()}`;
  }

  getOutlookCalendarUrl(appointment: BookedAppointment): string {
    const params = new URLSearchParams({
      subject: this.getCalendarSummary(appointment),
      startdt: new Date(appointment.start_time).toISOString(),
      enddt: new Date(appointment.end_time).toISOString(),
      body: appointment.notes || 'No notes provided.'
    });
    return `https://outlook.office.com/calendar/0/deeplink/compose?${params.toString()}`;
  }

  getAppleCalendarDownloadUrl(appointment: BookedAppointment): string {
    return `/api/availability/appointments/${appointment.id}/ics?student_email=${encodeURIComponent(this.sessionEmail)}`;
  }

  toggleCalendarPanel(appointmentId: number): void {
    this.calendarPanelAppointmentId = this.calendarPanelAppointmentId === appointmentId ? null : appointmentId;
    if (this.calendarPanelAppointmentId === appointmentId) {
      this.pendingCancelAppointmentId = null;
      if (this.reschedulePanelAppointmentId === appointmentId) {
        this.closeReschedulePanel();
      }
    }
  }

  get visibleRescheduleOptions(): RescheduleDayGroup[] {
    const activeWeekKey = this.rescheduleWeekKeys[this.rescheduleWeekIndex];
    if (!activeWeekKey) {
      return [];
    }

    return this.rescheduleOptions.filter((group) => this.getWeekStartKey(new Date(group.slots[0].start_time)) === activeWeekKey);
  }

  get canShowPreviousRescheduleWeek(): boolean {
    return this.rescheduleWeekIndex > 0;
  }

  get canShowNextRescheduleWeek(): boolean {
    return this.rescheduleWeekIndex < this.rescheduleWeekKeys.length - 1;
  }

  get rescheduleWeekRangeLabel(): string {
    const visibleOptions = this.visibleRescheduleOptions;
    if (visibleOptions.length === 0) {
      return '';
    }

    const first = new Date(visibleOptions[0].slots[0].start_time);
    const last = new Date(visibleOptions[visibleOptions.length - 1].slots[0].start_time);
    return `${first.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} - ${last.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`;
  }


  async openReschedulePanel(appointment: BookedAppointment): Promise<void> {
    if (this.role !== 'user') {
      return;
    }

    if (this.reschedulePanelAppointmentId === appointment.id) {
      this.closeReschedulePanel();
      return;
    }

    this.reschedulePanelAppointmentId = appointment.id;
    this.isLoadingRescheduleOptions = true;
    this.rescheduleOptions = [];
    this.rescheduleWeekKeys = [];
    this.rescheduleWeekIndex = 0;
    this.selectedRescheduleStartTime = null;
    this.rescheduleViewMode = 'quick';
    this.error = '';
    this.successMessage = '';

    try {
      const response = await fetch(
        `/api/availability/calendar?days=14&appointment_type=${encodeURIComponent(appointment.appointment_type)}`,
        { cache: 'no-store' }
      );
      if (!response.ok) {
        const detail = await this.tryReadError(response);
        throw new Error(detail || `Unable to load available times (HTTP ${response.status}).`);
      }

      const allSlots = await response.json() as CalendarSlot[];
      const currentAppointmentStart = new Date(appointment.start_time).toISOString();
      const availableSlots = allSlots.filter((slot) => (
        slot.is_available && new Date(slot.start_time).toISOString() !== currentAppointmentStart
      ));

      const groupedSlots = new Map<string, CalendarSlot[]>();
      for (const slot of availableSlots) {
        const dateKey = this.toLocalDateKey(new Date(slot.start_time));
        const existing = groupedSlots.get(dateKey);
        if (existing) {
          existing.push(slot);
        } else {
          groupedSlots.set(dateKey, [slot]);
        }
      }

      this.rescheduleOptions = Array.from(groupedSlots.entries())
        .map(([dateKey, slots]) => ({
          dateKey,
          slots: slots.sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())
        }))
        .sort((a, b) => a.dateKey.localeCompare(b.dateKey));

      this.rescheduleWeekKeys = Array.from(new Set(
        this.rescheduleOptions.map((group) => this.getWeekStartKey(new Date(group.slots[0].start_time)))
      ));
      this.rescheduleWeekIndex = 0;

      if (availableSlots.length > 0) {
        this.selectedRescheduleStartTime = availableSlots
          .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())[0]
          ?.start_time || null;
      }
    } catch (error) {
      if (error instanceof Error) {
        this.error = error.message;
      } else {
        this.error = 'Unable to reschedule appointment right now.';
      }
    } finally {
      this.isLoadingRescheduleOptions = false;
      this.cdr.detectChanges();
    }
  }

  closeReschedulePanel(): void {
    this.reschedulePanelAppointmentId = null;
    this.isLoadingRescheduleOptions = false;
    this.rescheduleOptions = [];
    this.rescheduleWeekKeys = [];
    this.rescheduleWeekIndex = 0;
    this.selectedRescheduleStartTime = null;
    this.rescheduleViewMode = 'quick';
  }

  selectRescheduleTime(startTime: string): void {
    this.selectedRescheduleStartTime = startTime;
  }

  setRescheduleViewMode(mode: RescheduleViewMode): void {
    this.rescheduleViewMode = mode;
  }

  showPreviousRescheduleWeek(): void {
    if (!this.canShowPreviousRescheduleWeek) {
      return;
    }

    this.rescheduleWeekIndex -= 1;
  }

  showNextRescheduleWeek(): void {
    if (!this.canShowNextRescheduleWeek) {
      return;
    }

    this.rescheduleWeekIndex += 1;
  }

  async confirmReschedule(appointment: BookedAppointment): Promise<void> {
    if (this.role !== 'user' || !this.selectedRescheduleStartTime) {
      return;
    }

    this.reschedulingAppointmentId = appointment.id;
    this.error = '';
    this.successMessage = '';

    try {
      const response = await fetch(`/api/availability/appointments/${appointment.id}/reschedule`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          student_email: this.sessionEmail,
          start_time: this.selectedRescheduleStartTime
        })
      });

      if (!response.ok) {
        const detail = await this.tryReadError(response);
        throw new Error(detail || `Unable to reschedule appointment (HTTP ${response.status}).`);
      }

      const updated = await response.json() as BookedAppointment;
      this.appointments = this.appointments
        .map((item) => (item.id === updated.id ? updated : item))
        .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
      this.closeReschedulePanel();
      this.successMessage = 'Appointment rescheduled.';
    } catch (error) {
      if (error instanceof Error) {
        this.error = error.message;
      } else {
        this.error = 'Unable to reschedule appointment right now.';
      }
    } finally {
      this.reschedulingAppointmentId = null;
      this.cdr.detectChanges();
    }
  }

  async cancelAppointment(appointmentId: number): Promise<void> {
    if (this.role !== 'user') {
      return;
    }

    this.pendingCancelAppointmentId = null;
    this.cancelingAppointmentId = appointmentId;
    this.error = '';
    this.successMessage = '';

    try {
      const response = await fetch(
        `/api/availability/appointments/${appointmentId}?student_email=${encodeURIComponent(this.sessionEmail)}`,
        {
          method: 'DELETE'
        }
      );

      if (!response.ok) {
        const detail = await this.tryReadError(response);
        throw new Error(detail || `Unable to cancel appointment (HTTP ${response.status}).`);
      }

      this.appointments = this.appointments.filter((appointment) => appointment.id !== appointmentId);
      this.successMessage = 'Appointment has been cancelled.';
    } catch (error) {
      if (error instanceof Error) {
        this.error = error.message;
      } else {
        this.error = 'Unable to cancel appointment right now.';
      }
    } finally {
      this.cancelingAppointmentId = null;
      this.cdr.detectChanges();
    }
  }

  requestCancelConfirmation(appointmentId: number): void {
    if (this.role !== 'user' || this.cancelingAppointmentId === appointmentId) {
      return;
    }

    if (this.reschedulePanelAppointmentId === appointmentId) {
      this.closeReschedulePanel();
    }
    if (this.calendarPanelAppointmentId === appointmentId) {
      this.calendarPanelAppointmentId = null;
    }

    this.pendingCancelAppointmentId = appointmentId;
    this.error = '';
    this.successMessage = '';
  }

  dismissCancelConfirmation(): void {
    this.pendingCancelAppointmentId = null;
  }

  startEditing(appointment: BookedAppointment): void {
    this.editingAppointmentId = appointment.id;
    this.closeReschedulePanel();
    this.calendarPanelAppointmentId = null;
    this.saveError = '';
    this.saveSuccess = '';
    this.draftNotesById[appointment.id] = appointment.notes || '';
  }

  cancelEditing(): void {
    this.editingAppointmentId = null;
    this.saveError = '';
  }

  updateDraftNotes(appointmentId: number, value: string): void {
    this.draftNotesById[appointmentId] = value;
  }

  async saveNotes(appointment: BookedAppointment): Promise<void> {
    this.savingAppointmentId = appointment.id;
    this.saveError = '';
    this.saveSuccess = '';

    try {
      const response = await fetch(`/api/availability/appointments/${appointment.id}/notes`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          student_email: this.sessionEmail,
          notes: this.draftNotesById[appointment.id] ?? ''
        })
      });

      if (!response.ok) {
        const detail = await this.tryReadError(response);
        throw new Error(detail || `Unable to update notes (HTTP ${response.status}).`);
      }

      const updated = await response.json() as BookedAppointment;
      this.appointments = this.appointments.map((item) => (
        item.id === updated.id ? updated : item
      ));
      this.editingAppointmentId = null;
      this.saveSuccess = 'Appointment notes updated.';
    } catch (error) {
      if (error instanceof Error) {
        this.saveError = error.message;
      } else {
        this.saveError = 'Unable to update notes right now.';
      }
    } finally {
      this.savingAppointmentId = null;
      this.cdr.detectChanges();
    }
  }

  private async loadAppointments(): Promise<void> {
    if (this.role !== 'user') {
      this.error = 'My Appointments is only available for student accounts.';
      this.isLoading = false;
      this.cdr.detectChanges();
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
      this.cdr.detectChanges();
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

  private toLocalDateKey(value: Date): string {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  private getWeekStartKey(value: Date): string {
    const start = new Date(value);
    const day = start.getDay();
    const diff = day === 0 ? -6 : 1 - day;
    start.setDate(start.getDate() + diff);
    return this.toLocalDateKey(start);
  }

}

import { DatePipe, NgFor, NgIf } from '@angular/common';
import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';

type SessionRole = 'admin' | 'user';

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
  constructor(private readonly cdr: ChangeDetectorRef) {}
  readonly sessionEmail = this.getSessionEmail();
  readonly role = this.getRole();

  appointments: BookedAppointment[] = [];
  isLoading = true;
  cancelingAppointmentId: number | null = null;
  reschedulingAppointmentId: number | null = null;
  reschedulePanelAppointmentId: number | null = null;
  isLoadingRescheduleOptions = false;
  rescheduleOptions: RescheduleDayGroup[] = [];
  selectedRescheduleStartTime: string | null = null;
  successMessage = '';
  error = '';
  saveError = '';
  saveSuccess = '';
  editingAppointmentId: number | null = null;
  savingAppointmentId: number | null = null;
  draftNotesById: Record<number, string> = {};

  ngOnInit(): void {
    this.loadAppointments();
  }

  formatAppointmentType(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
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
    this.selectedRescheduleStartTime = null;
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
    this.selectedRescheduleStartTime = null;
  }

  selectRescheduleTime(startTime: string): void {
    this.selectedRescheduleStartTime = startTime;
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
      this.successMessage = 'Appointment canceled.';
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

  startEditing(appointment: BookedAppointment): void {
    this.editingAppointmentId = appointment.id;
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

  private getRole(): SessionRole {
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
      return 'student@lynxhealth.local';
    }

    try {
      const parsed = JSON.parse(data) as { email?: string };
      const normalized = parsed.email?.trim().toLowerCase();
      return normalized || 'student@lynxhealth.local';
    } catch {
      return 'student@lynxhealth.local';
    }
  }

  private getSessionStorageItem(): string | null {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return null;
    }

    return localStorage.getItem('lynxSession');
  }
}

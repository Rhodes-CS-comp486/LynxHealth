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

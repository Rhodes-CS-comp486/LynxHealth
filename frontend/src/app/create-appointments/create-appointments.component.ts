import { DatePipe, NgClass, NgFor, NgIf } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

interface AvailabilitySlot {
  id: number;
  date: string;
  time: string;
  duration_minutes: number;
  appointment_type: string;
  start_time: string;
  end_time: string;
  is_booked: boolean;
}

interface CalendarDay {
  date: Date;
  key: string;
  slots: AvailabilitySlot[];
}

@Component({
  selector: 'app-create-appointments',
  standalone: true,
  imports: [RouterLink, NgIf, NgFor, FormsModule, DatePipe, NgClass],
  templateUrl: './create-appointments.component.html',
  styleUrl: './create-appointments.component.css'
})
export class CreateAppointmentsComponent implements OnInit {
  readonly role = this.getRole();
  readonly sessionEmail = this.getSessionEmail();

  slots: AvailabilitySlot[] = [];
  slotDate = '';
  slotTime = '';
  durationMinutes = 30;
  appointmentType = 'immunization';
  adminMessage = '';
  adminError = '';
  isSaving = false;

  weekStart = this.getWeekStart(new Date());
  calendarDays: CalendarDay[] = [];

  readonly appointmentTypes = ['immunization', 'testing', 'counseling', 'other', 'prescription'];

  ngOnInit(): void {
    this.buildCalendar();
    this.loadSlots();

    if (this.role !== 'admin') {
      this.adminError = 'Only admins can create appointment slots.';
    }
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

  async createSlot(): Promise<void> {
    if (this.role !== 'admin') {
      this.adminError = 'Only admins can create appointment slots.';
      return;
    }

    if (!this.slotDate || !this.slotTime || !this.durationMinutes || !this.appointmentType) {
      this.adminError = 'Date, time, duration, and appointment type are required.';
      return;
    }

    this.isSaving = true;
    this.adminError = '';
    this.adminMessage = '';

    try {
      const response = await fetch('http://localhost:8000/availability/slots', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          admin_email: this.sessionEmail,
          date: this.slotDate,
          time: this.slotTime,
          duration_minutes: Number(this.durationMinutes),
          appointment_type: this.appointmentType
        })
      });

      const payload = await response.json();

      if (!response.ok) {
        this.adminError = payload?.detail || 'Unable to create slot.';
        return;
      }

      this.adminMessage = 'Appointment slot created successfully.';
      this.slotDate = '';
      this.slotTime = '';
      this.durationMinutes = 30;
      this.appointmentType = 'immunization';
      await this.loadSlots();
    } catch {
      this.adminError = 'Could not connect to API. Start the backend on port 8000.';
    } finally {
      this.isSaving = false;
    }
  }

  private async loadSlots(): Promise<void> {
    try {
      const response = await fetch('http://localhost:8000/availability/slots');
      if (!response.ok) {
        this.slots = [];
        this.buildCalendar();
        return;
      }

      this.slots = await response.json() as AvailabilitySlot[];
      this.buildCalendar();
    } catch {
      this.slots = [];
      this.buildCalendar();
    }
  }

  private buildCalendar(): void {
    const slotMap = new Map<string, AvailabilitySlot[]>();
    for (const slot of this.slots) {
      const key = this.formatDateKey(new Date(slot.start_time));
      const existing = slotMap.get(key) || [];
      existing.push(slot);
      slotMap.set(key, existing);
    }

    this.calendarDays = [];
    for (let i = 0; i < 7; i += 1) {
      const dayDate = new Date(this.weekStart);
      dayDate.setDate(this.weekStart.getDate() + i);
      const key = this.formatDateKey(dayDate);
      const daySlots = (slotMap.get(key) || []).slice().sort((a, b) =>
        new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
      );

      this.calendarDays.push({
        date: dayDate,
        key,
        slots: daySlots
      });
    }
  }

  private getWeekStart(date: Date): Date {
    const start = new Date(date);
    start.setHours(0, 0, 0, 0);
    start.setDate(start.getDate() - start.getDay());
    return start;
  }

  private formatDateKey(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  trackByKey(_index: number, day: CalendarDay): string {
    return day.key;
  }

  private getRole(): 'admin' | 'user' {
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
    const data = localStorage.getItem('lynxSession');

    if (!data) {
      return 'user@lynxhealth.local';
    }

    try {
      const parsed = JSON.parse(data) as { email?: string };
      return parsed.email || 'user@lynxhealth.local';
    } catch {
      return 'user@lynxhealth.local';
    }
  }
}

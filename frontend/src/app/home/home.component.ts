import { DatePipe, NgFor, NgIf } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';

type SessionRole = 'admin' | 'user';

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

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, NgIf, NgFor, DatePipe],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css'
})
export class HomeComponent implements OnInit {
  readonly role = this.getRole();

  slots: AvailabilitySlot[] = [];

  ngOnInit(): void {
    this.loadSlots();
  }

  private async loadSlots(): Promise<void> {
    try {
      const endpoint = this.role === 'user'
        ? 'http://localhost:8000/availability/slots?students_only=true'
        : 'http://localhost:8000/availability/slots';

      const response = await fetch(endpoint);
      if (!response.ok) {
        return;
      }

      this.slots = await response.json() as AvailabilitySlot[];
    } catch {
      this.slots = [];
    }
  }

  private getRole(): SessionRole {
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

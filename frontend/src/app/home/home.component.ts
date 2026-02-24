import { DatePipe, NgFor, NgIf } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

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
  role: SessionRole = 'user';
  slots: AvailabilitySlot[] = [];

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.handleSamlCallback();
    this.role = this.getRole();
    this.loadSlots();
  }

  private handleSamlCallback(): void {
    if (typeof window === 'undefined') return;

    const params = new URLSearchParams(window.location.search);
    const session = params.get('session');

    if (session) {
      try {
        const decoded = decodeURIComponent(session);
        localStorage.setItem('lynxSession', decoded);
        // Clean the URL so session param doesn't stay in the address bar
        window.history.replaceState({}, '', '/home');
      } catch {
        // ignore
      }
    }
  }

  private async loadSlots(): Promise<void> {
    try {
      const endpoint = this.role === 'user'
        ? '/api/availability/slots?students_only=true'
        : '/api/availability/slots';

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

  private getSessionStorageItem(): string | null {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return null;
    }

    return localStorage.getItem('lynxSession');
  }
}

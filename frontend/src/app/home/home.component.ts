import { NgIf } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AppointmentTypeOptionsService } from '../appointment-type-options.service';

type SessionRole = 'admin' | 'user';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, NgIf],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css'
})
export class HomeComponent implements OnInit {
  role: SessionRole = 'user';

  constructor(
    private readonly router: Router,
    private readonly appointmentTypeOptionsService: AppointmentTypeOptionsService,
  ) {}

  ngOnInit(): void {
    this.handleSamlCallback();
    this.role = this.getRole();

    if (this.shouldRedirectToMyAppointments()) {
      this.router.navigate(['/my-appointments'], { replaceUrl: true });
    }

    if (this.role === 'user') {
      this.appointmentTypeOptionsService.prefetchAppointmentTypes();
    }

    this.loadSlots();
  }

  prefetchAppointmentTypes(): void {
    if (this.role !== 'user') {
      return;
    }

    this.appointmentTypeOptionsService.prefetchAppointmentTypes();
  }

  private handleSamlCallback(): void {
    if (typeof window === 'undefined') return;

    const params = new URLSearchParams(window.location.search);
    const session = params.get('session');

    if (session) {
      try {
        const decoded = decodeURIComponent(session);
        localStorage.setItem('lynxSession', decoded);
        window.history.replaceState({}, '', '/home');
      } catch {
        // ignore
      }
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

  private shouldRedirectToMyAppointments(): boolean {
    if (typeof window === 'undefined') {
      return false;
    }

    return window.location.hash === '#my-appointments';
  }
}

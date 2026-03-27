import { NgIf } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { getClientSession, saveClientSession, SessionRole } from '../session';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, NgIf],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css'
})
export class HomeComponent implements OnInit {
  role: SessionRole = 'user';

  constructor(private readonly router: Router) {}

  ngOnInit(): void {
    this.handleSamlCallback();
    this.role = this.getRole();

    if (this.shouldRedirectToMyAppointments()) {
      this.router.navigate(['/my-appointments'], { replaceUrl: true });
    }
  }

  private handleSamlCallback(): void {
    if (typeof window === 'undefined') return;

    const params = new URLSearchParams(window.location.search);
    const session = params.get('session');

    if (session) {
      const savedSession = saveClientSession(decodeURIComponent(session));
      if (savedSession) {
        this.role = savedSession.role;
        window.history.replaceState({}, '', '/home');
      }
    }
  }

  private getRole(): SessionRole {
    return getClientSession().role;
  }

  private shouldRedirectToMyAppointments(): boolean {
    if (typeof window === 'undefined') {
      return false;
    }

    return window.location.hash === '#my-appointments';
  }
}

import { NgIf } from '@angular/common';
import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

type SessionRole = 'admin' | 'user';

@Component({
  selector: 'app-hours',
  standalone: true,
  imports: [RouterLink, NgIf],
  templateUrl: './hours.component.html',
  styleUrl: './hours.component.css'
})
export class HoursComponent {
  readonly role: SessionRole = this.getRole();

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

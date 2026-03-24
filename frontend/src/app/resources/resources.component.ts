import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-resources',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './resources.component.html',
  styleUrl: './resources.component.css'
})
export class ResourcesComponent {
  readonly role = this.getRole();
  readonly isAdmin = this.role === 'admin';
  isEditing = false;

  toggleEditMode(): void {
    this.isEditing = !this.isEditing;
  }

  private getRole(): 'admin' | 'user' {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return 'user';
    }

    try {
      const session = localStorage.getItem('lynxSession');
      if (!session) {
        return 'user';
      }

      const parsed = JSON.parse(session) as { role?: string };
      return parsed.role === 'admin' ? 'admin' : 'user';
    } catch {
      return 'user';
    }
  }
}

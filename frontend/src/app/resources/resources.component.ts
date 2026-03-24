import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-resources',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './resources.component.html',
  styleUrl: './resources.component.css'
})
export class ResourcesComponent {
  readonly role = this.getRole();
  readonly isAdmin = this.role === 'admin';
  isEditing = false;
  section = {
    header: 'Welcome to the Student Health Center!',
    content:
      'The Rhodes College Student Health Center is committed to being an accessible and inclusive healthcare resource for our diverse student body. We offer personalized medical services, preventive care, and health education that support academic success and personal growth.'
  };

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

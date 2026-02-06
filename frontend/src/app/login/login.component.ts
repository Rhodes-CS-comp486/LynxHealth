import { NgIf } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, NgIf],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css'
})
export class LoginComponent {
  email = '';
  role: 'admin' | 'user' = 'user';
  errorMessage = '';

  constructor(private readonly router: Router) {}

  onSubmit(): void {
    const normalizedEmail = this.email.trim().toLowerCase();

    if (this.role === 'admin' && !normalizedEmail.endsWith('@admin.edu')) {
      this.errorMessage = 'Admin login requires an email ending in @admin.edu.';
      return;
    }

    this.errorMessage = '';

    const session = {
      email: normalizedEmail || `${this.role}@lynxhealth.local`,
      role: this.role
    };

    localStorage.setItem('lynxSession', JSON.stringify(session));
    this.router.navigate(['/home']);
  }
}

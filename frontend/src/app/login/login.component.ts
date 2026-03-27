import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { saveClientSession } from '../session';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css'
})
export class LoginComponent {
  email = '';
  role: 'admin' | 'user' = 'user';
  errorMessage = '';

  constructor(private readonly router: Router) {}

  loginWithSaml(): void {
    window.location.href = '/api/auth/sso/login';
  }

  testAdminLogin(): void {
    saveClientSession(JSON.stringify({
      email: 'admin@admin.edu',
      role: 'admin' as const
    }));
    this.router.navigate(['/home']);
  }
}

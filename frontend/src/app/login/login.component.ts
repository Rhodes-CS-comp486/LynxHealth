import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { saveClientSession } from '../session';

/**
 * Entry screen of the SPA.
 *
 * Production login goes through SAML SSO via ``loginWithSaml``. The
 * ``testAdminLogin`` / ``testUserLogin`` helpers short-circuit the SSO flow
 * so developers can exercise each role locally without an IdP handy.
 */
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

  testUserLogin(): void {
    saveClientSession(JSON.stringify({
      email: 'student@lynxhealth.local',
      role: 'user' as const
    }));
    this.router.navigate(['/home']);
  }
}

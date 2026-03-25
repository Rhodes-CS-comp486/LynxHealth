import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

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
    window.location.href = 'https://lynxhc.com/auth/saml/login';
  }

  testAdminLogin(): void {
    const session = {
      email: 'admin@lynxhealth.local',
      role: 'admin' as const
    };
    if (typeof window !== 'undefined' && typeof localStorage !== 'undefined') {
      localStorage.setItem('lynxSession', JSON.stringify(session));
    }
    this.router.navigate(['/home']);
  }
}

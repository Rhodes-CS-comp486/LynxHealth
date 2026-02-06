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

  constructor(private readonly router: Router) {}

  onSubmit(): void {
    const session = {
      email: this.email.trim() || `${this.role}@lynxhealth.local`,
      role: this.role
    };

    localStorage.setItem('lynxSession', JSON.stringify(session));
    this.router.navigate(['/home']);
  }
}

import { Routes } from '@angular/router';
import { HomeComponent } from './home/home.component';
import { LoginComponent } from './login/login.component';
import { CreateAppointmentsComponent } from './create-appointments/create-appointments.component';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'login'
  },
  {
    path: 'login',
    component: LoginComponent
  },
  {
    path: 'home',
    component: HomeComponent
  },
  {
    path: 'create-appointments',
    component: CreateAppointmentsComponent
  },
  {
    path: 'creatappointments',
    redirectTo: 'create-appointments'
  },
  {
    path: '**',
    redirectTo: 'login'
  }
];

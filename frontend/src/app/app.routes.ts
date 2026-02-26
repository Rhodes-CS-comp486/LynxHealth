import { Routes } from '@angular/router';
import { HomeComponent } from './home/home.component';
import { LoginComponent } from './login/login.component';
import { CreateAppointmentsComponent } from './create-appointments/create-appointments.component';
import { AvailabilityCalendarComponent } from './availability-calendar/availability-calendar.component';
import { MyAppointmentsComponent } from './my-appointments/my-appointments.component';

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
    path: 'availability-calendar',
    component: AvailabilityCalendarComponent
  },
  {
    path: 'my-appointments',
    component: MyAppointmentsComponent
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

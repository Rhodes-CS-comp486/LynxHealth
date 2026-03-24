import { NgFor, NgIf } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

type SessionRole = 'admin' | 'user';

interface ResourceSection {
  header: string;
  content: string;
  isEditing: boolean;
}

@Component({
  selector: 'app-resources',
  standalone: true,
  imports: [NgIf, NgFor, FormsModule],
  templateUrl: './resources.component.html',
  styleUrl: './resources.component.css'
})
export class ResourcesComponent {
  readonly role = this.getRole();

  sections: ResourceSection[] = [
    {
      header: 'Mental Health Support',
      content: 'Connect with campus counseling, peer support groups, and crisis hotlines available 24/7.',
      isEditing: false,
    },
    {
      header: 'Preventive Care',
      content: 'Find vaccination guidance, annual wellness recommendations, and preventive screening checklists.',
      isEditing: false,
    },
    {
      header: 'Nutrition and Fitness',
      content: 'Review healthy meal planning tips, hydration guidance, and student-friendly movement routines.',
      isEditing: false,
    },
  ];

  private originalByIndex: Record<number, Pick<ResourceSection, 'header' | 'content'>> = {};

  startEditing(index: number): void {
    if (this.role !== 'admin') {
      return;
    }

    const section = this.sections[index];
    if (!section) {
      return;
    }

    this.originalByIndex[index] = {
      header: section.header,
      content: section.content,
    };

    section.isEditing = true;
  }

  saveSection(index: number): void {
    const section = this.sections[index];
    if (!section) {
      return;
    }

    section.header = section.header.trim() || 'Untitled resource';
    section.content = section.content.trim() || 'No details provided.';
    section.isEditing = false;
    delete this.originalByIndex[index];
  }

  cancelEditing(index: number): void {
    const section = this.sections[index];
    const original = this.originalByIndex[index];

    if (!section || !original) {
      return;
    }

    section.header = original.header;
    section.content = original.content;
    section.isEditing = false;
    delete this.originalByIndex[index];
  }

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

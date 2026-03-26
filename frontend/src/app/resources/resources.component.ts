import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

interface PageSection {
  id?: number;
  page: string;
  section_key: string;
  header: string;
  content: string;
  display_order: number;
}

@Component({
  selector: 'app-resources',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './resources.component.html',
  styleUrl: './resources.component.css'
})
export class ResourcesComponent implements OnInit {
  role: 'admin' | 'user' = 'user';
  isAdmin = false;
  isEditing = false;
  isSaving = false;
  sectionsLoaded = false;

  sections: PageSection[] = [];
  addedSections: PageSection[] = [];

  private apiUrl = 'http://localhost:8000/pages';

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.role = this.getRole();
    this.isAdmin = this.role === 'admin';
    this.loadSections();
  }

  loadSections(): void {
    this.http.get<PageSection[]>(`${this.apiUrl}/resources/sections`).subscribe({
      next: (sections) => {
        const defaultKeys = [
          'welcome', 'mission', 'visiting', 'services', 'cancellation_policy',
          'emergency_care', 'payment', 'self_care', 'allergy_shots', 'records',
          'opioid_policy', 'class_excuses'
        ];

        this.sections = [];
        this.addedSections = [];

        for (const s of sections) {
          if (defaultKeys.includes(s.section_key)) {
            this.sections.push(s);
          } else {
            this.addedSections.push(s);
          }
        }

        this.sectionsLoaded = true;
      },
      error: (err) => {
        console.error('Failed to load sections:', err);
        this.sectionsLoaded = true;
      }
    });
  }

  getSection(key: string): PageSection | undefined {
    return this.sections.find(s => s.section_key === key);
  }

  toggleEditMode(): void {
    if (this.isEditing) {
      this.saveAllSections();
    } else {
      this.isEditing = true;
    }
  }

  saveAllSections(): void {
    // Filter out custom sections with empty header or content
    const validAdded = this.addedSections.filter(
      s => s.header.trim() && s.content.trim()
    );

    // Check if any custom sections are incomplete (has one field but not the other)
    const incomplete = this.addedSections.filter(
      s => (s.header.trim() && !s.content.trim()) || (!s.header.trim() && s.content.trim())
    );

    if (incomplete.length > 0) {
      alert('Please fill in both header and content for all new sections, or remove empty ones.');
      return;
    }

    this.isSaving = true;
    const email = this.getEmail();

    const allSections = [...this.sections, ...validAdded];

    const payload = {
      admin_email: email,
      sections: allSections.map((s, i) => ({
        section_key: s.section_key,
        header: s.header,
        content: s.content,
        display_order: i,
      }))
    };

    this.http.put<PageSection[]>(`${this.apiUrl}/resources/sections`, payload).subscribe({
      next: () => {
        this.isEditing = false;
        this.isSaving = false;
        this.loadSections();
      },
      error: (err) => {
        console.error('Failed to save sections:', err);
        this.isSaving = false;
      }
    });
  }

  addSection(): void {
    const newSection: PageSection = {
      page: 'resources',
      section_key: `custom_${Date.now()}`,
      header: '',
      content: '',
      display_order: this.sections.length + this.addedSections.length,
    };
    this.addedSections.push(newSection);
  }

  removeAddedSection(index: number): void {
    const section = this.addedSections[index];

    if (section.id) {
      this.http.delete(`${this.apiUrl}/resources/sections/${section.id}`).subscribe({
        next: () => {
          this.addedSections.splice(index, 1);
        },
        error: (err) => {
          console.error('Failed to delete section:', err);
        }
      });
    } else {
      this.addedSections.splice(index, 1);
    }
  }

  private getRole(): 'admin' | 'user' {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return 'user';
    }

    try {
      const session = localStorage.getItem('lynxSession');
      if (!session) return 'user';
      const parsed = JSON.parse(session) as { role?: string };
      return parsed.role === 'admin' ? 'admin' : 'user';
    } catch {
      return 'user';
    }
  }

  private getEmail(): string {
    try {
      const session = localStorage.getItem('lynxSession');
      if (!session) return '';
      const parsed = JSON.parse(session) as { email?: string };
      return parsed.email || '';
    } catch {
      return '';
    }
  }
}

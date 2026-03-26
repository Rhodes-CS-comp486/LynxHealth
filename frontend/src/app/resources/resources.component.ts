import { CommonModule } from '@angular/common';
import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
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
  readonly role = this.getRole();
  readonly isAdmin = this.role === 'admin';
  readonly sessionEmail = this.getSessionEmail();

  isEditing = false;
  isSaving = false;

  sections: PageSection[] = [];
  addedSections: PageSection[] = [];
  sectionMap: { [key: string]: PageSection } = {};

  private readonly apiUrl = 'http://localhost:8000/pages';

  constructor(private readonly cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    this.loadSections();
  }

  private async loadSections(): Promise<void> {
    try {
      const response = await fetch(`${this.apiUrl}/resources/sections`, {
        cache: 'no-store'
      });

      if (!response.ok) {
        console.error('Failed to load sections:', response.status);
        return;
      }

      const sections = await response.json() as PageSection[];
      const defaultKeys = [
        'welcome', 'mission', 'visiting', 'services', 'cancellation_policy',
        'emergency_care', 'payment', 'self_care', 'allergy_shots', 'records',
        'opioid_policy', 'class_excuses'
      ];

      this.sections = [];
      this.addedSections = [];
      this.sectionMap = {};

      for (const s of sections) {
        if (defaultKeys.includes(s.section_key)) {
          this.sections.push(s);
          this.sectionMap[s.section_key] = s;
        } else {
          this.addedSections.push(s);
        }
      }

      this.refreshView();
    } catch (error) {
      console.error('Failed to load sections:', error);
    }
  }

  toggleEditMode(): void {
    if (this.isEditing) {
      this.saveAllSections();
    } else {
      this.isEditing = true;
      this.refreshView();

      // Populate rich editors with current content after DOM renders
      setTimeout(() => {
        const editors = document.querySelectorAll('.rich-editor');
        const allSections = [...this.sections, ...this.addedSections];
        editors.forEach((editor, index) => {
          if (allSections[index]) {
            editor.innerHTML = allSections[index].content;
          }
        });
      }, 50);
    }
  }

  async saveAllSections(): Promise<void> {
    const validAdded = this.addedSections.filter(
      s => s.header.trim() && s.content.trim()
    );

    const incomplete = this.addedSections.filter(
      s => (s.header.trim() && !s.content.trim()) || (!s.header.trim() && s.content.trim())
    );

    if (incomplete.length > 0) {
      alert('Please fill in both header and content for all new sections, or remove empty ones.');
      return;
    }

    this.isSaving = true;
    this.refreshView();

    const allSections = [...this.sections, ...validAdded];

    const payload = {
      admin_email: this.sessionEmail,
      sections: allSections.map((s, i) => ({
        section_key: s.section_key,
        header: s.header,
        content: s.content,
        display_order: i,
      }))
    };

    try {
      const response = await fetch(`${this.apiUrl}/resources/sections`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const error = await response.json();
        console.error('Failed to save sections:', error);
        alert('Failed to save. Check console for details.');
        this.isSaving = false;
        this.refreshView();
        return;
      }

      this.isEditing = false;
      this.isSaving = false;
      await this.loadSections();
    } catch (error) {
      console.error('Failed to save sections:', error);
      alert('Failed to save. Check console for details.');
      this.isSaving = false;
      this.refreshView();
    }
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
    this.refreshView();

    setTimeout(() => {
      const elements = document.querySelectorAll('.edit-controls');
      const last = elements[elements.length - 1];
      if (last) {
        last.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 100);
  }

  async removeSection(key: string): Promise<void> {
    const section = this.sectionMap[key];
    if (!section) return;

    if (!confirm(`Are you sure you want to delete the "${section.header}" section?`)) {
      return;
    }

    if (section.id) {
      try {
        const response = await fetch(`${this.apiUrl}/resources/sections/${section.id}`, {
          method: 'DELETE'
        });

        if (!response.ok) {
          console.error('Failed to delete section:', response.status);
          return;
        }
      } catch (error) {
        console.error('Failed to delete section:', error);
        return;
      }
    }

    this.sections = this.sections.filter(s => s.section_key !== key);
    delete this.sectionMap[key];
    this.refreshView();
  }

  async removeAddedSection(index: number): Promise<void> {
    const section = this.addedSections[index];
    const name = section.header || 'this section';

    if (!confirm(`Are you sure you want to delete "${name}"?`)) {
      return;
    }

    if (section.id) {
      try {
        const response = await fetch(`${this.apiUrl}/resources/sections/${section.id}`, {
          method: 'DELETE'
        });

        if (!response.ok) {
          console.error('Failed to delete section:', response.status);
          return;
        }

        this.addedSections.splice(index, 1);
        this.refreshView();
      } catch (error) {
        console.error('Failed to delete section:', error);
      }
    } else {
      this.addedSections.splice(index, 1);
    }
  }

  private refreshView(): void {
    this.cdr.detectChanges();
  }

  applyFormat(command: string): void {
    document.execCommand(command, false);
  }

  applyRed(): void {
    document.execCommand('foreColor', false, '#e2483b');
  }

  insertLink(): void {
    const url = prompt('Enter URL:');
    if (url) {
      document.execCommand('createLink', false, url);
    }
  }

  syncContent(sectionKey: string, field: 'header' | 'content', event: Event): void {
    const el = event.target as HTMLElement;
    const value = el.innerHTML;

    if (this.sectionMap[sectionKey]) {
      this.sectionMap[sectionKey][field] = value;
    }
  }

  syncAddedContent(index: number, field: 'header' | 'content', event: Event): void {
    const el = event.target as HTMLElement;
    this.addedSections[index][field] = el.innerHTML;
  }

  private getRole(): 'admin' | 'user' {
    const data = this.getSessionStorageItem();
    if (!data) return 'user';

    try {
      const parsed = JSON.parse(data) as { role?: string };
      return parsed.role === 'admin' ? 'admin' : 'user';
    } catch {
      return 'user';
    }
  }

  private getSessionEmail(): string {
    const data = this.getSessionStorageItem();
    const fallback = this.role === 'admin' ? 'admin@admin.edu' : 'user@lynxhealth.local';

    if (!data) return fallback;

    try {
      const parsed = JSON.parse(data) as { email?: string };
      return parsed.email?.trim().toLowerCase() || fallback;
    } catch {
      return fallback;
    }
  }

  private getSessionStorageItem(): string | null {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return null;
    }
    return localStorage.getItem('lynxSession');
  }
}

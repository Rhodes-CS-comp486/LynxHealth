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
        this.populateEditors();
      }, 50);
    }
  }

  private populateEditors(): void {
    const editors = document.querySelectorAll('.rich-editor');
    editors.forEach((editor) => {
      const el = editor as HTMLElement;
      const sectionKey = el.getAttribute('data-section-key');
      const addedIndex = el.getAttribute('data-added-index');

      if (sectionKey) {
        const section = this.sections.find(s => s.section_key === sectionKey);
        if (section) {
          el.innerHTML = section.content;
        }
      } else if (addedIndex !== null) {
        const idx = parseInt(addedIndex, 10);
        if (this.addedSections[idx]) {
          el.innerHTML = this.addedSections[idx].content;
        }
      }
    });
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

    // Ensure all links have target="_blank" before saving
    const processContent = (html: string): string => {
      const temp = document.createElement('div');
      temp.innerHTML = html;
      const links = temp.querySelectorAll('a');
      links.forEach(link => {
        link.setAttribute('target', '_blank');
        link.setAttribute('rel', 'noreferrer');
      });
      return temp.innerHTML;
    };

    const allSections = [...this.sections, ...validAdded];

    const payload = {
      admin_email: this.sessionEmail,
      sections: allSections.map((s, i) => ({
        section_key: s.section_key,
        header: s.header,
        content: processContent(s.content),
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

  insertLink(): void {
    // Check if the current selection is inside an existing link
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;

    let node: Node | null = selection.anchorNode;
    let existingLink: HTMLAnchorElement | null = null;

    while (node) {
      if (node.nodeType === Node.ELEMENT_NODE && (node as HTMLElement).tagName === 'A') {
        existingLink = node as HTMLAnchorElement;
        break;
      }
      node = node.parentNode;
    }

    if (existingLink) {
      // Editing existing link
      const action = prompt(
        `Current URL: ${existingLink.href}\n\nEnter new URL, or type "remove" to delete the link:`,
        existingLink.href
      );

      if (action === null) return;

      if (action.toLowerCase().trim() === 'remove') {
        // Unwrap the link, keep text
        const range = document.createRange();
        range.selectNodeContents(existingLink);
        selection.removeAllRanges();
        selection.addRange(range);
        document.execCommand('unlink', false);
      } else if (action.trim()) {
        existingLink.href = action.trim();
        existingLink.target = '_blank';
        existingLink.rel = 'noreferrer';
      }
    } else {
      // Creating new link
      if (selection.toString().trim() === '') {
        alert('Please select the text you want to turn into a link first.');
        return;
      }

      const url = prompt('Enter URL:');
      if (url) {
        document.execCommand('createLink', false, url);
        // Find the newly created link and add target="_blank"
        setTimeout(() => {
          const editors = document.querySelectorAll('.rich-editor');
          editors.forEach(editor => {
            const links = editor.querySelectorAll('a:not([target])');
            links.forEach(link => {
              (link as HTMLAnchorElement).target = '_blank';
              (link as HTMLAnchorElement).rel = 'noreferrer';
            });
          });
        }, 10);
      }
    }
  }

  moveSectionByIndex(index: number, direction: number): void {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= this.sections.length) return;

    // Sync any pending edits from the editors before swapping
    this.syncAllEditorsToModel();

    [this.sections[index], this.sections[newIndex]] = [this.sections[newIndex], this.sections[index]];
    this.refreshView();

    // Repopulate editors with new order
    setTimeout(() => this.populateEditors(), 50);
  }

  moveSectionUp(key: string): void {
    const index = this.sections.findIndex(s => s.section_key === key);
    this.moveSectionByIndex(index, -1);
  }

  moveSectionDown(key: string): void {
    const index = this.sections.findIndex(s => s.section_key === key);
    this.moveSectionByIndex(index, 1);
  }

  moveAddedSectionUp(index: number): void {
    if (index <= 0) return;
    this.syncAllEditorsToModel();
    [this.addedSections[index - 1], this.addedSections[index]] = [this.addedSections[index], this.addedSections[index - 1]];
    this.refreshView();
    setTimeout(() => this.populateEditors(), 50);
  }

  moveAddedSectionDown(index: number): void {
    if (index >= this.addedSections.length - 1) return;
    this.syncAllEditorsToModel();
    [this.addedSections[index], this.addedSections[index + 1]] = [this.addedSections[index + 1], this.addedSections[index]];
    this.refreshView();
    setTimeout(() => this.populateEditors(), 50);
  }

  private syncAllEditorsToModel(): void {
    const editors = document.querySelectorAll('.rich-editor');
    editors.forEach((editor) => {
      const el = editor as HTMLElement;
      const sectionKey = el.getAttribute('data-section-key');
      const addedIndex = el.getAttribute('data-added-index');

      if (sectionKey) {
        const section = this.sections.find(s => s.section_key === sectionKey);
        if (section) {
          section.content = el.innerHTML;
        }
      } else if (addedIndex !== null) {
        const idx = parseInt(addedIndex, 10);
        if (this.addedSections[idx]) {
          this.addedSections[idx].content = el.innerHTML;
        }
      }
    });
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

  trackBySectionKey(_index: number, section: PageSection): string {
    return section.section_key;
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

import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

interface ResourceSection {
  id: string;
  title: string;
  contentHtml: string;
}

@Component({
  selector: 'app-resources',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule],
  templateUrl: './resources.component.html',
  styleUrl: './resources.component.css'
})
export class ResourcesComponent {
  readonly role = this.getRole();
  readonly isAdmin = this.role === 'admin';

  sections: ResourceSection[] = this.getInitialSections();
  editingSectionId: string | null = null;
  draftTitle = '';
  draftContentHtml = '';

  constructor() {
    this.loadPersistedSections();
  }

  trackBySectionId(_: number, section: ResourceSection): string {
    return section.id;
  }

  startEditing(section: ResourceSection): void {
    this.editingSectionId = section.id;
    this.draftTitle = section.title;
    this.draftContentHtml = section.contentHtml;
  }

  cancelEditing(): void {
    this.editingSectionId = null;
    this.draftTitle = '';
    this.draftContentHtml = '';
  }

  saveSection(sectionId: string): void {
    const targetSection = this.sections.find((section) => section.id === sectionId);
    if (!targetSection) {
      return;
    }

    targetSection.title = this.draftTitle.trim() || targetSection.title;
    targetSection.contentHtml = this.draftContentHtml.trim();
    this.persistSections();
    this.cancelEditing();
  }

  deleteSection(sectionId: string): void {
    this.sections = this.sections.filter((section) => section.id !== sectionId);
    if (this.editingSectionId === sectionId) {
      this.cancelEditing();
    }
    this.persistSections();
  }

  addSection(): void {
    const newSection: ResourceSection = {
      id: `section-${Date.now()}`,
      title: 'New Section',
      contentHtml: '<p>Add content for this section.</p>'
    };

    this.sections = [...this.sections, newSection];
    this.persistSections();
    this.startEditing(newSection);
  }

  insertSubheader(): void {
    this.draftContentHtml += '\n<h3>New Subheader</h3>\n<p>Add supporting text here.</p>';
  }

  insertBulletList(): void {
    this.draftContentHtml += '\n<ul>\n  <li>First bullet</li>\n  <li>Second bullet</li>\n</ul>';
  }

  private persistSections(): void {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return;
    }

    localStorage.setItem('lynxResourcesSections', JSON.stringify(this.sections));
  }

  private loadPersistedSections(): void {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return;
    }

    const storedSections = localStorage.getItem('lynxResourcesSections');
    if (!storedSections) {
      return;
    }

    try {
      const parsed = JSON.parse(storedSections) as ResourceSection[];
      if (Array.isArray(parsed) && parsed.every((section) => section.id && section.title && typeof section.contentHtml === 'string')) {
        this.sections = parsed;
      }
    } catch {
      localStorage.removeItem('lynxResourcesSections');
    }
  }

  private getRole(): 'admin' | 'user' {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return 'user';
    }

    try {
      const session = localStorage.getItem('lynxSession');
      if (!session) {
        return 'user';
      }

      const parsed = JSON.parse(session) as { role?: string };
      return parsed.role === 'admin' ? 'admin' : 'user';
    } catch {
      return 'user';
    }
  }

  private getInitialSections(): ResourceSection[] {
    return [
      {
        id: 'mission',
        title: 'Mission',
        contentHtml:
          '<p>Our mission is to empower students to make informed health decisions, take responsibility for their well-being, and build habits that promote lifelong wellness. In every interaction, we foster an environment of kindness, respect, and cultural humility—reflecting Rhodes College\'s values of integrity, compassion, and community engagement.</p>'
      },
      {
        id: 'visiting',
        title: 'Visiting the Student Health Center',
        contentHtml:
          '<p>The Rhodes College Student Health Center is located in the <strong>Moore Moore Building</strong>, with the <strong>main entrance on the east side of the building</strong>, along Thomas Lane.</p><p>Handicap access is available on the south side of the Student Health Center, closest to the Refectory. For students requiring assistance at the handicap entrance to the Moore Moore Building, please call <strong>(901) 843-3895 for the Student Health Center</strong> or <strong>(901) 843-3128 for the Student Counseling Center</strong>.</p>'
      },
      {
        id: 'services',
        title: 'On-Site Services Provided in the Health Center',
        contentHtml:
          '<ul><li>Illness evaluations, diagnosis, and treatment</li><li>General physicals, not first-year\'s admission physicals</li><li>Gynecological exams</li><li>Wound care (minor)</li><li>Allergy shots, flu shots, and other vaccines</li><li>Health education information</li><li>Laboratory tests</li><li>Referrals to local healthcare specialists</li></ul><p>Patients with long-term or chronic illnesses will need to be seen by their primary care physician. The Student Health Center can assist with decisions regarding follow-up care with off-campus providers if necessary.</p><h3>Vaccines Offered</h3><ul><li>Tdap (Tetanus-Diphtheria-Pertussis) - $55</li><li>Tuberculosis Skin Test (PPD) - $25</li></ul>'
      },
      {
        id: 'emergency',
        title: 'Emergency Care',
        contentHtml:
          '<p><strong>Rhodes College Campus Safety — (901-843-3880 non-emergency) and (901-843-3333).</strong></p><p>In the event of an injury or emergency occurring in the classroom or on campus, please call Campus Safety. <strong>Be prepared to give your name, your exact location, and the nature of the injury or illness.</strong></p><h3>After-Hours Emergencies</h3><p>When the Student Health Center is closed, Campus Safety will coordinate emergency medical assistance at (901) 843-3333.</p><h3>After-Hours Health Care and Information</h3><p>When the Student Health Center is closed, local hospital emergency rooms and some walk-in centers are available. Here is a <a class="resource-link inline-link" href="https://sites.rhodes.edu/health/memphis-health-resources" target="_blank" rel="noreferrer">list of off-campus medical clinics</a>.</p>'
      },
      {
        id: 'official-links',
        title: 'Official Rhodes Health Links',
        contentHtml:
          '<div class="link-list"><a class="resource-link" href="https://sites.rhodes.edu/health" target="_blank" rel="noreferrer">More Information about the Health Center</a><a class="resource-link" href="https://sites.rhodes.edu/health/rhodes-policies" target="_blank" rel="noreferrer">Rhodes Policies</a><a class="resource-link" href="https://sites.rhodes.edu/health/emergency-care" target="_blank" rel="noreferrer">Emergency Care</a></div>'
      }
    ];
  }
}

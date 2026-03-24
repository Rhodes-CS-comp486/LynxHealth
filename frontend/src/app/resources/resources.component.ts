import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

type SessionRole = 'admin' | 'user';

interface ResourceBlock {
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
  readonly role: SessionRole = this.getRole();
  readonly isAdmin = this.role === 'admin';

  blocks: ResourceBlock[] = this.getInitialBlocks();
  editingBlockId: string | null = null;
  draftTitle = '';
  draftContentHtml = '';

  constructor() {
    this.loadPersistedBlocks();
  }

  trackByBlockId(_: number, block: ResourceBlock): string {
    return block.id;
  }

  startEditing(block: ResourceBlock): void {
    this.editingBlockId = block.id;
    this.draftTitle = block.title;
    this.draftContentHtml = block.contentHtml;
  }

  cancelEditing(): void {
    this.editingBlockId = null;
    this.draftTitle = '';
    this.draftContentHtml = '';
  }

  saveBlock(blockId: string): void {
    const targetBlock = this.blocks.find((block) => block.id === blockId);
    if (!targetBlock) {
      return;
    }

    targetBlock.title = this.draftTitle.trim() || targetBlock.title;
    targetBlock.contentHtml = this.draftContentHtml.trim();
    this.persistBlocks();
    this.cancelEditing();
  }

  deleteBlock(blockId: string): void {
    this.blocks = this.blocks.filter((block) => block.id !== blockId);
    if (this.editingBlockId === blockId) {
      this.cancelEditing();
    }
    this.persistBlocks();
  }

  addBlock(): void {
    const newBlock: ResourceBlock = {
      id: `block-${Date.now()}`,
      title: 'New Content Block',
      contentHtml: '<p>Add content for this block.</p>'
    };

    this.blocks = [...this.blocks, newBlock];
    this.persistBlocks();
    this.startEditing(newBlock);
  }

  insertSubheader(): void {
    this.draftContentHtml += '\n<h3>New Subheader</h3>\n<p>Add supporting text here.</p>';
  }

  insertBulletList(): void {
    this.draftContentHtml += '\n<ul>\n  <li>First bullet</li>\n  <li>Second bullet</li>\n</ul>';
  }

  private persistBlocks(): void {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return;
    }

    localStorage.setItem('lynxResourcesBlocks', JSON.stringify(this.blocks));
  }

  private loadPersistedBlocks(): void {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return;
    }

    const storedBlocks = localStorage.getItem('lynxResourcesBlocks');
    if (!storedBlocks) {
      return;
    }

    try {
      const parsed = JSON.parse(storedBlocks) as ResourceBlock[];
      if (Array.isArray(parsed) && parsed.every((block) => block.id && block.title && typeof block.contentHtml === 'string')) {
        this.blocks = parsed;
      }
    } catch {
      localStorage.removeItem('lynxResourcesBlocks');
    }
  }

  private getRole(): SessionRole {
    if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
      return 'user';
    }

    try {
      const session = localStorage.getItem('lynxSession');
      if (!session) {
        return 'user';
      }

      const parsed = JSON.parse(session) as { role?: string };
      const normalizedRole = parsed.role?.toLowerCase().trim();
      return normalizedRole === 'admin' ? 'admin' : 'user';
    } catch {
      return 'user';
    }
  }

  private getInitialBlocks(): ResourceBlock[] {
    return [
      {
        id: 'mission',
        title: 'Mission',
        contentHtml: `<p>Our mission is to empower students to make informed health decisions, take responsibility for their well-being, and build habits that promote lifelong wellness. In every interaction, we foster an environment of kindness, respect, and cultural humility—reflecting Rhodes College's values of integrity, compassion, and community engagement.</p>`
      },
      {
        id: 'visiting',
        title: 'Visiting the Student Health Center',
        contentHtml: `<p>The Rhodes College Student Health Center is located in the <strong>Moore Moore Building</strong>, with the <strong>main entrance on the east side of the building</strong>, along Thomas Lane.</p><p>Handicap access is available on the south side of the Student Health Center, closest to the Refectory. For students requiring assistance at the handicap entrance to the Moore Moore Building, please call <strong>(901) 843-3895 for the Student Health Center</strong> or <strong>(901) 843-3128 for the Student Counseling Center</strong>.</p>`
      },
      {
        id: 'services',
        title: 'On-Site Services Provided in the Health Center',
        contentHtml: `<ul><li>Illness evaluations, diagnosis, and treatment</li><li>General physicals, not first-year's admission physicals</li><li>Gynecological exams</li><li>Wound care (minor)</li><li>Allergy shots, flu shots, and other vaccines (please see list below)</li><li>Health education information</li><li>Laboratory tests</li><li>Referrals to local healthcare specialists</li></ul><p>Patients with long-term or chronic illnesses will need to be seen by their primary care physician. The Student Health Center can assist with decisions regarding follow-up care with off-campus providers if necessary.</p><h3>Vaccines Offered</h3><ul><li>Tdap (Tetanus-Diphtheria-Pertussis) - $55</li><li>Tuberculosis Skin Test (PPD) - $25</li></ul>`
      },
      {
        id: 'no-show',
        title: 'Appointments Cancellation/No Show Policy',
        contentHtml: `<p class="subheading"><strong>Effective October 13, 2025</strong></p><p>We value your time and strive to provide high-quality care to every student. To help us serve you and others efficiently, please review our updated policy.</p><h3>Cancelling or Rescheduling</h3><p>If you need to cancel or reschedule, contact the Student Health Center at least 2 hours prior to your appointment by phone or email. Early notice allows us to offer the slot to another student.</p><h3>No-Show &amp; Late Arrival</h3><p>You'll be charged a <strong>$25 fee</strong> (billed to your student account) if you:</p><ul><li>Miss your appointment without notifying the Student Health Center <strong>at least 2 hours</strong> before your appointment by phone <strong>(901-843-3895)</strong> or email <strong>health@rhodes.edu</strong></li><li>Arrive more than 15 minutes late without prior notification</li></ul><p>Late arrivals may wait to be seen at the provider's next available opening, but on-time patients will be prioritized.</p><h3>Emergency &amp; After-Hours</h3><p>We understand that emergencies happen. If you're unable to keep a scheduled appointment due to extenuating circumstances:</p><ul><li>Call or email us to explain.</li><li>If it is after hours or on a weekend, leave a message — messages received within the 2-hour window are acceptable.</li></ul>`
      },
      {
        id: 'emergency',
        title: 'Emergency Care',
        contentHtml: `<p><strong>Rhodes College Campus Safety — (901-843-3880 non-emergency) and (901-843-3333).</strong></p><p>In the event of an injury or emergency occurring in the classroom or on campus, please call Campus Safety. <strong>Be prepared to give your name, your exact location, and the nature of the injury or illness.</strong> Campus Safety will respond to the scene and evaluate whether the patient needs to be transported by ambulance to an emergency facility.</p><h3>After-Hours Emergencies</h3><p>When the Student Health Center is closed, Campus Safety will coordinate emergency medical assistance at (901) 843-3333. The patient may be transferred to a local medical facility if the conditions warrant it. The patient will be responsible for the cost of transfer and care at that facility.</p><h3>After-Hours Health Care and Information</h3><p>When the Student Health Center is closed, local hospital emergency rooms and some walk-in centers are available. Here is a <a class="resource-link inline-link" href="https://sites.rhodes.edu/health/memphis-health-resources" target="_blank" rel="noreferrer">list of off-campus medical clinics</a>.</p>`
      },
      {
        id: 'payment',
        title: 'Payment',
        contentHtml: `<p>There is <strong>NO</strong> charge for clinical office visits and in-house screening and testing such as Strep, COVID, Influenza, Mono, urinalysis, or pregnancy tests.</p><p>However, a fee for vaccines/immunizations offered at the Student Health Center will be charged to the Student's Rhodes College account.</p><p>Any services requiring an outside entity, such as blood work, X-rays, ultrasounds, etc., are billed to the student's health insurance. You and/or your parents are responsible for charges not covered by your insurance for off-campus medical services.</p><h3>UnitedHealthcare Student Resources</h3><p>The 2025-2026 rates and website for <a class="resource-link inline-link" href="https://studentcenter.uhcsr.com/rhodes" target="_blank" rel="noreferrer">UnitedHealthcare Student Resources</a> are available.</p>`
      },
      {
        id: 'self-care',
        title: 'Self-Care Counter',
        contentHtml: `<p>During regular clinic hours, students can visit the Student Health Center's Self-Care Counter for medications and supplies for minor symptoms at no charge. Please speak to the front desk nurse for any questions and concerns.</p>`
      },
      {
        id: 'allergy',
        title: 'Allergy Shots',
        contentHtml: `<p><strong>Requirements:</strong> Your allergy provider will need to send your allergy serums, administration orders, injection protocol, and last provider visit to the Student Health Center. Once all items have been received and verified by the Nurse Practitioner, you may begin scheduling your appointments to receive your injections.</p><p>The Student Health Center does not accept deliveries of serums and does not initiate treatment therapy; only maintenance therapy is provided.</p><p><strong>*Please note that there will be a 30-minute wait time in the office after receiving injections to ensure there are no adverse reactions.</strong></p>`
      },
      {
        id: 'records',
        title: 'Questions and Medical Records',
        contentHtml: `<p>For administrative questions, vaccination information, or medical records, please email <a class="resource-link inline-link" href="mailto:health@rhodes.edu">health@rhodes.edu</a>.</p><p>Steps to <a class="resource-link inline-link" href="https://sites.rhodes.edu/health/request-immunization-record" target="_blank" rel="noreferrer">request an immunization record</a></p>`
      },
      {
        id: 'policy',
        title: 'Opioid Analgesics and Mental Health Medication Policy',
        contentHtml: `<p>The Student Health Center does not prescribe opioid analgesics for the treatment of chronic pain. Patients requiring chronic pain or acute pain management, including the use of opioid analgesics, will be referred to an appropriate off-site resource for ongoing care and management of their chronic or acute pain.</p><p>For initiation or refills of mental health medications, please contact the <strong>Rhodes College Student Counseling Center at (901) 843-3128.</strong></p>`
      },
      {
        id: 'excuses',
        title: 'Class and Work Excuses',
        contentHtml: `<p>The Rhodes College Student Health Center (SHC) encourages the development of responsible healthcare habits. Medical excuses will not routinely be issued for missed classes or examinations. SHC cannot provide medical documentation of illnesses or excuses for class/work.</p><p>Please review the Rhodes College Student Handbook on <a class="resource-link inline-link" href="https://catalog.rhodes.edu/content.php?catoid=31&navoid=1118" target="_blank" rel="noreferrer">Class Attendance Policy</a>.</p>`
      },
      {
        id: 'links',
        title: 'Official Rhodes Health Links',
        contentHtml: `<div class="link-list"><a class="resource-link" href="https://sites.rhodes.edu/health" target="_blank" rel="noreferrer">More Information about the Health Center</a><a class="resource-link" href="https://sites.rhodes.edu/health/rhodes-policies" target="_blank" rel="noreferrer">Rhodes Policies</a><a class="resource-link" href="https://sites.rhodes.edu/health/emergency-care" target="_blank" rel="noreferrer">Emergency Care</a></div>`
      }
    ];
  }
}

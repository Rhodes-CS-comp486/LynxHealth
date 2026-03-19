import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

interface ResourceSection {
  id: string;
  label: string;
  title: string;
  description: string;
  sourceUrl: string;
  highlights: string[];
  quickLinks: Array<{ label: string; url: string }>;
}

@Component({
  selector: 'app-resources',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './resources.component.html',
  styleUrl: './resources.component.css'
})
export class ResourcesComponent {
  readonly role = this.getRole();
  readonly sections: ResourceSection[] = [
    {
      id: 'health-awareness',
      label: 'Health Awareness',
      title: 'Stay informed with everyday health and wellness guidance',
      description:
        'This page brings together prevention tips, wellness education, and updates that help students make informed decisions before, during, and after a visit to the health center.',
      sourceUrl: 'https://sites.rhodes.edu/health/health-awareness-resources',
      highlights: [
        'Review health awareness topics and wellness information gathered by the Rhodes Health Center.',
        'Use the official Rhodes site for updates that may change over time, including seasonal guidance and student support resources.',
        'Find a central starting point for broader health education before exploring campus or community services.'
      ],
      quickLinks: [
        { label: 'Open Health Awareness Resources', url: 'https://sites.rhodes.edu/health/health-awareness-resources' },
        { label: 'Visit Health Center Home', url: 'https://sites.rhodes.edu/health' }
      ]
    },
    {
      id: 'policies',
      label: 'Policies & Insurance',
      title: 'Know the policies, insurance expectations, and medical record steps',
      description:
        'Rhodes shares key details about insurance requirements, waiver and opt-in information, medical records, immunization records, and academic excuse expectations.',
      sourceUrl: 'https://sites.rhodes.edu/health/rhodes-policies',
      highlights: [
        'Students are expected to maintain health insurance coverage while enrolled, and the Rhodes site outlines plan and waiver details.',
        'Medical records are kept confidential, and the site explains how to request immunization records before graduation or when needed.',
        'The health center does not issue academic excuses, but the official page explains how treatment verification and Student Life support work.'
      ],
      quickLinks: [
        { label: 'Open Rhodes Policies', url: 'https://sites.rhodes.edu/health/rhodes-policies' },
        { label: 'Student Insurance Portal', url: 'https://studentcenter.uhcsr.com/rhodes' }
      ]
    },
    {
      id: 'emergency-care',
      label: 'Emergency Care',
      title: 'Be ready when urgent or after-hours care is needed',
      description:
        'Emergency care information helps students quickly identify where to go when the campus health center is closed or when immediate treatment is needed.',
      sourceUrl: 'https://sites.rhodes.edu/health/emergency-care',
      highlights: [
        'Use this section to jump directly to emergency and urgent-care guidance from Rhodes.',
        'Keep this page handy for situations when students need fast direction beyond regular appointment scheduling.',
        'Pair emergency guidance with the hours section so users can tell when to use on-campus services versus off-campus care.'
      ],
      quickLinks: [
        { label: 'Open Emergency Care', url: 'https://sites.rhodes.edu/health/emergency-care' },
        { label: 'Open Campus COVID FAQ', url: 'https://sites.rhodes.edu/health/campus-covid-faq' }
      ]
    },
    {
      id: 'off-campus',
      label: 'Off-Campus Support',
      title: 'Explore community providers, referrals, and nearby health support',
      description:
        'Rhodes also publishes pages for Memphis health resources, referrals, and tips for using off-campus clinics so students can continue care when they need specialized services.',
      sourceUrl: 'https://sites.rhodes.edu/health/memphis-health-resources',
      highlights: [
        'Find pathways to Memphis-area health resources and referrals when the Student Health Center sends students elsewhere.',
        'Review guidance for visiting off-campus health clinics so students know what to expect before an appointment.',
        'Use the official Rhodes pages to compare care options and stay connected to health center recommendations.'
      ],
      quickLinks: [
        { label: 'Open Memphis Health Resources', url: 'https://sites.rhodes.edu/health/memphis-health-resources' },
        { label: 'Tips for Off-Campus Clinics', url: 'https://sites.rhodes.edu/health/tips-visiting-campus-health-clinics' }
      ]
    }
  ];

  selectedSectionId = this.sections[0].id;

  constructor(private readonly route: ActivatedRoute) {
    const sectionId = this.route.snapshot.fragment;
    if (sectionId && this.sections.some((section) => section.id === sectionId)) {
      this.selectedSectionId = sectionId;
    }
  }

  get selectedSection(): ResourceSection {
    return this.sections.find((section) => section.id === this.selectedSectionId) ?? this.sections[0];
  }

  selectSection(sectionId: string): void {
    this.selectedSectionId = sectionId;
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
}

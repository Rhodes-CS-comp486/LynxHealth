"""
Page-content endpoints for admin-editable CMS sections.

Each page (e.g. ``resources``) owns an ordered list of ``PageSection`` rows
that the frontend renders as headers + body copy. Admins can create, reorder,
and delete sections; when a page has no sections yet, a hard-coded default
set is seeded so first-time visitors see meaningful content.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.models.page_section import PageSection

router = APIRouter(tags=['pages'])

MAX_HEADER_LENGTH = 200
MAX_CONTENT_LENGTH = 5000
MAX_SECTION_KEY_LENGTH = 100


class PageSectionRequest(BaseModel):
    section_key: str
    header: str
    content: str
    display_order: int = 0

    @field_validator('header')
    @classmethod
    def validate_header(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('Section header is required.')
        if len(normalized) > MAX_HEADER_LENGTH:
            raise ValueError(f'Header must be {MAX_HEADER_LENGTH} characters or fewer.')
        return normalized

    @field_validator('content')
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('Section content is required.')
        if len(normalized) > MAX_CONTENT_LENGTH:
            raise ValueError(f'Content must be {MAX_CONTENT_LENGTH} characters or fewer.')
        return normalized

    @field_validator('section_key')
    @classmethod
    def validate_section_key(cls, value: str) -> str:
        normalized = value.strip().lower().replace(' ', '_')
        if not normalized:
            raise ValueError('Section key is required.')
        if len(normalized) > MAX_SECTION_KEY_LENGTH:
            raise ValueError(f'Section key must be {MAX_SECTION_KEY_LENGTH} characters or fewer.')
        return normalized


class BulkUpdateRequest(BaseModel):
    admin_email: str
    sections: list[PageSectionRequest]

    @field_validator('admin_email')
    @classmethod
    def validate_admin_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.endswith('@admin.edu'):
            raise ValueError('Only admins can update page content.')
        return normalized


class AddSectionRequest(BaseModel):
    admin_email: str
    section_key: str
    header: str
    content: str
    display_order: int = 0

    @field_validator('admin_email')
    @classmethod
    def validate_admin_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.endswith('@admin.edu'):
            raise ValueError('Only admins can add page sections.')
        return normalized

    @field_validator('header')
    @classmethod
    def validate_header(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('Section header is required.')
        if len(normalized) > MAX_HEADER_LENGTH:
            raise ValueError(f'Header must be {MAX_HEADER_LENGTH} characters or fewer.')
        return normalized

    @field_validator('content')
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('Section content is required.')
        if len(normalized) > MAX_CONTENT_LENGTH:
            raise ValueError(f'Content must be {MAX_CONTENT_LENGTH} characters or fewer.')
        return normalized

    @field_validator('section_key')
    @classmethod
    def validate_section_key(cls, value: str) -> str:
        normalized = value.strip().lower().replace(' ', '_')
        if not normalized:
            raise ValueError('Section key is required.')
        if len(normalized) > MAX_SECTION_KEY_LENGTH:
            raise ValueError(f'Section key must be {MAX_SECTION_KEY_LENGTH} characters or fewer.')
        return normalized


class PageSectionResponse(BaseModel):
    id: int
    page: str
    section_key: str
    header: str
    content: str
    display_order: int

    model_config = ConfigDict(from_attributes=True)


RESOURCES_DEFAULT_SECTIONS: list[dict] = [
    {
        'section_key': 'welcome',
        'header': 'Welcome to the Student Health Center!',
        'content': (
            'The Rhodes College Student Health Center is committed to being an accessible and inclusive '
            'healthcare resource for our diverse student body. We offer personalized medical services, '
            'preventive care, and health education that support academic success and personal growth.'
        ),
        'display_order': 0,
    },
    {
        'section_key': 'mission',
        'header': 'Mission',
        'content': (
            'Our mission is to empower students to make informed health decisions, take responsibility '
            'for their well-being, and build habits that promote lifelong wellness. In every interaction, '
            'we foster an environment of kindness, respect, and cultural humility\u2014reflecting Rhodes '
            "College\u2019s values of integrity, compassion, and community engagement."
        ),
        'display_order': 1,
    },
    {
        'section_key': 'visiting',
        'header': 'Visiting the Student Health Center',
        'content': (
            'The Rhodes College Student Health Center is located in the Moore Moore Building, with the '
            'main entrance on the east side of the building, along Thomas Lane.\n\n'
            'Handicap access is available on the south side of the Student Health Center, closest to the '
            'Refectory. For students requiring assistance at the handicap entrance to the Moore Moore '
            'Building, please call (901) 843-3895 for the Student Health Center or (901) 843-3128 for '
            'the Student Counseling Center.'
        ),
        'display_order': 2,
    },
    {
        'section_key': 'services',
        'header': 'On-Site Services Provided in the Health Center',
        'content': (
            '\u2022 Illness evaluations, diagnosis, and treatment\n'
            '\u2022 General physicals, not first-year\'s admission physicals\n'
            '\u2022 Gynecological exams\n'
            '\u2022 Wound care (minor)\n'
            '\u2022 Allergy shots, flu shots, and other vaccines\n'
            '\u2022 Health education information\n'
            '\u2022 Laboratory tests\n'
            '\u2022 Referrals to local healthcare specialists\n\n'
            'Patients with long-term or chronic illnesses will need to be seen by their primary care '
            'physician. The Student Health Center can assist with decisions regarding follow-up care '
            'with off-campus providers if necessary.\n\n'
            'Vaccines Offered:\n'
            '\u2022 Tdap (Tetanus-Diphtheria-Pertussis) - $55\n'
            '\u2022 Tuberculosis Skin Test (PPD) - $25'
        ),
        'display_order': 3,
    },
    {
        'section_key': 'cancellation_policy',
        'header': 'Appointments Cancellation/No Show Policy',
        'content': (
            'Effective October 13, 2025\n\n'
            'We value your time and strive to provide high-quality care to every student. To help us '
            'serve you and others efficiently, please review our updated policy.\n\n'
            'Cancelling or Rescheduling: If you need to cancel or reschedule, contact the Student '
            'Health Center at least 2 hours prior to your appointment by phone or email. Early notice '
            'allows us to offer the slot to another student.\n\n'
            'No-Show & Late Arrival: You\'ll be charged a $25 fee (billed to your student account) if '
            'you miss your appointment without notifying the Student Health Center at least 2 hours '
            'before your appointment by phone (901-843-3895) or email health@rhodes.edu, or arrive '
            'more than 15 minutes late without prior notification.\n\n'
            'Late arrivals may wait to be seen at the provider\'s next available opening, but on-time '
            'patients will be prioritized.\n\n'
            'Emergency & After-Hours: We understand that emergencies happen. If you\'re unable to keep '
            'a scheduled appointment due to extenuating circumstances, call or email us to explain. '
            'If it is after hours or on a weekend, leave a message \u2014 messages received within the '
            '2-hour window are acceptable.'
        ),
        'display_order': 4,
    },
    {
        'section_key': 'emergency_care',
        'header': 'Emergency Care',
        'content': (
            'Rhodes College Campus Safety \u2014 (901-843-3880 non-emergency) and (901-843-3333).\n\n'
            'In the event of an injury or emergency occurring in the classroom or on campus, please call '
            'Campus Safety. Be prepared to give your name, your exact location, and the nature of the '
            'injury or illness. Campus Safety will respond to the scene and evaluate whether the patient '
            'needs to be transported by ambulance to an emergency facility.\n\n'
            'After-Hours Emergencies: When the Student Health Center is closed, Campus Safety will '
            'coordinate emergency medical assistance at (901) 843-3333. The patient may be transferred '
            'to a local medical facility if the conditions warrant it. The patient will be responsible '
            'for the cost of transfer and care at that facility.\n\n'
            'After-Hours Health Care and Information: When the Student Health Center is closed, local '
            'hospital emergency rooms and some walk-in centers are available. Here is a '
            '<a href="https://sites.rhodes.edu/health/memphis-health-resources" target="_blank" rel="noreferrer">list of off-campus medical clinics</a>.'
        ),
        'display_order': 5,
    },
    {
        'section_key': 'payment',
        'header': 'Payment',
        'content': (
            'There is NO charge for clinical office visits and in-house screening and testing such as '
            'Strep, COVID, Influenza, Mono, urinalysis, or pregnancy tests.\n\n'
            'However, a fee for vaccines/immunizations offered at the Student Health Center will be '
            'charged to the Student\'s Rhodes College account.\n\n'
            'Any services requiring an outside entity, such as blood work, X-rays, ultrasounds, etc., '
            'are billed to the student\'s health insurance. You and/or your parents are responsible for '
            'charges not covered by your insurance for off-campus medical services.\n\n'
            'The 2025-2026 rates and website for '
            '<a href="https://studentcenter.uhcsr.com/school-page" target="_blank" rel="noreferrer">UnitedHealthcare Student Resources</a> are available.'
        ),
        'display_order': 6,
    },
    {
        'section_key': 'self_care',
        'header': 'Self-Care Counter',
        'content': (
            'During regular clinic hours, students can visit the Student Health Center\'s Self-Care '
            'Counter for medications and supplies for minor symptoms at no charge. Please speak to the '
            'front desk nurse for any questions and concerns.'
        ),
        'display_order': 7,
    },
    {
        'section_key': 'allergy_shots',
        'header': 'Allergy Shots',
        'content': (
            'Requirements: Your allergy provider will need to send your allergy serums, administration '
            'orders, injection protocol, and last provider visit to the Student Health Center. Once all '
            'items have been received and verified by the Nurse Practitioner, you may begin scheduling '
            'your appointments to receive your injections.\n\n'
            'The Student Health Center does not accept deliveries of serums and does not initiate '
            'treatment therapy; only maintenance therapy is provided.\n\n'
            '*Please note that there will be a 30-minute wait time in the office after receiving '
            'injections to ensure there are no adverse reactions.'
        ),
        'display_order': 8,
    },
    {
        'section_key': 'records',
        'header': 'Questions and Medical Records',
        'content': (
            'For administrative questions, vaccination information, or medical records, please email '
            'health@rhodes.edu. Steps to '
            '<a href="https://sites.rhodes.edu/health/health-awareness-resources/request-immunization-record" target="_blank" rel="noreferrer">request an immunization record</a>.'
        ),
        'display_order': 9,
    },
    {
        'section_key': 'opioid_policy',
        'header': 'Opioid Analgesics and Mental Health Medication Policy',
        'content': (
            'The Student Health Center does not prescribe opioid analgesics for the treatment of '
            'chronic pain. Patients requiring chronic pain or acute pain management, including the use '
            'of opioid analgesics, will be referred to an appropriate off-site resource for ongoing '
            'care and management of their chronic or acute pain.\n\n'
            'For initiation or refills of mental health medications, please contact the Rhodes College '
            'Student Counseling Center at (901) 843-3128.'
        ),
        'display_order': 10,
    },
    {
        'section_key': 'class_excuses',
        'header': 'Class and Work Excuses',
        'content': (
            'The Rhodes College Student Health Center (SHC) encourages the development of responsible '
            'healthcare habits. Medical excuses will not routinely be issued for missed classes or '
            'examinations. SHC cannot provide medical documentation of illnesses or excuses for '
            'class/work.\n\n'
            'Please review the Rhodes College Student Handbook on '
            '<a href="https://handbook.rhodes.edu/student-handbook/academics-rhodes/class-attendance-policy" target="_blank" rel="noreferrer">Class Attendance Policy</a>.'
        ),
        'display_order': 11,
    },
]


def seed_default_sections(page: str, db: Session) -> list[PageSection]:
    """Populate a brand-new ``resources`` page with the hardcoded defaults.

    Called lazily by ``get_page_sections`` when a page is queried but has no
    rows in the database yet. Returns ``[]`` for any page other than
    ``'resources'`` so other pages simply stay empty until an admin adds
    their first section.
    """
    if page != 'resources':
        return []

    rows: list[PageSection] = []
    for section_data in RESOURCES_DEFAULT_SECTIONS:
        row = PageSection(
            page=page,
            section_key=section_data['section_key'],
            header=section_data['header'],
            content=section_data['content'],
            display_order=section_data['display_order'],
        )
        db.add(row)
        rows.append(row)

    db.commit()
    for row in rows:
        db.refresh(row)

    return rows


@router.get('/{page}/sections', response_model=list[PageSectionResponse])
def get_page_sections(page: str, db: Session = Depends(get_db)):
    """Return all sections for ``page`` in display order, seeding defaults if empty."""
    try:
        sections = db.query(PageSection).filter(
            PageSection.page == page,
        ).order_by(PageSection.display_order.asc()).all()

        if not sections:
            sections = seed_default_sections(page, db)

        return sections
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable.',
        ) from exc


@router.put('/{page}/sections', response_model=list[PageSectionResponse])
def update_page_sections(page: str, data: BulkUpdateRequest, db: Session = Depends(get_db)):
    """Replace every section on ``page`` with the provided list (admin only)."""
    try:
        db.query(PageSection).filter(PageSection.page == page).delete()

        rows: list[PageSection] = []
        for section in data.sections:
            row = PageSection(
                page=page,
                section_key=section.section_key,
                header=section.header,
                content=section.content,
                display_order=section.display_order,
            )
            db.add(row)
            rows.append(row)

        db.commit()
        for row in rows:
            db.refresh(row)

        return sorted(rows, key=lambda r: r.display_order)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable.',
        ) from exc


@router.post('/{page}/sections', response_model=PageSectionResponse, status_code=status.HTTP_201_CREATED)
def add_page_section(page: str, data: AddSectionRequest, db: Session = Depends(get_db)):
    """Append a new section to ``page`` (admin only); auto-increments display order."""
    try:
        max_order = db.query(PageSection.display_order).filter(
            PageSection.page == page,
        ).order_by(PageSection.display_order.desc()).first()

        next_order = (max_order[0] + 1) if max_order else 0

        row = PageSection(
            page=page,
            section_key=data.section_key,
            header=data.header,
            content=data.content,
            display_order=data.display_order if data.display_order else next_order,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        return row
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable.',
        ) from exc


@router.delete('/{page}/sections/{section_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_page_section(
    page: str,
    section_id: int,
    db: Session = Depends(get_db),
):
    """Delete a single section. Returns 404 if the id does not belong to ``page``."""
    try:
        section = db.query(PageSection).filter(
            PageSection.id == section_id,
            PageSection.page == page,
        ).first()

        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Section not found.',
            )

        db.delete(section)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable.',
        ) from exc
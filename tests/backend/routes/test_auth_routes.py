from backend.routes.auth_routes import get_user_role_from_email


def test_login_returns_admin_role_for_admin_domain() -> None:
    role = get_user_role_from_email('Nurse@admin.edu')

    assert role == 'admin'


def test_login_returns_user_role_for_non_admin_domain() -> None:
    role = get_user_role_from_email('student@example.edu')

    assert role == 'user'

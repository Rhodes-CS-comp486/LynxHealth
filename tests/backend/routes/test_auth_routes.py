from backend.routes.auth_routes import LoginRequest, login


def test_login_returns_admin_role_for_admin_domain() -> None:
    response = login(LoginRequest(email='Nurse@admin.edu'))

    assert response['user']['role'] == 'admin'


def test_login_returns_user_role_for_non_admin_domain() -> None:
    response = login(LoginRequest(email='student@example.edu'))

    assert response['user']['role'] == 'user'

from app.models import User, EmailVerificationToken


def register(client, email="alice@example.com", password="Password123", name="Alice"):
    return client.post(
        "/auth/register",
        data={
            "name": name,
            "email": email,
            "password": password,
            "confirm_password": password,
        },
        follow_redirects=True,
    )


def login(client, email="alice@example.com", password="Password123"):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def verify_user(app, client, email="alice@example.com"):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        token = EmailVerificationToken.query.filter_by(user_id=user.id).first()
        token_value = token.token
    client.get(f"/auth/verify-email/{token_value}")


def register_and_login(app, client, email="alice@example.com", password="Password123", name="Alice"):
    register(client, email=email, password=password, name=name)
    verify_user(app, client, email=email)
    login(client, email=email, password=password)

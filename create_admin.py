"""
Script para crear usuarios de prueba en la base de datos.
Ejecutar después de aplicar las migraciones:

    python create_admin.py
"""
import os
import sys
import django
from decouple import config

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.users.models import User, StudentProfile, TeacherProfile


def create_user(email, username, first_name, last_name, role, password,
                is_staff=False, is_superuser=False):
    """
    Creates or updates a User and sets the password using Django's native hasher.
    Returns (user, created).
    """
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'role': role,
            'is_active': True,
            'is_staff': is_staff,
            'is_superuser': is_superuser,
        }
    )
    # Always apply password so re-runs keep credentials in sync.
    user.set_password(password)
    user.save()
    return user, created


def print_user(user, password, created):
    action = "creado" if created else "contraseña actualizada"
    print(f"  {'✅' if created else 'ℹ️ '} [{action}] {user.email}  |  role={user.role}")
    print(f"     username: {user.username}  |  password: {password}")


print("=" * 60)
print("👥 SEED DE USUARIOS")
print("=" * 60)

# ------------------------------------------------------------------
# Admin
# ------------------------------------------------------------------
admin_user, admin_created = create_user(
    email='admin@legacydevs.com',
    username='admin',
    first_name='Admin',
    last_name='LegacyDevs',
    role='admin',
    password=config('USERS_PASSWORD', default='1234'),
    is_staff=True,
    is_superuser=True,
)
print_user(admin_user, config('USERS_PASSWORD'), admin_created)

print("\n" + "=" * 60)
print("✅ SEED COMPLETADO")
print("=" * 60)
print("Endpoint de login: POST http://127.0.0.1:8000/api/auth/login/")
print("=" * 60)

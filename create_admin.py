"""
Script para crear usuario administrador en la base de datos
Ejecutar después de aplicar las migraciones
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.hashers import make_password
from apps.users.models import Person, UserAccount

print("="*60)
print("👤 CREANDO USUARIO ADMINISTRADOR")
print("="*60)

# Crear o actualizar persona
person, person_created = Person.objects.get_or_create(
    email='admin@legacydevs.com',
    defaults={
        'first_name': 'Admin',
        'last_name': 'LegacyDevs',
        'status': True
    }
)

if person_created:
    print(f"✅ Persona creada: {person.email}")
else:
    print(f"ℹ️  Persona ya existe: {person.email}")

# Crear o actualizar cuenta de usuario
hashed_password = make_password('1234')
user_account, account_created = UserAccount.objects.get_or_create(
    id_person=person,
    defaults={
        'username': 'admin',
        'password_hash': hashed_password,
        'role': 'admin',
        'status': True
    }
)

if account_created:
    print(f"✅ Cuenta de usuario creada: {user_account.username}")
else:
    # Actualizar contraseña si ya existe
    user_account.password_hash = hashed_password
    user_account.save()
    print(f"✅ Contraseña actualizada para: {user_account.username}")

print("\n" + "="*60)
print("✅ USUARIO ADMINISTRADOR LISTO")
print("="*60)
print(f"Email: {person.email}")
print(f"Username: {user_account.username}")
print(f"Password: 1234")
print(f"Role: {user_account.role}")
print("="*60)
print("\nPuedes iniciar sesión con estas credenciales en:")
print("POST http://127.0.0.1:8000/api/auth/login/")
print("="*60)

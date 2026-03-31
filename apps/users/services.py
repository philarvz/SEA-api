import secrets
import string

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from loguru import logger

from apps.users.models import StudentProfile, TeacherProfile
from apps.academic.models import Group, Subject

User = get_user_model()


class UserRegistrationService:
    """Stateless service that centralises all user registration logic."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def register_user(data: dict) -> tuple:
        """
        Create a User and its role-specific profile inside a single DB
        transaction, then fire the welcome e-mail (outside the transaction
        boundary so an e-mail failure does not roll back the user).

        Args:
            data: Validated data from RegisterUserSerializer.

        Returns:
            Tuple[User, str]: The created User instance and the plain-text
                              password (for audit logging only; never
                              exposed to the client).
        """
        plain_password = UserRegistrationService._generate_password(
            data['matricula'], data['role']
        )

        # ----------------------------------------------------------
        # 1. Create the core user account
        # ----------------------------------------------------------
        user = User.objects.create_user(
            username=data['matricula'],          # matricula doubles as username
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            matricula=data['matricula'],
            role=data['role'],
            is_active=data.get('status', True),
            password=plain_password,             # create_user hashes this
        )

        # ----------------------------------------------------------
        # 2. Create the role-specific profile
        # ----------------------------------------------------------
        role = user.role

        if role == 'student':
            group = None
            if data.get('id_group'):
                group = Group.objects.get(pk=data['id_group'])
            StudentProfile.objects.create(user=user, group=group)

        elif role == 'teacher':
            profile = TeacherProfile.objects.create(user=user)
            if data.get('subject_ids'):
                subjects = Subject.objects.filter(pk__in=data['subject_ids'])
                profile.subjects.set(subjects)

        # Admin users do not need a dedicated profile.

        logger.info(
            'User registered | id={} email={} role={} matricula={}',
            user.pk, user.email, user.role, user.matricula,
        )

        # ----------------------------------------------------------
        # 3. Send welcome e-mail (non-blocking; failure only logged)
        # ----------------------------------------------------------
        try:
            UserRegistrationService._send_welcome_email(user, plain_password)
        except Exception as exc:
            logger.error(
                'Welcome e-mail NOT sent to {} | error={}',
                user.email, exc,
            )

        return user, plain_password

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_password(matricula: str, role: str) -> str:
        """
        Build the initial password following the institutional convention:
            <PREFIX> + last_3_chars(matricula) + 3_random_alphanumeric

        Prefix by role:
            student → ALU
            teacher → PRO
            admin   → ADM

        No spaces or dashes are included.
        """
        prefix_map = {
            'student': 'ALU',
            'teacher': 'PRO',
            'admin':   'ADM',
        }
        prefix = prefix_map.get(role, 'USR')
        last3 = matricula[-3:]
        rand3 = ''.join(
        secrets.choice(string.ascii_letters + string.digits)
        for _ in range(3))
        return f"{prefix}{last3}{rand3}"

    @staticmethod
    def _send_welcome_email(user: User, plain_password: str) -> None:
        """
        Render the welcome_account.vm template and send it as an HTML
        e-mail with a plain-text fallback.
        """
        role_labels = {
            'student': 'Alumno',
            'teacher': 'Docente',
            'admin': 'Administrador',
        }

        context = {
            'full_name': user.full_name,
            'email': user.email,
            'username': user.username,
            'password': plain_password,
            'role': role_labels.get(user.role, user.role),
            'matricula': user.matricula,
        }

        subject = 'Bienvenido(a) al Sistema de Evaluación Académica (SEA)'
        html_body = render_to_string('email/welcome_account.vm', context)
        text_body = (
            f"Hola {user.full_name},\n\n"
            f"Tu cuenta en SEA ha sido creada exitosamente.\n\n"
            f"Usuario (matrícula): {user.username}\n"
            f"Correo: {user.email}\n"
            f"Clave temporal: {plain_password}\n\n"
            f"Por seguridad te recomendamos cambiar tu clave en tu perfil.\n\n"
            f"— Equipo SEA"
        )

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)

        logger.info('Welcome e-mail sent | to={}', user.email)


class UserUpdateService:
    """Service for updating existing users and their role-specific profiles."""

    @staticmethod
    @transaction.atomic
    def update_user(user: User, data: dict) -> User:
        # ----------------------------------------------------------
        # 1. Update core user fields
        # ----------------------------------------------------------
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data:
            user.email = data['email']
        if 'matricula' in data:
            # Si se actualiza la matrícula, también actualizamos el username
            user.matricula = data['matricula']
            user.username = data['matricula']
        if 'status' in data:
            user.status = data['status']
            user.is_active = data['status']

        user.save()

        # ----------------------------------------------------------
        # 2. Update role-specific profile (role cannot change)
        # ----------------------------------------------------------
        if user.role == 'student':
            UserUpdateService._update_student_profile(user, data)
        elif user.role == 'teacher':
            UserUpdateService._update_teacher_profile(user, data)
        # Admin no necesita perfil específico

        logger.info(
            'User updated | id={} email={} role={} matricula={}',
            user.pk, user.email, user.role, user.matricula,
        )

        return user

    @staticmethod
    def _update_student_profile(user: User, data: dict) -> None:
        """Update or create StudentProfile."""
        profile, created = StudentProfile.objects.get_or_create(user=user)
        
        if 'id_group' in data:
            if data['id_group'] is None:
                profile.group = None
            else:
                profile.group = Group.objects.get(pk=data['id_group'])
        
        profile.save()
        logger.info('Student profile {} | user_id={}', 'created' if created else 'updated', user.pk)

    @staticmethod
    def _update_teacher_profile(user: User, data: dict) -> None:
        """Update or create TeacherProfile."""
        profile, created = TeacherProfile.objects.get_or_create(user=user)
        
        if 'subject_ids' in data:
            if data['subject_ids'] is None or len(data['subject_ids']) == 0:
                profile.subjects.clear()
            else:
                subjects = Subject.objects.filter(pk__in=data['subject_ids'])
                profile.subjects.set(subjects)
        
        profile.save()
        logger.info('Teacher profile {} | user_id={}', 'created' if created else 'updated', user.pk)

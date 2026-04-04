import secrets
import string

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
from loguru import logger

from apps.users.models import StudentProfile, TeacherProfile, PasswordResetCode
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
        # Para administradores, generar username único basado en email
        if data['role'] == 'admin':
            username = data['email'].split('@')[0]
            # Asegurar que el username sea único
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            matricula = None
        else:
            username = data['matricula']
            matricula = data['matricula']
        
        plain_password = UserRegistrationService._generate_password(
            matricula or username, data['role']
        )

        # ----------------------------------------------------------
        # 1. Create the core user account
        # ----------------------------------------------------------
        user = User.objects.create_user(
            username=username,
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            matricula=matricula,
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
            user.pk, user.email, user.role, user.matricula or 'N/A',
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
    def _generate_password(identifier: str, role: str) -> str:
        """
        Build the initial password following the institutional convention:
            <PREFIX> + last_3_chars(identifier) + 3_random_alphanumeric

        Prefix by role:
            student → ALU
            teacher → PRO
            admin   → ADM

        For admins without matricula, identifier is the username.
        No spaces or dashes are included.
        """
        prefix_map = {
            'student': 'ALU',
            'teacher': 'PRO',
            'admin':   'ADM',
        }
        prefix = prefix_map.get(role, 'USR')
        last3 = identifier[-3:] if len(identifier) >= 3 else identifier
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
            'matricula': user.matricula or 'N/A',
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
            # Solo si no es un administrador o si tiene matrícula
            if data['matricula']:
                user.matricula = data['matricula']
                if user.role != 'admin':
                    user.username = data['matricula']
            else:
                user.matricula = None
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
            user.pk, user.email, user.role, user.matricula or 'N/A',
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


class PasswordRecoveryService:
    """Servicio para gestionar la recuperación de contraseña"""

    @staticmethod
    @transaction.atomic
    def request_password_reset(email: str) -> dict:
        """
        Genera un código de 6 dígitos y lo envía por correo electrónico
        
        Args:
            email: Correo electrónico del usuario
            
        Returns:
            dict con información del proceso
        """
        try:
            user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            # Por seguridad, no revelar si el email existe o no
            logger.warning(f'Password reset requested for non-existent email: {email}')
            return {'message': 'Si el correo existe, recibirás un código de verificación.'}

        # Invalidar códigos anteriores no usados para este usuario
        PasswordResetCode.objects.filter(
            user=user, 
            is_used=False
        ).update(is_used=True)

        # Generar código de 6 dígitos
        code = ''.join(secrets.choice(string.digits) for _ in range(6))
        
        # Calcular tiempo de expiración (15 minutos)
        expires_at = timezone.now() + timedelta(minutes=15)
        
        # Crear registro del código
        PasswordResetCode.objects.create(
            user=user,
            code=code,
            expires_at=expires_at
        )

        # Enviar email con el código
        try:
            PasswordRecoveryService._send_reset_code_email(user, code)
            logger.info(f'Password reset code sent to {email}')
        except Exception as e:
            logger.error(f'Failed to send reset code email to {email}: {e}')
            raise RuntimeError('Error al enviar el correo electrónico. Inténtalo de nuevo.')

        return {
            'message': 'Código de verificación enviado a tu correo electrónico.',
            'expires_in_minutes': 15
        }

    @staticmethod
    def verify_reset_code(email: str, code: str) -> dict:
        """
        Verifica si el código es válido para el email proporcionado
        
        Args:
            email: Correo electrónico del usuario
            code: Código de 6 dígitos
            
        Returns:
            dict con el resultado de la verificación
        """
        try:
            user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            raise ValueError('Correo electrónico no encontrado.')

        try:
            reset_code = PasswordResetCode.objects.filter(
                user=user,
                code=code.upper(),
                is_used=False
            ).latest('created_at')
        except PasswordResetCode.DoesNotExist:
            raise ValueError('Código de verificación inválido.')

        if not reset_code.is_valid():
            raise ValueError('El código ha expirado. Solicita uno nuevo.')

        logger.info(f'Reset code verified for {email}')
        
        return {
            'valid': True,
            'message': 'Código verificado correctamente.'
        }

    @staticmethod
    @transaction.atomic
    def reset_password(email: str, code: str, new_password: str) -> dict:
        """
        Restablece la contraseña del usuario después de verificar el código
        
        Args:
            email: Correo electrónico del usuario
            code: Código de 6 dígitos
            new_password: Nueva contraseña
            
        Returns:
            dict con el resultado del restablecimiento
        """
        try:
            user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            raise ValueError('Correo electrónico no encontrado.')

        try:
            reset_code = PasswordResetCode.objects.filter(
                user=user,
                code=code.upper(),
                is_used=False
            ).latest('created_at')
        except PasswordResetCode.DoesNotExist:
            raise ValueError('Código de verificación inválido.')

        if not reset_code.is_valid():
            raise ValueError('El código ha expirado. Solicita uno nuevo.')

        # Cambiar la contraseña
        user.set_password(new_password)
        user.save()

        # Marcar el código como usado
        reset_code.is_used = True
        reset_code.save()

        logger.info(f'Password reset successfully for {email}')

        return {
            'message': 'Contraseña restablecida exitosamente.'
        }

    @staticmethod
    def _send_reset_code_email(user: User, code: str) -> None:
        """
        Envía el correo electrónico con el código de verificación
        
        Args:
            user: Usuario al que se le enviará el código
            code: Código de 6 dígitos
        """
        context = {
            'full_name': user.full_name,
            'email': user.email,
            'code': code,
        }

        subject = 'Recuperación de Contraseña - SEA'
        html_body = render_to_string('email/password_reset.vm', context)
        text_body = (
            f"Hola {user.full_name},\n\n"
            f"Tu código de verificación para restablecer tu contraseña es: {code}\n\n"
            f"Este código expirará en 15 minutos.\n\n"
            f"Si no solicitaste este cambio, ignora este correo.\n\n"
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

        logger.info(f'Password reset email sent to {user.email}')

"""
Users module models
Includes: User (AbstractUser), StudentProfile, TeacherProfile
"""

from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Custom User model extending AbstractUser.
    Centraliza autenticación e identidad básica.
    AbstractUser ya provee: username, first_name, last_name,
    email, password, is_active, date_joined, etc.
    """

    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Administrator'),
    ]

    id_user = models.AutoField(primary_key=True)
    # Sobreescribimos email para hacerlo único
    email = models.EmailField(max_length=150, unique=True)
    # Matrícula institucional única por usuario (ej. 20233tn070)
    matricula = models.CharField(
        max_length=20,
        unique=True,
        db_column='matricula',
        help_text='Matrícula institucional única del usuario.',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def full_name(self):
        """Retorna el nombre completo del usuario"""
        return f"{self.first_name} {self.last_name}"


class StudentProfile(models.Model):
    """
    Perfil específico para estudiantes.
    Almacena datos propios del rol: grupo académico.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='student_profile'
    )
    group = models.ForeignKey(
        'academic.Group',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students'
    )

    class Meta:
        db_table = 'student_profile'
        verbose_name = 'Student Profile'
        verbose_name_plural = 'Student Profiles'

    def __str__(self):
        return f"Student: {self.user.username}"


class TeacherProfile(models.Model):
    """
    Perfil específico para docentes.
    Almacena datos propios del rol: departamento y materias asignadas.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_profile'
    )
    department = models.CharField(max_length=150, blank=True)
    # Materias asignadas al docente (M2M)
    subjects = models.ManyToManyField(
        'academic.Subject',
        blank=True,
        related_name='teachers',
        db_table='teacher_subject',
    )

    class Meta:
        db_table = 'teacher_profile'
        verbose_name = 'Teacher Profile'
        verbose_name_plural = 'Teacher Profiles'

    def __str__(self):
        return f"Teacher: {self.user.username}"

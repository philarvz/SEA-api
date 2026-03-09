"""
Users module models
Includes: Person, UserAccount
"""

from django.db import models


class Person(models.Model):
    """
    Model representing a person in the system (student, admin or teacher)
    """
    id_person = models.AutoField(primary_key=True, db_column='id_person')
    first_name = models.CharField(max_length=100, db_column='first_name')
    last_name = models.CharField(max_length=150, db_column='last_name')
    email = models.EmailField(max_length=150, unique=True)
    id_group = models.ForeignKey(
        'academic.Group',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_group',
        related_name='persons'
    )
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'person'
        verbose_name = 'Person'
        verbose_name_plural = 'Persons'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        """Returns the person's full name"""
        return f"{self.first_name} {self.last_name}"


class UserAccount(models.Model):
    """
    Model representing a user account (1:1 with Person)
    Handles authentication and role management
    """
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Administrator'),
    ]

    id_user = models.AutoField(primary_key=True, db_column='id_user')
    id_person = models.OneToOneField(
        Person,
        on_delete=models.CASCADE,
        db_column='id_person',
        related_name='user_account'
    )
    username = models.CharField(max_length=100, unique=True)
    password_hash = models.CharField(max_length=255, db_column='password_hash')
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    status = models.BooleanField(default=True)

    class Meta:
        db_table = 'user_account'
        verbose_name = 'User Account'
        verbose_name_plural = 'User Accounts'
        ordering = ['username']

    def __str__(self):
        return f"{self.username} ({self.role})"

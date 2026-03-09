from django.db import models

# Note: This app now uses Person + UserAccount models from apps.users
# The custom User model below is kept for reference but not actively used

# Uncomment if you want to use Django's AbstractUser in the future
# from django.contrib.auth.models import AbstractUser
# 
# class User(AbstractUser):
#     """
#     Custom User model for future extensibility
#     Currently DISABLED - using Person + UserAccount instead
#     """
#     email = models.EmailField(unique=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     
#     class Meta:
#         db_table = 'auth_user'
#         verbose_name = 'User'
#         verbose_name_plural = 'Users'
#         ordering = ['-created_at']
#     
#     def __str__(self):
#         return self.email

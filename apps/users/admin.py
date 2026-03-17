from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, StudentProfile, TeacherProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'status', 'is_active']
    list_filter = ['role', 'status', 'is_active']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['last_name', 'first_name']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('SEA Fields', {'fields': ('role', 'status')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('SEA Fields', {'fields': ('email', 'first_name', 'last_name', 'role', 'status')}),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'group']
    search_fields = ['user__username', 'user__email']
    autocomplete_fields = ['user']


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'department']
    search_fields = ['user__username', 'user__email']
    autocomplete_fields = ['user']

from django.contrib import admin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):

    list_display = (
        "correo",
        "nombre",
        "apellido",
        "rol",
        "jornada",
        "centro_formacion",
        "is_active",
    )

    list_filter = (
        "rol",
        "jornada",
        "centro_formacion",
        "is_active",
    )

    search_fields = (
        "correo",
        "nombre",
        "apellido",
        "ficha",
    )

    ordering = ("correo",)

    fieldsets = (
        ("Información de acceso", {
            "fields": (
                "correo",
                "password",
            )
        }),

        ("Información personal", {
            "fields": (
                "nombre",
                "apellido",
                "celular",
                "centro_formacion",
                "jornada",
                "ficha",
            )
        }),

        ("Permisos y rol", {
            "fields": (
                "rol",
                "is_active",
                "is_staff",
                "is_superuser",
            )
        }),
    )
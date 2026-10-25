from django.core.management.base import BaseCommand

from usuarios.models import Usuario


class Command(BaseCommand):

    help = "Crea o actualiza los tres administradores fijos de ViveSport"

    def handle(self, *args, **options):

        administradores = [
            {
                "nombre": "Paola",
                "apellido": "Alvarez",
                "correo": "paalvarez@sena.edu.co",
                "password": "Adminpaolabienestar",
                "celular": "3147741641",
                "centro_formacion": "Diseño, Confección y Moda",
            },
            {
                "nombre": "Walter",
                "apellido": "Giraldo",
                "correo": "wgiraldom@sena.edu.co",
                "password": "Adminwalterbienestar",
                "celular": "3013604877",
                "centro_formacion": "Manufactura de Cuero",
            },
            {
                "nombre": "Santiago",
                "apellido": "Viveros",
                "correo": "contactanos.vivesport@gmail.com",
                "password": "Adminsantiagovivesport",
                "celular": "3216413786",
                "centro_formacion": "Diseño, Confección y Moda",
            },
        ]

        for datos in administradores:

            usuario, creado = Usuario.objects.get_or_create(
                correo=datos["correo"],
                defaults={
                    "nombre": datos["nombre"],
                    "apellido": datos["apellido"],
                    "celular": datos["celular"],
                    "centro_formacion": datos["centro_formacion"],
                    "jornada": "Mañana",
                    "ficha": "000000",
                    "rol": "admin",
                    "is_active": True,
                    "is_staff": True,
                    "is_superuser": True,
                }
            )

            if creado:

                usuario.set_password(
                    datos["password"]
                )

                usuario.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Administrador creado: {datos['correo']}"
                    )
                )

            else:

                usuario.nombre = datos["nombre"]
                usuario.apellido = datos["apellido"]
                usuario.celular = datos["celular"]
                usuario.centro_formacion = datos["centro_formacion"]
                usuario.rol = "admin"
                usuario.is_active = True
                usuario.is_staff = True
                usuario.is_superuser = True

                usuario.save()

                self.stdout.write(
                    self.style.WARNING(
                        f"Administrador actualizado: {datos['correo']}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Administradores de ViveSport configurados correctamente."
            )
        )
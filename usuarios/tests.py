from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from usuarios.models import (
    Torneo,
    Equipo,
    IntegranteEquipo,
    FaseTorneo,
    Partido,
    ResultadoPartido,
    Gol,
)


Usuario = get_user_model()


class FinalizacionTorneoTests(TestCase):
    """
    Pruebas automatizadas para verificar que el registro
    del resultado de una final permita finalizar el torneo
    y notificar a los responsables de los equipos.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user(
            correo="admin_pruebas@vivesport.test",
            password="PruebasSeguras123!",
            nombre="Administrador",
            apellido="Pruebas",
            celular="3000000001",
            centro_formacion="Diseño, Confección y Moda",
            jornada="Mañana",
            ficha="1234567",
            rol="admin",
            is_staff=True,
        )

        cls.responsable_local = Usuario.objects.create_user(
            correo="local_pruebas@vivesport.test",
            password="PruebasSeguras123!",
            nombre="Responsable",
            apellido="Local",
            celular="3000000002",
            centro_formacion="Diseño, Confección y Moda",
            jornada="Mañana",
            ficha="1234567",
            rol="usuario",
        )

        cls.responsable_visitante = Usuario.objects.create_user(
            correo="visitante_pruebas@vivesport.test",
            password="PruebasSeguras123!",
            nombre="Responsable",
            apellido="Visitante",
            celular="3000000003",
            centro_formacion="Manufactura de Cuero",
            jornada="Tarde",
            ficha="7654321",
            rol="usuario",
        )

        cls.torneo = Torneo.objects.create(
            nombre="Torneo de pruebas automatizadas",
            deporte="futbol",
            duracion_partido=60,
            descripcion="Torneo creado exclusivamente para pruebas.",
            fecha_inicio=timezone.localdate(),
            estado="en_curso",
        )

        cls.equipo_local = Equipo.objects.create(
            nombre="Equipo Local de Pruebas",
            responsable=cls.responsable_local,
        )

        cls.equipo_visitante = Equipo.objects.create(
            nombre="Equipo Visitante de Pruebas",
            responsable=cls.responsable_visitante,
        )

        cls.jugador_local = IntegranteEquipo.objects.create(
            equipo=cls.equipo_local,
            nombre="Jugador",
            apellido="Local",
            celular="3000000011",
            centro_formacion="Diseño, Confección y Moda",
            jornada="Mañana",
            ficha="1234567",
        )

        cls.jugador_visitante = IntegranteEquipo.objects.create(
            equipo=cls.equipo_visitante,
            nombre="Jugador",
            apellido="Visitante",
            celular="3000000012",
            centro_formacion="Manufactura de Cuero",
            jornada="Tarde",
            ficha="7654321",
        )

        cls.fase_final = FaseTorneo.objects.create(
            torneo=cls.torneo,
            nombre="Final",
            tipo="final",
            orden=1,
            activa=True,
        )

        cls.partido_final = Partido.objects.create(
            torneo=cls.torneo,
            fase=cls.fase_final,
            equipo_local=cls.equipo_local,
            equipo_visitante=cls.equipo_visitante,
            numero=1,
            estado="programado",
        )

    def iniciar_sesion_admin(self):
        """
        Autentica al administrador de pruebas.
        """
        self.client.force_login(self.admin)

    def datos_resultado_final(self):
        """
        Construye un POST con un gol del equipo local.
        """
        return {
            "marcador_local": "1",
            "marcador_visitante": "0",
            "jugadores_local": [str(self.jugador_local.pk)],
            "jugadores_visitante": [str(self.jugador_visitante.pk)],
            "goles_local": [str(self.jugador_local.pk)],
            "goles_visitante": [],
        }

    @patch("usuarios.views.enviar_correo_vivesport")
    def test_finalizar_torneo_y_notificar_campeon(
        self,
        mock_enviar_correo,
    ):
        """
        Una final jugada con ganador debe finalizar el torneo
        y preparar la notificación a ambos responsables.
        """
        self.iniciar_sesion_admin()

        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(
                reverse(
                    "registrar_resultado",
                    args=[self.partido_final.pk],
            ),
            data=self.datos_resultado_final(),
            )

        self.assertEqual(respuesta.status_code, 302)

        self.torneo.refresh_from_db()
        self.partido_final.refresh_from_db()

        self.assertEqual(self.partido_final.estado, "jugado")
        self.assertEqual(self.torneo.estado, "finalizado")

        resultado = ResultadoPartido.objects.get(
            partido=self.partido_final,
        )

        self.assertEqual(resultado.marcador_local, 1)
        self.assertEqual(resultado.marcador_visitante, 0)

        self.assertEqual(
            Gol.objects.filter(
                partido=self.partido_final,
                equipo=self.equipo_local,
                jugador=self.jugador_local,
            ).count(),
            1,
        )

        mock_enviar_correo.assert_called()

        llamadas = mock_enviar_correo.call_args_list

        correo_campeon = next(
            (
                llamada
                for llamada in llamadas
                if "torneo finalizado" in llamada.kwargs.get(
                    "asunto",
                    "",
                ).lower()
            ),
            None,
        )

        self.assertIsNotNone(
            correo_campeon,
            "No se preparó el correo de finalización del torneo.",
        )

        destinatarios = correo_campeon.kwargs["destinatarios"]

        self.assertCountEqual(
            destinatarios,
            [
                self.responsable_local.correo,
                self.responsable_visitante.correo,
            ],
        )

        self.assertIn(
            self.equipo_local.nombre,
            correo_campeon.kwargs["mensaje"],
        )

        self.assertIn(
            self.equipo_visitante.nombre,
            correo_campeon.kwargs["mensaje"],
        )

    @patch("usuarios.views.enviar_correo_vivesport")
    def test_usuario_no_administrador_no_registra_resultado(
        self,
        mock_enviar_correo,
    ):
        """
        Un usuario normal no debe poder registrar resultados.
        """
        self.client.force_login(self.responsable_local)

        respuesta = self.client.post(
            reverse(
                "registrar_resultado",
                args=[self.partido_final.pk],
            ),
            data=self.datos_resultado_final(),
        )

        self.assertEqual(respuesta.status_code, 302)

        self.partido_final.refresh_from_db()
        self.torneo.refresh_from_db()

        self.assertEqual(self.partido_final.estado, "programado")
        self.assertEqual(self.torneo.estado, "en_curso")

        self.assertFalse(
            ResultadoPartido.objects.filter(
                partido=self.partido_final,
            ).exists()
        )

        mock_enviar_correo.assert_not_called()

    @patch("usuarios.views.enviar_correo_vivesport")
    def test_final_empatada_no_finaliza_torneo(
        self,
        mock_enviar_correo,
    ):
        """
        Un empate en la final no debe declarar campeón
        ni finalizar el torneo.
        """
        self.iniciar_sesion_admin()

        datos = self.datos_resultado_final()
        datos["goles_local"] = [str(self.jugador_local.pk)]
        datos["goles_visitante"] = [str(self.jugador_visitante.pk)]

        respuesta = self.client.post(
            reverse(
                "registrar_resultado",
                args=[self.partido_final.pk],
            ),
            data=datos,
        )

        self.assertEqual(respuesta.status_code, 302)

        self.torneo.refresh_from_db()
        self.partido_final.refresh_from_db()

        self.assertEqual(self.partido_final.estado, "jugado")
        self.assertEqual(self.torneo.estado, "en_curso")

        resultado = ResultadoPartido.objects.get(
            partido=self.partido_final,
        )

        self.assertEqual(resultado.marcador_local, 1)
        self.assertEqual(resultado.marcador_visitante, 1)

        asuntos = [
            llamada.kwargs.get("asunto", "").lower()
            for llamada in mock_enviar_correo.call_args_list
        ]

        self.assertFalse(
            any("torneo finalizado" in asunto for asunto in asuntos)
        )

    @patch("usuarios.views.enviar_correo_vivesport")
    def test_partido_ya_jugado_no_admite_otro_resultado(
        self,
        mock_enviar_correo,
    ):
        """
        Un partido que ya está jugado no debe aceptar
        un nuevo registro de resultado.
        """
        self.iniciar_sesion_admin()

        ResultadoPartido.objects.create(
            partido=self.partido_final,
            marcador_local=1,
            marcador_visitante=0,
        )

        self.partido_final.estado = "jugado"
        self.partido_final.save(update_fields=["estado"])

        respuesta = self.client.post(
            reverse(
                "registrar_resultado",
                args=[self.partido_final.pk],
            ),
            data=self.datos_resultado_final(),
        )

        self.assertEqual(respuesta.status_code, 302)

        self.torneo.refresh_from_db()

        self.assertEqual(self.torneo.estado, "en_curso")

        self.assertEqual(
            ResultadoPartido.objects.filter(
                partido=self.partido_final,
            ).count(),
            1,
        )

        mock_enviar_correo.assert_not_called()

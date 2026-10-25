from datetime import timedelta

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


# =========================================================
# MANAGER DE USUARIO
# =========================================================

class UsuarioManager(BaseUserManager):

    def create_user(
        self,
        correo,
        password=None,
        **extra_fields
    ):

        if not correo:
            raise ValueError(
                "El usuario debe tener un correo"
            )

        correo = self.normalize_email(correo)

        usuario = self.model(
            correo=correo,
            **extra_fields
        )

        usuario.set_password(password)

        usuario.save(
            using=self._db
        )

        return usuario

    def create_superuser(
        self,
        correo,
        password=None,
        **extra_fields
    ):

        extra_fields.setdefault(
            "is_staff",
            True
        )

        extra_fields.setdefault(
            "is_superuser",
            True
        )

        return self.create_user(
            correo,
            password,
            **extra_fields
        )


# =========================================================
# USUARIO
# =========================================================

class Usuario(
    AbstractBaseUser,
    PermissionsMixin
):

    JORNADA_CHOICES = [
        ("Mañana", "Mañana"),
        ("Tarde", "Tarde"),
        ("Noche", "Noche"),
    ]

    CENTRO_CHOICES = [
        (
            "Diseño, Confección y Moda",
            "Diseño, Confección y Moda"
        ),
        (
            "Manufactura de Cuero",
            "Manufactura de Cuero"
        ),
    ]

    ROL_CHOICES = [
        ("usuario", "Usuario"),
        ("admin", "Administrador"),
    ]

    nombre = models.CharField(
        max_length=50
    )

    apellido = models.CharField(
        max_length=50
    )

    correo = models.EmailField(
        unique=True
    )

    celular = models.CharField(
        max_length=10
    )

    centro_formacion = models.CharField(
        max_length=100,
        choices=CENTRO_CHOICES
    )

    jornada = models.CharField(
        max_length=20,
        choices=JORNADA_CHOICES
    )

    ficha = models.CharField(
        max_length=7,
        verbose_name="Numero de ficha"
    )

    rol = models.CharField(
        max_length=10,
        choices=ROL_CHOICES,
        default="usuario"
    )

    is_active = models.BooleanField(
        default=True
    )

    is_staff = models.BooleanField(
        default=False
    )

    is_superuser = models.BooleanField(
        default=False
    )

    objects = UsuarioManager()

    USERNAME_FIELD = "correo"

    REQUIRED_FIELDS = []

    def __str__(self):

        return (
            f"{self.nombre} "
            f"{self.apellido}"
        )


# =========================================================
# TORNEO
# =========================================================

class Torneo(models.Model):

    DEPORTE_CHOICES = [
        ("futbol", "Fútbol"),
        ("voleibol", "Voleibol"),
        ("tenis_mesa", "Tenis de Mesa"),
    ]

    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        (
            "inscripciones_abiertas",
            "Inscripciones abiertas"
        ),
        (
            "inscripciones_cerradas",
            "Inscripciones cerradas"
        ),
        ("en_curso", "En curso"),
        ("finalizado", "Finalizado"),
    ]

    nombre = models.CharField(
        max_length=150
    )

    deporte = models.CharField(
        max_length=20,
        choices=DEPORTE_CHOICES
    )

    duracion_partido = models.PositiveIntegerField(
        default=60,
        verbose_name="Duración del partido (minutos)"
    )

    descripcion = models.TextField(
        blank=True
    )

    fecha_inicio = models.DateField()

    estado = models.CharField(
        max_length=30,
        choices=ESTADO_CHOICES,
        default="pendiente"
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    actualizado_en = models.DateTimeField(
        auto_now=True
    )

    def clean(self):

        super().clean()

        if self.fecha_inicio:

            fecha_actual = timezone.localdate()

            if self.fecha_inicio < fecha_actual:

                raise ValidationError({
                    "fecha_inicio": (
                        "La fecha de inicio no puede "
                        "ser anterior al día de hoy."
                    )
                })

    def __str__(self):

        return self.nombre


# =========================================================
# EQUIPO
# =========================================================

class Equipo(models.Model):

    nombre = models.CharField(
        max_length=100
    )

    responsable = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="equipos_responsable"
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    actualizado_en = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):

        return self.nombre


# =========================================================
# INTEGRANTE DEL EQUIPO
# =========================================================

class IntegranteEquipo(models.Model):

    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name="integrantes"
    )

    nombre = models.CharField(
        max_length=50
    )

    apellido = models.CharField(
        max_length=50
    )

    celular = models.CharField(
        max_length=10
    )

    centro_formacion = models.CharField(
        max_length=100,
        choices=Usuario.CENTRO_CHOICES
    )

    jornada = models.CharField(
        max_length=20,
        choices=Usuario.JORNADA_CHOICES
    )

    ficha = models.CharField(
        max_length=8
    )

    def __str__(self):

        return (
            f"{self.nombre} "
            f"{self.apellido}"
        )


# =========================================================
# CONFIGURACIÓN DE INSCRIPCIONES
# =========================================================

class ConfiguracionInscripcion(models.Model):

    torneo = models.OneToOneField(
        Torneo,
        on_delete=models.CASCADE,
        related_name="configuracion_inscripcion"
    )

    minimo_integrantes = models.PositiveIntegerField()

    maximo_integrantes = models.PositiveIntegerField()

    inscripciones_abiertas = models.BooleanField(
        default=False
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    actualizado_en = models.DateTimeField(
        auto_now=True
    )

    def clean(self):

        super().clean()

        if self.minimo_integrantes < 1:

            raise ValidationError({
                "minimo_integrantes": (
                    "El mínimo de integrantes debe "
                    "ser mayor o igual a 1."
                )
            })

        if self.maximo_integrantes < 1:

            raise ValidationError({
                "maximo_integrantes": (
                    "El máximo de integrantes debe "
                    "ser mayor o igual a 1."
                )
            })

        if (
            self.minimo_integrantes
            > self.maximo_integrantes
        ):

            raise ValidationError({
                "minimo_integrantes": (
                    "El mínimo de integrantes no puede "
                    "ser mayor que el máximo."
                ),
                "maximo_integrantes": (
                    "El máximo de integrantes no puede "
                    "ser menor que el mínimo."
                ),
            })

    def __str__(self):

        return (
            f"Configuración - "
            f"{self.torneo.nombre}"
        )


# =========================================================
# CONTROL DE ELIMINACIONES
# =========================================================

class ControlInscripcion(models.Model):

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="controles_inscripcion"
    )

    torneo = models.ForeignKey(
        Torneo,
        on_delete=models.CASCADE,
        related_name="controles_inscripcion"
    )

    eliminaciones_realizadas = (
        models.PositiveSmallIntegerField(
            default=0
        )
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "usuario",
                    "torneo"
                ],
                name="control_unico_usuario_torneo"
            )
        ]

    def puede_eliminar(self):

        return (
            self.eliminaciones_realizadas < 2
        )

    def registrar_eliminacion(self):

        if not self.puede_eliminar():

            return False

        self.eliminaciones_realizadas += 1

        self.save(
            update_fields=[
                "eliminaciones_realizadas"
            ]
        )

        return True

    def __str__(self):

        return (
            f"{self.usuario} - "
            f"{self.torneo} - "
            f"Eliminaciones: "
            f"{self.eliminaciones_realizadas}/2"
        )


# =========================================================
# INSCRIPCIÓN
# =========================================================

class Inscripcion(models.Model):

    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("aceptada", "Aceptada"),
        ("rechazada", "Rechazada"),
    ]

    torneo = models.ForeignKey(
        Torneo,
        on_delete=models.CASCADE,
        related_name="inscripciones"
    )

    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name="inscripciones"
    )

    responsable = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="inscripciones_realizadas"
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default="pendiente"
    )

    ediciones_realizadas = (
        models.PositiveSmallIntegerField(
            default=0
        )
    )

    edicion_bloqueada = models.BooleanField(
        default=False
    )

    fecha_inscripcion = models.DateTimeField(
        auto_now_add=True
    )

    actualizado_en = models.DateTimeField(
        auto_now=True
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "torneo",
                    "equipo"
                ],
                name="inscripcion_unica_torneo_equipo"
            )
        ]

    def actualizar_bloqueo_automatico(self):

        if self.estado != "pendiente" or self.edicion_bloqueada:

            return False

        fecha_bloqueo = (
            self.torneo.fecha_inicio
            - timedelta(days=3)
        )

        if timezone.localdate() >= fecha_bloqueo:

            self.edicion_bloqueada = True

            self.save(
                update_fields=[
                    "edicion_bloqueada",
                    "actualizado_en",
                ]
            )

            return True

        return False


    def esta_definida(self):

        if self.estado != "pendiente":

            return True

        self.actualizar_bloqueo_automatico()

        return self.edicion_bloqueada


    def puede_editar(self):

        self.actualizar_bloqueo_automatico()

        return (
            self.estado == "pendiente"
            and self.ediciones_realizadas < 3
            and not self.edicion_bloqueada
        )


    def registrar_edicion(self):

        if not self.puede_editar():

            return False

        self.ediciones_realizadas += 1

        if self.ediciones_realizadas >= 3:

            self.edicion_bloqueada = True

        self.save(
            update_fields=[
                "ediciones_realizadas",
                "edicion_bloqueada",
                "actualizado_en",
            ]
        )

        return True


    def __str__(self):

        return (
            f"{self.equipo.nombre} - "
            f"{self.torneo.nombre} - "
            f"{self.get_estado_display()}"
        )


# =========================================================
# CONFIGURACIÓN DE COMPETICIÓN
# =========================================================

class ConfiguracionCompeticion(models.Model):

    torneo = models.OneToOneField(
        Torneo,
        on_delete=models.CASCADE,
        related_name="configuracion_competicion"
    )

    cantidad_grupos = models.PositiveIntegerField()

    equipos_clasifican = models.PositiveIntegerField()

    sorteo_realizado = models.BooleanField(
        default=False
    )

    competicion_generada = models.BooleanField(
        default=False
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    actualizado_en = models.DateTimeField(
        auto_now=True
    )

    def clean(self):

        super().clean()

        if self.cantidad_grupos < 1:

            raise ValidationError({
                "cantidad_grupos": (
                    "La cantidad de grupos debe "
                    "ser mayor o igual a 1."
                )
            })

        if self.equipos_clasifican < 2:

            raise ValidationError({
                "equipos_clasifican": (
                    "Deben clasificar al menos "
                    "2 equipos."
                )
            })

        if self.equipos_clasifican > 8:

            raise ValidationError({
                "equipos_clasifican": (
                    "Un máximo de 8 equipos pueden "
                    "clasificar a las fases eliminatorias."
                )
            })

        if self.equipos_clasifican & (
            self.equipos_clasifican - 1
        ):

            raise ValidationError({
                "equipos_clasifican": (
                    "La cantidad de equipos que "
                    "clasifican debe ser 2, 4, 8, "
                    "16, 32, etc."
                )
            })

        if (
            self.equipos_clasifican
            < self.cantidad_grupos
        ):

            raise ValidationError({
                "equipos_clasifican": (
                    "La cantidad de equipos que "
                    "clasifican no puede ser menor "
                    "que la cantidad de grupos."
                )
            })

        if (
            self.equipos_clasifican
            % self.cantidad_grupos != 0
        ):

            raise ValidationError({
                "equipos_clasifican": (
                    "La cantidad de equipos que "
                    "clasifican debe ser divisible "
                    "entre la cantidad de grupos."
                )
            })

    def __str__(self):

        return (
            f"{self.torneo.nombre} - "
            f"{self.cantidad_grupos} grupos - "
            f"{self.equipos_clasifican} clasifican"
        )


# =========================================================
# FASE DEL TORNEO
# =========================================================

class FaseTorneo(models.Model):

    TIPO_CHOICES = [
        ("grupos", "Fase de grupos"),
        ("octavos", "Octavos de final"),
        ("cuartos", "Cuartos de final"),
        ("semifinal", "Semifinal"),
        ("final", "Final"),
    ]

    torneo = models.ForeignKey(
        Torneo,
        on_delete=models.CASCADE,
        related_name="fases"
    )

    nombre = models.CharField(
        max_length=100
    )

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES
    )

    orden = models.PositiveIntegerField()

    activa = models.BooleanField(
        default=False
    )

    creada_automaticamente = models.BooleanField(
        default=False
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    actualizado_en = models.DateTimeField(
        auto_now=True
    )

    class Meta:

        ordering = [
            "orden"
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "torneo",
                    "tipo"
                ],
                name="fase_unica_por_tipo_torneo"
            )
        ]

    def __str__(self):

        return (
            f"{self.torneo.nombre} - "
            f"{self.nombre}"
        )


# =========================================================
# GRUPO
# =========================================================

class Grupo(models.Model):

    fase = models.ForeignKey(
        FaseTorneo,
        on_delete=models.CASCADE,
        related_name="grupos"
    )

    nombre = models.CharField(
        max_length=50
    )

    numero = models.PositiveIntegerField()

    equipos = models.ManyToManyField(
        Equipo,
        related_name="grupos_torneo",
        blank=True
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    actualizado_en = models.DateTimeField(
        auto_now=True
    )

    class Meta:

        ordering = [
            "numero"
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "fase",
                    "numero"
                ],
                name="grupo_unico_por_fase"
            )
        ]

    def __str__(self):

        return (
            f"{self.fase.torneo.nombre} - "
            f"{self.nombre}"
        )


# =========================================================
# EQUIPO EN GRUPO
# =========================================================

class EquipoGrupo(models.Model):

    grupo = models.ForeignKey(
        Grupo,
        on_delete=models.CASCADE,
        related_name="equipos_grupo"
    )

    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name="grupos_asignados"
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "grupo",
                    "equipo"
                ],
                name="equipo_unico_por_grupo"
            )
        ]

    def __str__(self):

        return (
            f"{self.equipo.nombre} - "
            f"{self.grupo.nombre}"
        )


# =========================================================
# PARTIDO
# =========================================================

class Partido(models.Model):

    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("programado", "Programado"),
        ("jugado", "Jugado"),
        ("cancelado", "Cancelado"),
    ]

    torneo = models.ForeignKey(
        Torneo,
        on_delete=models.CASCADE,
        related_name="partidos"
    )

    fase = models.ForeignKey(
        FaseTorneo,
        on_delete=models.CASCADE,
        related_name="partidos",
        null=True,
        blank=True
    )

    grupo = models.ForeignKey(
        Grupo,
        on_delete=models.CASCADE,
        related_name="partidos",
        null=True,
        blank=True
    )

    equipo_local = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name="partidos_local"
    )

    equipo_visitante = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name="partidos_visitante"
    )

    numero = models.PositiveIntegerField()

    jornada = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    fecha = models.DateField(
        null=True,
        blank=True
    )

    hora = models.TimeField(
        null=True,
        blank=True
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default="pendiente"
    )

    partido_origen_local = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="partidos_destino_local",
        null=True,
        blank=True
    )

    partido_origen_visitante = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="partidos_destino_visitante",
        null=True,
        blank=True
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    actualizado_en = models.DateTimeField(
        auto_now=True
    )

    class Meta:

        ordering = [
            "numero"
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "torneo",
                    "numero"
                ],
                name="partido_unico_por_torneo"
            )
        ]

    def clean(self):

        super().clean()

        if (
            self.equipo_local
            and self.equipo_visitante
            and self.equipo_local
            == self.equipo_visitante
        ):

            raise ValidationError({
                "equipo_visitante": (
                    "Un equipo no puede jugar "
                    "contra sí mismo."
                )
            })

        if self.fase:

            if self.fase.torneo_id != self.torneo_id:

                raise ValidationError({
                    "fase": (
                        "La fase debe pertenecer "
                        "al mismo torneo."
                    )
                })

        if self.grupo:

            if not self.fase:

                raise ValidationError({
                    "grupo": (
                        "El partido debe tener una "
                        "fase antes de asignar un grupo."
                    )
                })

            if self.grupo.fase_id != self.fase_id:

                raise ValidationError({
                    "grupo": (
                        "El grupo debe pertenecer "
                        "a la fase seleccionada."
                    )
                })

            if (
                self.grupo.fase.torneo_id
                != self.torneo_id
            ):

                raise ValidationError({
                    "grupo": (
                        "El grupo debe pertenecer "
                        "al mismo torneo."
                    )
                })

    def __str__(self):

        return (
            f"Partido {self.numero} - "
            f"{self.equipo_local.nombre} vs "
            f"{self.equipo_visitante.nombre}"
        )


# =========================================================
# RESULTADO DEL PARTIDO
# =========================================================

class ResultadoPartido(models.Model):

    partido = models.OneToOneField(
        Partido,
        on_delete=models.CASCADE,
        related_name="resultado"
    )
    sets_programados = models.PositiveSmallIntegerField(
        choices=[
            (3, "Mejor de 3 sets"),
            (5, "Mejor de 5 sets"),
        ],
        null=True,
        blank=True,
    )
    marcador_local = models.PositiveIntegerField(
        default=0
    )

    marcador_visitante = models.PositiveIntegerField(
        default=0
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    actualizado_en = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):

        return (
            f"{self.partido} - "
            f"{self.marcador_local} : "
            f"{self.marcador_visitante}"
        )

# =========================================================
# PARTICIPACIÓN DE JUGADORES EN PARTIDOS
# =========================================================

class ParticipacionPartido(models.Model):

    partido = models.ForeignKey(
        Partido,
        on_delete=models.CASCADE,
        related_name="participaciones"
    )

    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name="participaciones_partidos"
    )

    jugador = models.ForeignKey(
        IntegranteEquipo,
        on_delete=models.CASCADE,
        related_name="participaciones"
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "partido",
                    "jugador"
                ],
                name="participacion_unica_jugador_partido"
            )
        ]

    def clean(self):

        super().clean()

        if self.partido:

            equipos_partido = [
                self.partido.equipo_local_id,
                self.partido.equipo_visitante_id,
            ]

            if self.equipo_id not in equipos_partido:

                raise ValidationError({
                    "equipo": (
                        "El equipo debe participar "
                        "en el partido."
                    )
                })

        if self.jugador and self.equipo:

            if self.jugador.equipo_id != self.equipo_id:

                raise ValidationError({
                    "jugador": (
                        "El jugador debe pertenecer "
                        "al equipo seleccionado."
                    )
                })

    def __str__(self):

        return (
            f"{self.jugador} - "
            f"{self.partido}"
        )
# =========================================================
# GOLES
# =========================================================

class Gol(models.Model):

    partido = models.ForeignKey(
        Partido,
        on_delete=models.CASCADE,
        related_name="goles"
    )

    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name="goles"
    )

    jugador = models.ForeignKey(
        IntegranteEquipo,
        on_delete=models.CASCADE,
        related_name="goles"
    )

    minuto = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    def clean(self):

        super().clean()

        if self.partido:

            if self.partido.torneo.deporte != "futbol":

                raise ValidationError(
                    "Los goles solamente "
                    "pueden registrarse en fútbol."
                )

            equipos_partido = [
                self.partido.equipo_local_id,
                self.partido.equipo_visitante_id,
            ]

            if self.equipo_id not in equipos_partido:

                raise ValidationError({
                    "equipo": (
                        "El equipo debe participar "
                        "en el partido."
                    )
                })

        if self.jugador and self.equipo:

            if self.jugador.equipo_id != self.equipo_id:

                raise ValidationError({
                    "jugador": (
                        "El jugador debe pertenecer "
                        "al equipo seleccionado."
                    )
                })

    def __str__(self):

        return (
            f"{self.jugador} - "
            f"{self.partido}"
        )


# =========================================================
# TARJETAS
# =========================================================

class Tarjeta(models.Model):

    TIPO_CHOICES = [
        ("amarilla", "Tarjeta amarilla"),
        ("roja", "Tarjeta roja"),
    ]

    partido = models.ForeignKey(
        Partido,
        on_delete=models.CASCADE,
        related_name="tarjetas"
    )

    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name="tarjetas"
    )

    jugador = models.ForeignKey(
        IntegranteEquipo,
        on_delete=models.CASCADE,
        related_name="tarjetas"
    )

    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CHOICES
    )

    minuto = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    @property
    def penalizacion_juego_limpio(self):

        if self.tipo == "amarilla":

            return -1

        if self.tipo == "roja":

            return -2

        return 0

    def clean(self):

        super().clean()

        if self.partido:

            equipos_partido = [
                self.partido.equipo_local_id,
                self.partido.equipo_visitante_id,
            ]

            if self.equipo_id not in equipos_partido:

                raise ValidationError({
                    "equipo": (
                        "El equipo debe participar "
                        "en el partido."
                    )
                })

        if self.jugador and self.equipo:

            if self.jugador.equipo_id != self.equipo_id:

                raise ValidationError({
                    "jugador": (
                        "El jugador debe pertenecer "
                        "al equipo seleccionado."
                    )
                })

    def __str__(self):

        return (
            f"{self.jugador} - "
            f"{self.get_tipo_display()} - "
            f"{self.partido}"
        )


# =========================================================
# RECUPERACIÓN DE CONTRASEÑA
# =========================================================

class PasswordResetCode(models.Model):

    usuario = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="codigos_recuperacion"
    )

    correo = models.EmailField(
        max_length=254,
        db_index=True
    )

    codigo_hash = models.CharField(
        max_length=128
    )

    creado_en = models.DateTimeField(
        default=timezone.now,
        db_index=True
    )

    expira_en = models.DateTimeField()

    intentos = models.PositiveSmallIntegerField(
        default=0
    )

    usado_en = models.DateTimeField(
        null=True,
        blank=True
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["-creado_en"]
        indexes = [
            models.Index(
                fields=["correo", "creado_en"],
                name="reset_correo_fecha_idx"
            ),
            models.Index(
                fields=["ip_address", "creado_en"],
                name="reset_ip_fecha_idx"
            ),
        ]

    def __str__(self):
        return (
            f"Recuperación de contraseña: "
            f"{self.correo}"
        )
# =========================================================
# DETALLE DE SETS DE UN RESULTADO
# =========================================================

class SetResultado(models.Model):

    resultado = models.ForeignKey(
        ResultadoPartido,
        on_delete=models.CASCADE,
        related_name="sets",
    )

    numero = models.PositiveSmallIntegerField()

    puntos_local = models.PositiveIntegerField()

    puntos_visitante = models.PositiveIntegerField()

    class Meta:
        ordering = ["numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["resultado", "numero"],
                name="unique_set_por_resultado",
            )
        ]

    def __str__(self):
        return (
            f"Set {self.numero}: "
            f"{self.puntos_local} - "
            f"{self.puntos_visitante}"
        )

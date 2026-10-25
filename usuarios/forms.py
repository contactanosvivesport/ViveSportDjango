import re
import calendar
from datetime import datetime, timedelta
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Usuario,
    Torneo,
    Equipo,
    ConfiguracionInscripcion,
    IntegranteEquipo,
    ConfiguracionCompeticion,
    Partido,
    ResultadoPartido,
    Gol,
    Tarjeta,
    ParticipacionPartido
)


# =========================================================
# FORMULARIO DE REGISTRO DE USUARIO
# =========================================================

class RegistroForm(forms.ModelForm):

    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Mínimo 8 caracteres"
            }
        ),
        min_length=8
    )

    confirmar_password = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Repita su contraseña"
            }
        )
    )

    class Meta:

        model = Usuario

        fields = [
            "nombre",
            "apellido",
            "correo",
            "celular",
            "centro_formacion",
            "jornada",
            "ficha",
        ]

        widgets = {

            "nombre": forms.TextInput(
                attrs={
                    "placeholder": "Ingrese su nombre"
                }
            ),

            "apellido": forms.TextInput(
                attrs={
                    "placeholder": "Ingrese su apellido"
                }
            ),

            "correo": forms.EmailInput(
                attrs={
                    "placeholder": "correo@ejemplo.com"
                }
            ),

            "centro_formacion": forms.Select(),

            "jornada": forms.Select(),

            "ficha": forms.TextInput(
                attrs={
                    "placeholder": "7 dígitos",
                    "inputmode": "numeric",
                    "maxlength": "7"
                }
            ),
        }

    def clean_nombre(self):

        nombre = self.cleaned_data["nombre"].strip()

        if not re.fullmatch(
            r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü\s]+",
            nombre
        ):

            raise ValidationError(
                "El nombre solo puede contener letras."
            )

        return nombre

    def clean_apellido(self):

        apellido = self.cleaned_data["apellido"].strip()

        if not re.fullmatch(
            r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü\s]+",
            apellido
        ):

            raise ValidationError(
                "El apellido solo puede contener letras."
            )

        return apellido

    def clean_correo(self):

        correo = self.cleaned_data["correo"].strip().lower()

        if Usuario.objects.filter(
            correo=correo
        ).exists():

            raise ValidationError(
                "Este correo ya está registrado."
            )

        return correo

    def clean_celular(self):

        celular = self.cleaned_data["celular"].strip()

        if not celular.isdigit():

            raise ValidationError(
                "El celular solo puede contener números."
            )

        if len(celular) != 10:

            raise ValidationError(
                "El celular debe tener exactamente 10 números."
            )

        return celular

    def clean_ficha(self):
        ficha = self.cleaned_data["ficha"].strip()

        if not ficha.isdigit():
            raise ValidationError(
                "El número de ficha solo puede contener números."
            )

        if len(ficha) != 7:
            raise ValidationError(
                "El número de ficha debe tener exactamente 7 dígitos."
            )

        return ficha

    def clean(self):

        cleaned_data = super().clean()

        password = cleaned_data.get("password")

        confirmar_password = cleaned_data.get(
            "confirmar_password"
        )

        if password and confirmar_password:

            if password != confirmar_password:

                self.add_error(
                    "confirmar_password",
                    "Las contraseñas no coinciden."
                )

        return cleaned_data

    def save(self, commit=True):

        usuario = super().save(commit=False)

        usuario.set_password(
            self.cleaned_data["password"]
        )

        usuario.rol = "usuario"

        if commit:

            usuario.save()

        return usuario


# =========================================================
# FORMULARIO ADMINISTRATIVO DE USUARIOS
# =========================================================

class UsuarioAdminForm(forms.ModelForm):

    correo = forms.EmailField(
        label="Correo",
        error_messages={
            "required": (
                "El correo electrónico es obligatorio."
            ),
            "invalid": (
                "Ingrese un correo electrónico válido."
            )
        },
        widget=forms.EmailInput(
            attrs={
                "placeholder": "correo@ejemplo.com"
            }
        )
    )

    password = forms.CharField(
        label="Contraseña",
        required=False,
        min_length=8,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Mínimo 8 caracteres"
            }
        ),
        error_messages={
            "required": (
                "La contraseña es obligatoria."
            ),
            "min_length": (
                "La contraseña debe tener mínimo 8 caracteres."
            )
        }
    )

    confirmar_password = forms.CharField(
        label="Confirmar contraseña",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Repita la contraseña"
            }
        ),
        error_messages={
            "required": (
                "Debe confirmar la contraseña."
            )
        }
    )

    class Meta:

        model = Usuario

        fields = [
            "nombre",
            "apellido",
            "correo",
            "celular",
            "centro_formacion",
            "jornada",
            "ficha",
        ]

        widgets = {

            "nombre": forms.TextInput(
                attrs={
                    "placeholder": "Ingrese su nombre"
                }
            ),

            "apellido": forms.TextInput(
                attrs={
                    "placeholder": "Ingrese el apellido"
                }
            ),

            "celular": forms.TextInput(
                attrs={
                    "placeholder": "10 dígitos",
                    "inputmode": "numeric",
                    "maxlength": "10"
                }
            ),

            "centro_formacion": forms.Select(),

            "jornada": forms.Select(),

            "ficha": forms.TextInput(
                attrs={
                    "placeholder": "7 dígitos",
                    "inputmode": "numeric",
                    "maxlength": "7"
                }
            ),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        if not self.instance.pk:

            self.fields["password"].required = True

            self.fields["confirmar_password"].required = True

            self.fields["password"].widget.attrs[
                "placeholder"
            ] = "Mínimo 8 caracteres"

            self.fields["confirmar_password"].widget.attrs[
                "placeholder"
            ] = "Repita la contraseña"

        else:

            self.fields["password"].required = False

            self.fields["confirmar_password"].required = False

            self.fields["password"].widget.attrs[
                "placeholder"
            ] = "Dejar vacío para conservar la actual"

            self.fields["confirmar_password"].widget.attrs[
                "placeholder"
            ] = "Repita la nueva contraseña"

    def clean_nombre(self):

        nombre = self.cleaned_data["nombre"].strip()

        if not re.fullmatch(
            r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü\s]+",
            nombre
        ):

            raise ValidationError(
                "El nombre solo puede contener letras."
            )

        return nombre

    def clean_apellido(self):

        apellido = self.cleaned_data["apellido"].strip()

        if not re.fullmatch(
            r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü\s]+",
            apellido
        ):

            raise ValidationError(
                "El apellido solo puede contener letras."
            )

        return apellido

    def clean_correo(self):

        correo = self.cleaned_data["correo"].strip().lower()

        queryset = Usuario.objects.filter(
            correo__iexact=correo
        )

        if self.instance.pk:

            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():

            raise ValidationError(
                "Este correo ya está registrado."
            )

        return correo

    def clean_celular(self):

        celular = self.cleaned_data["celular"].strip()

        if not celular.isdigit():

            raise ValidationError(
                "El celular solo puede contener números."
            )

        if len(celular) != 10:

            raise ValidationError(
                "El celular debe tener exactamente 10 números."
            )

        return celular

    def clean_ficha(self):
        
        ficha = self.cleaned_data["ficha"].strip()

        if not ficha.isdigit():
            raise ValidationError(
                "El número de ficha solo puede contener números."
            )

        if len(ficha) != 7:
            raise ValidationError(
                "El número de ficha debe tener exactamente 7 dígitos."
            )

        return ficha


    def clean(self):

        cleaned_data = super().clean()

        password = cleaned_data.get("password")

        confirmar_password = cleaned_data.get(
            "confirmar_password"
        )

        if not self.instance.pk:

            if not password:

                self.add_error(
                    "password",
                    "La contraseña es obligatoria."
                )

            if not confirmar_password:

                self.add_error(
                    "confirmar_password",
                    "Debe confirmar la contraseña."
                )

        if password or confirmar_password:

            if password != confirmar_password:

                self.add_error(
                    "confirmar_password",
                    "Las contraseñas no coinciden."
                )

        return cleaned_data

    def save(self, commit=True):

        usuario = super().save(commit=False)

        password = self.cleaned_data.get("password")

        if password:

            usuario.set_password(password)

        if commit:

            usuario.save()

        return usuario


# =========================================================
# FORMULARIO DE TORNEOS
# =========================================================



class TorneoForm(forms.ModelForm):

    class Meta:
        model = Torneo

        fields = [
            "nombre",
            "deporte",
            "duracion_partido",
            "descripcion",
            "fecha_inicio",
        ]

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "placeholder": "Ingrese el nombre del torneo"
                }
            ),

            "deporte": forms.Select(),

            "duracion_partido": forms.NumberInput(
                attrs={
                    "min": "1",
                    "step": "1",
                    "placeholder": "Ejemplo: 60",
                }
            ),

            "descripcion": forms.Textarea(
                attrs={
                    "placeholder": "Ingrese la descripción del torneo",
                    "rows": 5,
                }
            ),

            "fecha_inicio": forms.DateInput(
                attrs={
                    "type": "date",
                }
            ),
        }

    def clean_duracion_partido(self):
        duracion = self.cleaned_data.get("duracion_partido")

        if duracion is None or duracion < 1:
            raise ValidationError(
                "La duración del partido debe ser de al menos 1 minuto."
            )

        return duracion

    def clean_fecha_inicio(self):
        fecha_inicio = self.cleaned_data.get("fecha_inicio")

        if (
            fecha_inicio
            and fecha_inicio < timezone.localdate()
        ):
            raise ValidationError(
                "La fecha de inicio no puede ser anterior al día de hoy."
            )

        return fecha_inicio

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.error_messages["required"] = (
                "Este campo es obligatorio."
            )

        

# =========================================================
# FORMULARIO DE CONFIGURACIÓN DE INSCRIPCIONES
# =========================================================

class ConfiguracionInscripcionForm(forms.ModelForm):

    class Meta:

        model = ConfiguracionInscripcion

        fields = [
            "torneo",
            "minimo_integrantes",
            "maximo_integrantes",
        ]

        widgets = {

            "torneo": forms.Select(),

            "minimo_integrantes": forms.NumberInput(
                attrs={
                    "min": "1",
                    "placeholder": "Ejemplo: 7"
                }
            ),

            "maximo_integrantes": forms.NumberInput(
                attrs={
                    "min": "1",
                    "placeholder": "Ejemplo: 11"
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.error_messages["required"] = (
                "Este campo es obligatorio."
            )

            field.error_messages["unique"] = (
                "Ya existe una configuración con este Torneo."
            )

# =========================================================
# FORMULARIO PARA CREAR EQUIPO
# =========================================================

class EquipoForm(forms.ModelForm):

    class Meta:

        model = Equipo

        fields = [
            "nombre",
        ]

        widgets = {

            "nombre": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Ingrese el nombre del equipo"
                    )
                }
            ),
        }

        labels = {
            "nombre": "Nombre del equipo"
        }

    def clean_nombre(self):

        nombre = self.cleaned_data["nombre"].strip()

        if not nombre:

            raise ValidationError(
                "El nombre del equipo es obligatorio."
            )

        return nombre


# =========================================================
# FORMULARIO PARA AGREGAR / EDITAR INTEGRANTES
# =========================================================

class IntegranteEquipoForm(forms.ModelForm):

    class Meta:

        model = IntegranteEquipo

        fields = [
            "nombre",
            "apellido",
            "celular",
            "centro_formacion",
            "jornada",
            "ficha",
        ]

        widgets = {

            "nombre": forms.TextInput(
                attrs={
                    "placeholder": "Ingrese el nombre"
                }
            ),

            "apellido": forms.TextInput(
                attrs={
                    "placeholder": "Ingrese el apellido"
                }
            ),

            "celular": forms.TextInput(
                attrs={
                    "placeholder": "10 dígitos",
                    "inputmode": "numeric",
                    "maxlength": "10"
                }
            ),

            "centro_formacion": forms.Select(),

            "jornada": forms.Select(),

            "ficha": forms.TextInput(
                attrs={
                    "placeholder": "7 dígitos",
                    "inputmode": "numeric",
                    "maxlength": "7"
                }
            ),
        }

        labels = {

            "nombre": "Nombre",

            "apellido": "Apellido",

            "celular": "Celular",

            "centro_formacion": "Centro de formación",

            "jornada": "Jornada",

            "ficha": "Número de ficha",
        }

    # =====================================================
    # INICIALIZAR FORMULARIO
    # =====================================================

    def __init__(self, *args, **kwargs):

        self.equipo = kwargs.pop(
            "equipo",
            None
        )

        super().__init__(
            *args,
            **kwargs
        )

    # =====================================================
    # VALIDAR NOMBRE
    # =====================================================

    def clean_nombre(self):

        nombre = self.cleaned_data["nombre"].strip()

        if not re.fullmatch(
            r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü\s]+",
            nombre
        ):

            raise ValidationError(
                "El nombre solo puede contener letras."
            )

        return nombre

    # =====================================================
    # VALIDAR APELLIDO
    # =====================================================

    def clean_apellido(self):

        apellido = self.cleaned_data["apellido"].strip()

        if not re.fullmatch(
            r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü\s]+",
            apellido
        ):

            raise ValidationError(
                "El apellido solo puede contener letras."
            )

        return apellido

    # =====================================================
    # VALIDAR CELULAR
    # =====================================================

    def clean_celular(self):

        celular = self.cleaned_data["celular"].strip()

        if not celular.isdigit():

            raise ValidationError(
                "El celular solo puede contener números."
            )

        if len(celular) != 10:

            raise ValidationError(
                "El celular debe tener exactamente 10 números."
            )

        return celular

    # =====================================================
    # VALIDAR FICHA
    # =====================================================

    def clean_ficha(self):
        ficha = self.cleaned_data["ficha"].strip()

        if not ficha.isdigit():
            raise ValidationError(
                "El número de ficha solo puede contener números."
            )

        if len(ficha) != 7:
            raise ValidationError(
                "El número de ficha debe tener exactamente 7 dígitos."
            )

        return ficha

    # =====================================================
    # VALIDAR INTEGRANTE DUPLICADO
    # =====================================================

    def clean(self):

        cleaned_data = super().clean()

        nombre = cleaned_data.get("nombre")
        apellido = cleaned_data.get("apellido")

        # -------------------------------------------------
        # SI FALTAN DATOS NO HACEMOS ESTA VALIDACIÓN
        # -------------------------------------------------

        if not nombre or not apellido:

            return cleaned_data

        # -------------------------------------------------
        # SI NO TENEMOS EQUIPO NO PODEMOS COMPARAR
        # -------------------------------------------------

        if not self.equipo:

            return cleaned_data

        # -------------------------------------------------
        # NORMALIZAR
        # -------------------------------------------------

        nombre_normalizado = nombre.strip().lower()
        apellido_normalizado = apellido.strip().lower()

        # -------------------------------------------------
        # BUSCAR INTEGRANTE CON EL MISMO NOMBRE Y APELLIDO
        # -------------------------------------------------

        queryset = self.equipo.integrantes.filter(
            nombre__iexact=nombre_normalizado,
            apellido__iexact=apellido_normalizado
        )

        # -------------------------------------------------
        # SI ESTAMOS EDITANDO, EXCLUIR EL MISMO INTEGRANTE
        # -------------------------------------------------

        if self.instance.pk:

            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        # -------------------------------------------------
        # VALIDAR DUPLICADO
        # -------------------------------------------------

        if queryset.exists():

            raise ValidationError(
                (
                    f"El integrante "
                    f"{nombre.strip()} "
                    f"{apellido.strip()} "
                    f"ya está registrado en este equipo."
                )
            )

        return cleaned_data


# =========================================================
# FORMULARIO DE CONFIGURACIÓN DE COMPETICIÓN
# =========================================================

class ConfiguracionCompeticionForm(forms.ModelForm):

    class Meta:

        model = ConfiguracionCompeticion

        fields = [
            "torneo",
            "cantidad_grupos",
            "equipos_clasifican",
        ]

        widgets = {

            "torneo": forms.Select(),

            "cantidad_grupos": forms.NumberInput(
                attrs={
                    "min": "1",
                    "placeholder": "Ejemplo: 4"
                }
            ),

            "equipos_clasifican": forms.NumberInput(
    attrs={
        "min": "2",
        "max": "8",
        "step": "1",
        "placeholder": "Ejemplo: 8"
    }
),
        }

        labels = {

            "torneo": "Torneo",

            "cantidad_grupos": (
                "Cantidad de grupos"
            ),

            "equipos_clasifican": (
                "Equipos que clasifican"
            ),
        }

    # =====================================================
    # VALIDAR QUE EL TORNEO NO TENGA OTRA CONFIGURACIÓN
    # =====================================================

    def clean_torneo(self):

        torneo = self.cleaned_data.get("torneo")

        if torneo is None:
            return torneo

        configuracion_existente = (
            ConfiguracionCompeticion.objects
            .filter(torneo=torneo)
            .exclude(pk=self.instance.pk)
            .exists()
        )

        if configuracion_existente:

            raise forms.ValidationError(
                "Este torneo ya tiene una configuración de competición."
            )

        return torneo


# =========================================================
# FORMULARIO PARA EDITAR CONFIGURACIÓN DE COMPETICIÓN
# =========================================================

class EditarConfiguracionCompeticionForm(forms.ModelForm):

    class Meta:

        model = ConfiguracionCompeticion

        fields = [
            "cantidad_grupos",
            "equipos_clasifican",
        ]

        widgets = {

            "cantidad_grupos": forms.NumberInput(
                attrs={
                    "min": "1",
                    "placeholder": "Ejemplo: 4"
                }
            ),

            "equipos_clasifican": forms.NumberInput(
                attrs={
                    "min": "2",
                    "placeholder": "Ejemplo: 8"
                }
            ),
        }

        labels = {

            "cantidad_grupos": (
                "Cantidad de grupos"
            ),

            "equipos_clasifican": (
                "Equipos que clasifican"
            ),
        }


# =========================================================
# FORMULARIO PARA PROGRAMAR PARTIDO
# =========================================================



class ProgramarPartidoForm(forms.ModelForm):

    fecha = forms.DateField(
        label="Fecha del partido",
        required=True,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "campo-formulario",
            }
        ),
        error_messages={
            "required": "Debes seleccionar la fecha del partido.",
            "invalid": "Introduce una fecha válida.",
        },
    )

    hora = forms.TimeField(
        label="Hora del partido",
        required=True,
        widget=forms.TimeInput(
            attrs={
                "type": "time",
                "class": "campo-formulario",
            }
        ),
        error_messages={
            "required": "Debes seleccionar la hora del partido.",
            "invalid": "Introduce una hora válida.",
        },
    )

    class Meta:
        model = Partido
        fields = ["fecha", "hora"]

    def _sumar_meses(self, fecha_hora, meses):
        mes_total = fecha_hora.month - 1 + meses
        anio = fecha_hora.year + mes_total // 12
        mes = mes_total % 12 + 1

        ultimo_dia = calendar.monthrange(anio, mes)[1]
        dia = min(fecha_hora.day, ultimo_dia)

        return fecha_hora.replace(
            year=anio,
            month=mes,
            day=dia,
        )

    def clean_fecha(self):
        fecha = self.cleaned_data.get("fecha")

        if not fecha:
            return fecha

        torneo = self.instance.torneo

        if fecha <= torneo.fecha_inicio:
            raise ValidationError(
                "La fecha del partido debe ser posterior "
                "a la fecha de inicio del torneo."
            )

        return fecha

    def clean(self):
        cleaned_data = super().clean()

        fecha = cleaned_data.get("fecha")
        hora = cleaned_data.get("hora")

        if not fecha or not hora:
            return cleaned_data

        partido_actual = self.instance

        if partido_actual.estado in ["jugado", "cancelado"]:
            raise ValidationError(
                "No puedes programar ni editar un partido "
                "que ya está jugado o cancelado."
            )

        ahora = timezone.localtime(timezone.now())

        fecha_hora_partido = timezone.make_aware(
            datetime.combine(fecha, hora),
            timezone.get_current_timezone(),
        )

        limite_minimo = ahora + timedelta(hours=1)
        limite_maximo = self._sumar_meses(ahora, 6)

        if fecha_hora_partido < limite_minimo:
            raise ValidationError(
                "El partido debe programarse con al menos "
                "una hora de anticipación respecto al "
                "momento actual."
            )

        if fecha_hora_partido > limite_maximo:
            raise ValidationError(
                "La fecha y hora del partido no pueden "
                "superar los seis meses desde el momento actual."
            )

        torneo = partido_actual.torneo

        # Conservar la validación de horario dentro del torneo.
        partidos_mismo_horario = Partido.objects.filter(
            torneo=torneo,
            fecha=fecha,
            hora=hora,
        ).exclude(
            estado="cancelado",
        )

        if partido_actual.pk:
            partidos_mismo_horario = (
                partidos_mismo_horario.exclude(
                    pk=partido_actual.pk
                )
            )

        if partidos_mismo_horario.exists():
            raise ValidationError(
                "Ya existe otro partido de este torneo "
                "en la misma fecha y hora."
            )

        # Equipos que participan en el partido que se programa.
        equipo_local = partido_actual.equipo_local
        equipo_visitante = partido_actual.equipo_visitante

        from django.db.models import Q

        equipos = (
            Q(equipo_local=equipo_local)
            | Q(equipo_visitante=equipo_local)
            | Q(equipo_local=equipo_visitante)
            | Q(equipo_visitante=equipo_visitante)
        )

        # Buscar encuentros de esos equipos en CUALQUIER torneo.
        # Se incluyen partidos programados y jugados.
        otros_partidos = (
            Partido.objects
            .filter(
                equipos,
                estado__in=["programado", "jugado"],
                fecha__isnull=False,
                hora__isnull=False,
            )
            .exclude(
                pk=partido_actual.pk
            )
            .select_related("torneo")
            .order_by("fecha", "hora")
        )

        descanso_minimo = timedelta(hours=1)

        duracion_actual = timedelta(
            minutes=torneo.duracion_partido
        )

        for otro in otros_partidos:

            inicio_otro = timezone.make_aware(
                datetime.combine(
                    otro.fecha,
                    otro.hora,
                ),
                timezone.get_current_timezone(),
            )

            duracion_otro = timedelta(
                minutes=otro.torneo.duracion_partido
            )

            fin_otro = inicio_otro + duracion_otro

            # Caso 1: el otro partido comienza antes
            # o al mismo tiempo que el partido propuesto.
            if inicio_otro <= fecha_hora_partido:

                primer_inicio_permitido = (
                    fin_otro + descanso_minimo
                )

                if (
                    fecha_hora_partido
                    < primer_inicio_permitido
                ):
                    raise ValidationError(
                        (
                            f"El equipo que participa en el "
                            f"partido {otro.numero} del torneo "
                            f"'{otro.torneo.nombre}' necesita "
                            f"terminar ese encuentro y descansar "
                            f"al menos una hora. Podrá jugar "
                            f"nuevamente a partir de las "
                            f"{primer_inicio_permitido.strftime('%d/%m/%Y %H:%M')}."
                        )
                    )

            # Caso 2: el otro partido comienza después
            # del partido que estamos programando.
            else:

                siguiente_inicio_permitido = (
                    fecha_hora_partido
                    + duracion_actual
                    + descanso_minimo
                )

                if inicio_otro < siguiente_inicio_permitido:
                    raise ValidationError(
                        (
                            f"Este horario afecta el descanso "
                            f"del equipo: ya tiene el partido "
                            f"{otro.numero} del torneo "
                            f"'{otro.torneo.nombre}' el "
                            f"{inicio_otro.strftime('%d/%m/%Y a las %H:%M')}. "
                            f"Después del partido propuesto "
                            f"debe disponer de una hora "
                            f"completa de descanso."
                        )
                    )

        return cleaned_data



# =========================================================
# FORMULARIO PARA REGISTRAR RESULTADO
# =========================================================

class ResultadoPartidoForm(forms.ModelForm):

    class Meta:

        model = ResultadoPartido

        fields = [
            "marcador_local",
            "marcador_visitante",
        ]

        widgets = {

            "marcador_local": forms.NumberInput(
                attrs={
                    "min": "0",
                    "placeholder": "Ejemplo: 2"
                }
            ),

            "marcador_visitante": forms.NumberInput(
                attrs={
                    "min": "0",
                    "placeholder": "Ejemplo: 1"
                }
            ),
        }

        labels = {

            "marcador_local": "Marcador local",

            "marcador_visitante": (
                "Marcador visitante"
            ),
        }

    # =====================================================
    # VALIDAR MARCADOR LOCAL
    # =====================================================

    def clean_marcador_local(self):

        marcador = self.cleaned_data.get(
            "marcador_local"
        )

        if marcador is None:
            return marcador

        if marcador < 0:

            raise ValidationError(
                "El marcador no puede ser negativo."
            )

        return marcador

    # =====================================================
    # VALIDAR MARCADOR VISITANTE
    # =====================================================

    def clean_marcador_visitante(self):

        marcador = self.cleaned_data.get(
            "marcador_visitante"
        )

        if marcador is None:
            return marcador

        if marcador < 0:

            raise ValidationError(
                "El marcador no puede ser negativo."
            )

        return marcador


# =========================================================
# FORMULARIO PARA REGISTRAR GOL
# =========================================================

class GolForm(forms.Form):

    jugador = forms.ModelChoiceField(
        queryset=IntegranteEquipo.objects.none(),
        label="Jugador",
        empty_label="Seleccione un jugador"
    )

    def __init__(self, *args, **kwargs):

        self.partido = kwargs.pop(
            "partido",
            None
        )

        super().__init__(
            *args,
            **kwargs
        )

        if self.partido:

            self.fields["jugador"].queryset = (
                IntegranteEquipo.objects
                .filter(
                    equipo__in=[
                        self.partido.equipo_local,
                        self.partido.equipo_visitante
                    ]
                )
                .order_by(
                    "nombre",
                    "apellido"
                )
            )

    def clean_jugador(self):

        jugador = self.cleaned_data.get(
            "jugador"
        )

        if not jugador:
            return jugador

        if jugador.equipo_id not in [
            self.partido.equipo_local_id,
            self.partido.equipo_visitante_id
        ]:

            raise ValidationError(
                (
                    "El jugador debe pertenecer "
                    "a uno de los equipos del partido."
                )
            )

        return jugador


# =========================================================
# FORMULARIO PARA REGISTRAR TARJETA
# =========================================================

class TarjetaForm(forms.Form):

    jugador = forms.ModelChoiceField(
        queryset=IntegranteEquipo.objects.none(),
        label="Jugador",
        empty_label="Seleccione un jugador"
    )

    tipo = forms.ChoiceField(
        choices=Tarjeta.TIPO_CHOICES,
        label="Tipo de tarjeta"
    )

    def __init__(self, *args, **kwargs):

        self.partido = kwargs.pop(
            "partido",
            None
        )

        super().__init__(
            *args,
            **kwargs
        )

        if self.partido:

            self.fields["jugador"].queryset = (
                IntegranteEquipo.objects
                .filter(
                    equipo__in=[
                        self.partido.equipo_local,
                        self.partido.equipo_visitante
                    ]
                )
                .order_by(
                    "nombre",
                    "apellido"
                )
            )

    def clean_jugador(self):

        jugador = self.cleaned_data.get(
            "jugador"
        )

        if not jugador:
            return jugador

        if jugador.equipo_id not in [
            self.partido.equipo_local_id,
            self.partido.equipo_visitante_id
        ]:

            raise ValidationError(
                (
                    "El jugador debe pertenecer "
                    "a uno de los equipos del partido."
                )
            )

        return jugador


# =========================================================
# FORMSET PARA REGISTRAR GOLES
# =========================================================

GolFormSet = forms.formset_factory(
    GolForm,
    extra=0
)


# =========================================================
# FORMSET PARA REGISTRAR TARJETAS
# =========================================================

TarjetaFormSet = forms.formset_factory(
    TarjetaForm,
    extra=0
)


# =========================================================
# FORMULARIO DE PARTICIPACIÓN EN PARTIDO
# =========================================================

class ParticipacionPartidoForm(forms.ModelForm):

    class Meta:

        model = ParticipacionPartido

        fields = [
            "jugador"
        ]

        labels = {
            "jugador": "Jugador"
        }

    def __init__(self, *args, **kwargs):

        partido = kwargs.pop(
            "partido",
            None
        )

        equipo = kwargs.pop(
            "equipo",
            None
        )

        super().__init__(
            *args,
            **kwargs
        )

        self.fields[
            "jugador"
        ].queryset = (
            IntegranteEquipo.objects.none()
        )

        if partido and equipo:

            if equipo not in [
                partido.equipo_local,
                partido.equipo_visitante
            ]:

                return

            self.fields[
                "jugador"
            ].queryset = (
                IntegranteEquipo.objects
                .filter(
                    equipo=equipo
                )
                .order_by(
                    "nombre",
                    "apellido"
                )
            )


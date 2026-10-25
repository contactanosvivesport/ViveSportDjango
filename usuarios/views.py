from django.contrib import messages
from .progresion_torneo import procesar_progresion_torneo
from django.db import models, transaction
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render
)

from .forms import (
    RegistroForm,
    UsuarioAdminForm,
    TorneoForm,
    ConfiguracionInscripcionForm,
    EquipoForm,
    IntegranteEquipoForm,
    ConfiguracionCompeticionForm,
    EditarConfiguracionCompeticionForm,
    ProgramarPartidoForm,
    ResultadoPartidoForm,
    GolFormSet,
    TarjetaFormSet
)

from .models import (
    Usuario,
    PasswordResetCode,
    Torneo,
    Equipo,
    IntegranteEquipo,
    ConfiguracionInscripcion,
    Inscripcion,
    ControlInscripcion,
    ConfiguracionCompeticion,
    FaseTorneo,
    Grupo,
    EquipoGrupo,
    Partido,
    ResultadoPartido,
    SetResultado,
    Gol,
    Tarjeta,
    ParticipacionPartido,
)
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import (
    check_password,
    make_password,
)
from django.contrib.auth.password_validation import (
    validate_password,
)
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils import timezone


def enviar_correo_vivesport(asunto, mensaje, destinatarios):
    """
    Programa el envío de una notificación después
    de confirmar la transacción de base de datos.
    """
    destinatarios_validos = list(
        dict.fromkeys(
            correo.strip()
            for correo in destinatarios
            if correo and correo.strip()
        )
    )

    if not destinatarios_validos:
        return

    transaction.on_commit(
        lambda: send_mail(
            asunto,
            mensaje,
            None,
            destinatarios_validos,
            fail_silently=True,
        )
    )


def notificar_administradores(asunto, mensaje):
    """
    Envía una notificación a los administradores activos.
    """
    destinatarios = (
        Usuario.objects
        .filter(
            rol="admin",
            is_active=True,
        )
        .exclude(correo="")
        .values_list("correo", flat=True)
        .distinct()
    )

    enviar_correo_vivesport(
        asunto,
        mensaje,
        destinatarios,
    )

# =========================================================
# REDIRECCIÓN SEGÚN EL ROL
# =========================================================

def redireccionar_por_rol(usuario):

    if usuario.rol == "admin":

        return redirect(
            "admin_dashboard"
        )

    return redirect(
        "inicio"
    )


# =========================================================
# REGISTRO
# =========================================================

def registro(request):

    if request.user.is_authenticated:

        return redireccionar_por_rol(
            request.user
        )

    if request.method == "POST":

        form = RegistroForm(
            request.POST
        )

        if form.is_valid():

            usuario = form.save()

            login(
                request,
                usuario
            )

            return redirect(
                "inicio"
            )

    else:

        form = RegistroForm()

    return render(
        request,
        "usuarios/registro.html",
        {
            "form": form
        }
    )


# =========================================================
# LOGIN
# =========================================================

def login_view(request):

    if request.user.is_authenticated:

        return redireccionar_por_rol(
            request.user
        )

    if request.method == "POST":

        correo = request.POST.get(
            "correo",
            ""
        ).strip().lower()

        password = request.POST.get(
            "password",
            ""
        )

        usuario = authenticate(
            request,
            correo=correo,
            password=password
        )

        if usuario is not None:

            login(
                request,
                usuario
            )

            return redireccionar_por_rol(
                usuario
            )

        return render(
            request,
            "usuarios/login.html",
            {
                "error": (
                    "Correo o contraseña incorrectos."
                ),
                "correo": correo
            }
        )

    return render(
        request,
        "usuarios/login.html"
    )


# =========================================================
# RECUPERACIÓN DE CONTRASEÑA: SOLICITAR CÓDIGO
# =========================================================

def solicitar_recuperacion(request):

    mensaje = (
        "Si existe una cuenta activa con ese correo, "
        "recibirás instrucciones para recuperar tu contraseña."
    )

    if request.method == "POST":

        correo = (
            request.POST.get("correo", "")
            .strip()
            .lower()
        )

        # Evitar procesar direcciones demasiado largas o vacías.
        if not correo or len(correo) > 254:
            return render(
                request,
                "usuarios/recuperar_password.html",
                {"mensaje": mensaje}
            )

        ahora = timezone.now()
        hace_15_minutos = ahora - timedelta(minutes=15)
        hace_24_horas = ahora - timedelta(hours=24)
        hace_60_segundos = ahora - timedelta(seconds=60)

        # Usamos la IP directa de la conexión.
        # No confiamos en X-Forwarded-For enviado por el cliente.
        ip = request.META.get("REMOTE_ADDR")

        solicitudes_correo = PasswordResetCode.objects.filter(
            correo__iexact=correo
        )

        solicitudes_ip = PasswordResetCode.objects.none()

        if ip:
            solicitudes_ip = PasswordResetCode.objects.filter(
                ip_address=ip
            )

        # Límites por correo.
        limite_correo = (
            solicitudes_correo.filter(
                creado_en__gte=hace_15_minutos
            ).count() >= 3
            or solicitudes_correo.filter(
                creado_en__gte=hace_24_horas
            ).count() >= 5
            or solicitudes_correo.filter(
                creado_en__gte=hace_60_segundos
            ).exists()
        )

        # Límites adicionales por IP.
        limite_ip = (
            solicitudes_ip.filter(
                creado_en__gte=hace_15_minutos
            ).count() >= 10
            or solicitudes_ip.filter(
                creado_en__gte=hace_24_horas
            ).count() >= 20
        )

        if limite_correo or limite_ip:
            return render(
                request,
                "usuarios/recuperar_password.html",
                {"mensaje": mensaje}
            )

        usuario = Usuario.objects.filter(
            correo__iexact=correo,
            is_active=True
        ).first()


        # Invalidar solicitudes anteriores de este correo.
        PasswordResetCode.objects.filter(
            correo__iexact=correo,
            usado_en__isnull=True
        ).update(usado_en=ahora)


        # Generamos siempre un código aleatorio.
        # Si la cuenta no existe, guardamos un registro ficticio
        # que nunca se enviará por correo.
        codigo = f"{secrets.randbelow(1_000_000):06d}"

        registro = PasswordResetCode.objects.create(
            usuario=usuario,
            correo=correo,
            codigo_hash=make_password(codigo),
            creado_en=ahora,
            expira_en=ahora + timedelta(minutes=10),
            ip_address=ip
        )

        # Solo se envía el código a una cuenta activa.
        if usuario is not None:

            try:
                send_mail(
                    subject="Código de recuperación - ViveSport",
                    message=(
                        f"Hola {usuario.nombre},\n\n"
                        "Recibimos una solicitud para cambiar "
                        "la contraseña de tu cuenta de ViveSport.\n\n"
                        f"Tu código de verificación es: {codigo}\n\n"
                        "Este código vence en 10 minutos y "
                        "solo puede utilizarse una vez.\n\n"
                        "Si no solicitaste este cambio, "
                        "ignora este mensaje."
                    ),
                    from_email=None,
                    recipient_list=[usuario.correo],
                    fail_silently=False
                )

            except Exception:
                # El código no debe poder utilizarse si el envío falla.
                registro.usado_en = timezone.now()
                registro.save(update_fields=["usado_en"])

        return redirect("verificar_codigo_recuperacion")

    return render(
        request,
        "usuarios/recuperar_password.html"
    )

# =========================================================
# RECUPERACIÓN DE CONTRASEÑA: VERIFICAR CÓDIGO
# =========================================================

def verificar_codigo_recuperacion(request):

    if request.method == "POST":

        correo = (
            request.POST.get("correo", "")
            .strip()
            .lower()
        )

        codigo = request.POST.get("codigo", "").strip()

        ahora = timezone.now()

        # Solo aceptamos códigos numéricos de seis dígitos.
        if (
            len(codigo) != 6
            or not codigo.isdigit()
            or len(correo) > 254
        ):
            messages.error(
                request,
                "El correo o el código no son válidos, "
                "o el código ha vencido."
            )

            return render(
                request,
                "usuarios/verificar_codigo.html"
            )

        # Buscamos la solicitud más reciente que todavía
        # pueda utilizarse para una cuenta activa.
        registro = PasswordResetCode.objects.filter(
            correo__iexact=correo,
            usuario__is_active=True,
            usado_en__isnull=True,
            expira_en__gt=ahora,
            intentos__lt=5
        ).order_by("-creado_en").first()

        if registro is None:

            messages.error(
                request,
                "El correo o el código no son válidos, "
                "o el código ha vencido."
            )

            return render(
                request,
                "usuarios/verificar_codigo.html"
            )

        # Incrementamos los intentos antes de validar
        # el código enviado por el usuario.
        
        if not check_password(codigo, registro.codigo_hash):

    # Contar únicamente los códigos incorrectos.
            registro.intentos += 1
            registro.save(update_fields=["intentos"])

            messages.error(
            request,
            "El correo o el código no son válidos, "
            "o el código ha vencido."
    )

            return render(
        request,
        "usuarios/verificar_codigo.html"
    )

# El código es correcto: no incrementar el contador.
# Continuar con la autorización temporal de recuperación.


        # Renovamos la clave de sesión para reducir el riesgo
        # de fijación de sesión.
        request.session.cycle_key()
        request.session.set_expiry(600)

        # Autorización temporal para cambiar la contraseña.
        request.session["password_reset_code_id"] = registro.pk
        request.session["password_reset_user_id"] = registro.usuario_id
        request.session["password_reset_expires"] = (
            ahora + timedelta(minutes=10)
        ).timestamp()

        return redirect("restablecer_password")

    return render(
        request,
        "usuarios/verificar_codigo.html"
    )

# =========================================================
# RECUPERACIÓN DE CONTRASEÑA: RESTABLECER CONTRASEÑA
# =========================================================

def restablecer_password(request):

    # Comprobar que la sesión contiene una autorización
    # válida obtenida tras verificar el código.
    codigo_id = request.session.get(
        "password_reset_code_id"
    )

    usuario_id = request.session.get(
        "password_reset_user_id"
    )

    autorizacion_expira = request.session.get(
        "password_reset_expires"
    )

    if not codigo_id or not usuario_id or not autorizacion_expira:
        messages.error(
            request,
            "Debes verificar un código válido antes de cambiar "
            "tu contraseña."
        )
        return redirect("solicitar_recuperacion")

    ahora = timezone.now()

    try:
        autorizacion_expira = float(autorizacion_expira)
    except (TypeError, ValueError):
        autorizacion_expira = 0

    if ahora.timestamp() >= autorizacion_expira:
        request.session.pop("password_reset_code_id", None)
        request.session.pop("password_reset_user_id", None)
        request.session.pop("password_reset_expires", None)
        request.session.set_expiry(None)

        messages.error(
            request,
            "La autorización ha vencido. Solicita un código nuevo."
        )
        return redirect("solicitar_recuperacion")

    registro = PasswordResetCode.objects.filter(
        pk=codigo_id,
        usuario_id=usuario_id,
        usuario__is_active=True,
        usado_en__isnull=True,
        expira_en__gt=ahora,
        intentos__lt=5
    ).first()

    if registro is None:
        request.session.pop("password_reset_code_id", None)
        request.session.pop("password_reset_user_id", None)
        request.session.pop("password_reset_expires", None)

        messages.error(
            request,
            "La solicitud de recuperación ya no es válida. "
            "Solicita un código nuevo."
        )
        return redirect("solicitar_recuperacion")

    usuario = registro.usuario

    if request.method == "POST":

        password = request.POST.get("password", "")
        confirmar_password = request.POST.get(
            "confirmar_password",
            ""
        )

        if not password or not confirmar_password:
            messages.error(
                request,
                "Debes completar los dos campos de contraseña."
            )

        elif password != confirmar_password:
            messages.error(
                request,
                "Las contraseñas no coinciden."
            )

        else:
            try:
                validate_password(password, user=usuario)

            except ValidationError as errores:
                for error in errores.messages:
                    messages.error(request, error)

            else:
                # Guardamos la contraseña mediante el mecanismo
                # seguro de Django, nunca como texto plano.
                usuario.set_password(password)
                usuario.save(update_fields=["password"])

                # Invalidar todos los códigos pendientes
                # asociados a esta cuenta.
                PasswordResetCode.objects.filter(
                    usuario=usuario,
                    usado_en__isnull=True
                ).update(usado_en=ahora)

                # Eliminar la autorización de recuperación.
                request.session.pop("password_reset_code_id", None)
                request.session.pop("password_reset_user_id", None)
                request.session.pop("password_reset_expires", None)

                messages.success(
                    request,
                    "Tu contraseña se ha actualizado correctamente. "
                    "Ya puedes iniciar sesión."
                )

                return redirect("login")

    return render(
        request,
        "usuarios/restablecer_password.html"
    )

# =========================================================
# INICIO USUARIO
# =========================================================

@login_required
def inicio(request):

    if request.user.rol == "admin":

        return redirect(
            "admin_dashboard"
        )

    return render(
        request,
        "usuarios/inicio.html"
    )


# =========================================================
# PANEL ADMINISTRATIVO
# =========================================================



@login_required
def admin_dashboard(request):

    if request.user.rol != "admin":
        return redirect("inicio")

    # Total de usuarios registrados
    usuarios_registrados = (
        Usuario.objects
        .filter(rol="usuario")
        .count()
    )

    # Total de equipos inscritos en torneos
    
    # Total de equipos con inscripción aceptada
    equipos_registrados = (
        Inscripcion.objects
        .filter(estado="aceptada")
        .values("equipo_id")
        .distinct()
        .count()
    )


    
    # Torneos activos:
    # - Inscripciones abiertas.
    # - Torneos en curso.
    # - Torneos con partidos jugados y resultados registrados.
    # - Excluir siempre los torneos finalizados.

    torneos_con_resultados = (
        Partido.objects
        .filter(
            estado="jugado",
            resultado__isnull=False,
        )
        .values("torneo_id")
    )

    torneos_activos = (
        Torneo.objects
        .filter(
            models.Q(
                estado__in=[
                    "inscripciones_abiertas",
                    "en_curso",
                ]
            )
            | models.Q(
                id__in=torneos_con_resultados
            )
        )
        .exclude(estado="finalizado")
        .distinct()
        .count()
    )


    return render(
        request,
        "usuarios/admin_dashboard.html",
        {
            "usuarios_registrados": usuarios_registrados,
            "equipos_registrados": equipos_registrados,
            "torneos_activos": torneos_activos,
        }
    )


# =========================================================
# CRUD USUARIOS
# =========================================================

@login_required
def usuarios_admin(request):

    if request.user.rol != "admin":
        return redirect(
            "inicio"
        )

    usuarios = (
        Usuario.objects
        .all()
        .order_by(
            "nombre",
            "apellido"
        )
    )

    return render(
        request,
        "usuarios/usuarios_admin.html",
        {
            "usuarios": usuarios
        }
    )


@login_required
def crear_usuario_admin(request):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    if request.method == "POST":

        form = UsuarioAdminForm(
            request.POST
        )

        if form.is_valid():

            usuario = form.save()

            messages.success(
                request,
                (
                    f"El usuario "
                    f"{usuario.nombre} "
                    f"{usuario.apellido} "
                    "fue creado correctamente."
                )
            )

            return redirect(
                "usuarios_admin"
            )

    else:

        form = UsuarioAdminForm()

    return render(
        request,
        "usuarios/crear_usuario_admin.html",
        {
            "form": form
        }
    )


@login_required
def ver_usuario_admin(
    request,
    usuario_id
):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    usuario = get_object_or_404(
        Usuario,
        id=usuario_id
    )

    return render(
        request,
        "usuarios/ver_usuario_admin.html",
        {
            "usuario": usuario
        }
    )


@login_required
def editar_usuario_admin(
    request,
    usuario_id
):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    usuario = get_object_or_404(
        Usuario,
        id=usuario_id
    )

    if (
        usuario.rol == "admin"
        and usuario.id != request.user.id
    ):

        messages.error(
            request,
            (
                "No puedes editar los datos "
                "de otro administrador."
            )
        )

        return redirect(
            "usuarios_admin"
        )

    if request.method == "POST":

        form = UsuarioAdminForm(
            request.POST,
            instance=usuario
        )

        if form.is_valid():

            usuario_actualizado = form.save()

            if (
                usuario_actualizado.id
                == request.user.id
            ):

                request.user.refresh_from_db()

            messages.success(
                request,
                (
                    f"Los datos de "
                    f"{usuario_actualizado.nombre} "
                    f"{usuario_actualizado.apellido} "
                    "fueron actualizados correctamente."
                )
            )

            return redirect(
                "usuarios_admin"
            )

    else:

        form = UsuarioAdminForm(
            instance=usuario
        )

    return render(
        request,
        "usuarios/editar_usuario_admin.html",
        {
            "form": form,
            "usuario": usuario
        }
    )



from django.db.models import Q

@login_required
def eliminar_usuario_admin(request, usuario_id):

    if request.user.rol != "admin":
        return redirect("inicio")

    usuario = get_object_or_404(
        Usuario,
        id=usuario_id
    )

    # La operación solo se permite mediante POST.
    if request.method != "POST":
        return redirect("usuarios_admin")

    # No permitir desactivar la propia cuenta.
    if usuario.id == request.user.id:
        messages.error(
            request,
            "No puedes desactivar tu propia cuenta."
        )
        return redirect("usuarios_admin")

    # No permitir desactivar otros administradores.
    if usuario.rol == "admin":
        messages.error(
            request,
            "No puedes desactivar la cuenta de otro administrador."
        )
        return redirect("usuarios_admin")

    # Comprobar si la cuenta ya está desactivada.
    if not usuario.is_active:
        messages.warning(
            request,
            "Esta cuenta ya se encuentra desactivada."
        )
        return redirect("usuarios_admin")

    # Buscar inscripciones relacionadas con el usuario,
    # tanto por responsable como por responsable del equipo.
    inscripciones_usuario = (
        Inscripcion.objects
        .filter(
            Q(responsable=usuario)
            | Q(equipo__responsable=usuario)
        )
        .select_related("torneo", "equipo")
        .distinct()
    )

    # Regla 1:
    # No desactivar si tiene alguna inscripción pendiente.
    tiene_inscripcion_pendiente = (
        inscripciones_usuario
        .filter(estado="pendiente")
        .exists()
    )

    if tiene_inscripcion_pendiente:
        messages.error(
            request,
            (
                f"No puedes desactivar a {usuario.nombre} "
                f"{usuario.apellido} porque tiene un equipo "
                "con una inscripción pendiente."
            )
        )
        return redirect("usuarios_admin")

    # Regla 2:
    # No desactivar si tiene un equipo inscrito y aceptado
    # en un torneo que todavía no ha finalizado.
    equipo_inscrito = (
        inscripciones_usuario
        .filter(
            estado="aceptada"
        )
        .exclude(
            torneo__estado="finalizado"
        )
        .exists()
    )

    if equipo_inscrito:
        messages.error(
            request,
            (
                f"No puedes desactivar a {usuario.nombre} "
                f"{usuario.apellido} porque tiene un equipo "
                "inscrito en un torneo que todavía no ha finalizado."
            )
        )
        return redirect("usuarios_admin")

    # Regla 3:
    # No desactivar si tiene alguna inscripción asociada
    # a un torneo en curso, independientemente del estado
    # de la inscripción.
    torneo_en_curso = (
        inscripciones_usuario
        .filter(
            torneo__estado="en_curso"
        )
        .exists()
    )

    if torneo_en_curso:
        messages.error(
            request,
            (
                f"No puedes desactivar a {usuario.nombre} "
                f"{usuario.apellido} porque tiene un equipo "
                "asociado a un torneo que está en curso."
            )
        )
        return redirect("usuarios_admin")

    # Si supera todas las comprobaciones, desactivar
    # la cuenta sin eliminar al usuario ni sus registros.
    usuario.is_active = False
    usuario.save(update_fields=["is_active"])

    messages.success(
        request,
        (
            f"La cuenta de {usuario.nombre} "
            f"{usuario.apellido} fue desactivada correctamente. "
            "Sus datos y registros históricos se conservaron."
        )
    )

    return redirect("usuarios_admin")


@login_required
def reactivar_usuario_admin(request, usuario_id):

    if request.user.rol != "admin":
        return redirect("inicio")

    # Reactivar solo mediante POST.
    if request.method != "POST":
        return redirect("usuarios_admin")

    usuario = get_object_or_404(
        Usuario,
        id=usuario_id
    )

    # Mantener la protección de cuentas administrativas.
    if usuario.rol == "admin":
        messages.error(
            request,
            "Esta opción solo permite reactivar cuentas de usuario."
        )
        return redirect("usuarios_admin")

    if usuario.is_active:
        messages.warning(
            request,
            "Esta cuenta ya está activa."
        )
        return redirect("usuarios_admin")

    # Verificar que ningún otro usuario, activo o inactivo,
    # tenga asignado el mismo correo.
    correo_en_uso = (
        Usuario.objects
        .filter(correo__iexact=usuario.correo)
        .exclude(pk=usuario.pk)
        .exists()
    )

    if correo_en_uso:
        messages.error(
            request,
            (
                "No se puede reactivar la cuenta porque existe "
                "otro usuario con ese correo electrónico. "
                "Revisa y resuelve el conflicto antes de continuar."
            )
        )
        return redirect("usuarios_admin")

    usuario.is_active = True
    usuario.save(update_fields=["is_active"])

    messages.success(
        request,
        (
            f"La cuenta de {usuario.nombre} "
            f"{usuario.apellido} fue reactivada correctamente."
        )
    )

    return redirect("usuarios_admin")


# =========================================================
# CRUD TORNEOS
# =========================================================

@login_required
def torneos_admin(request):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    torneos = (
        Torneo.objects
        .all()
        .order_by(
            "-fecha_inicio"
        )
    )

    return render(
        request,
        "usuarios/torneos_admin.html",
        {
            "torneos": torneos
        }
    )



@login_required
def crear_torneo(request):

    if request.user.rol != "admin":
        return redirect("inicio")

    if request.method == "POST":
        form = TorneoForm(request.POST)

        if form.is_valid():
            torneo = form.save()

            messages.success(
                request,
                (
                    f"El torneo '{torneo.nombre}' "
                    "fue creado correctamente."
                )
            )

            return redirect("torneos_admin")

    else:
        form = TorneoForm()

    return render(
        request,
        "usuarios/crear_torneo.html",
        {
            "form": form
        }
    )

@login_required
def ver_torneo_admin(
    request,
    torneo_id
):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id
    )

    return render(
        request,
        "usuarios/ver_torneo_admin.html",
        {
            "torneo": torneo
        }
    )





@login_required
def editar_torneo(request, torneo_id):
    if request.user.rol != "admin":
        return redirect("inicio")

    torneo = get_object_or_404(Torneo, id=torneo_id)

    # Bloquear la edición de torneos que ya comenzaron o finalizaron.
    if (
        torneo.estado in ["en_curso", "finalizado"]
        or torneo.fecha_inicio <= timezone.localdate()
    ):
        messages.error(
            request,
            "No puedes editar un torneo que ya comenzó o ha finalizado."
        )
        return redirect("torneos_admin")

    if request.method == "POST":
        form = TorneoForm(request.POST, instance=torneo)

        if form.is_valid():
            torneo_actualizado = form.save()
            messages.success(
                request,
                f"El torneo '{torneo_actualizado.nombre}' fue actualizado correctamente."
            )
            return redirect("torneos_admin")

        messages.error(
            request,
            "No se pudieron guardar los cambios. Revisa los errores del formulario."
        )
    else:
        form = TorneoForm(instance=torneo)

    return render(
        request,
        "usuarios/editar_torneo.html",
        {
            "form": form,
            "torneo": torneo,
        }
    )





@login_required
def eliminar_torneo(request, torneo_id):

    if request.user.rol != "admin":
        return redirect("inicio")

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id
    )

    # Verificar si existen inscripciones asociadas
    tiene_inscripciones = Inscripcion.objects.filter(
        torneo=torneo
    ).exists()

    # Verificar si existen partidos asociados
    tiene_partidos = Partido.objects.filter(
        torneo=torneo
    ).exists()

    # Verificar si ya se generaron fases de competición
    tiene_fases = FaseTorneo.objects.filter(
    torneo=torneo
    ).exists()
    # Solo se permite eliminar torneos pendientes
    # que no tengan inscripciones ni historial competitivo.
    puede_eliminarse = (
        torneo.estado == "pendiente"
        and not tiene_inscripciones
        and not tiene_partidos
        and not tiene_fases
    )

    if not puede_eliminarse:

        if torneo.estado == "inscripciones_abiertas":
            motivo_bloqueo = (
                "No puedes eliminar este torneo porque "
                "tiene las inscripciones abiertas. "
                "Cierra las inscripciones primero."
            )

        elif tiene_inscripciones:
            motivo_bloqueo = (
                "No puedes eliminar este torneo porque "
                "tiene equipos inscritos. Debes conservar "
                "sus registros de participación."
            )

        elif torneo.estado == "en_curso":
            motivo_bloqueo = (
                "No puedes eliminar un torneo que está "
                "en curso."
            )

        elif torneo.estado == "finalizado":
            motivo_bloqueo = (
                "No puedes eliminar un torneo finalizado "
                "porque debe conservarse su historial."
            )

        elif tiene_partidos or tiene_fases:
            motivo_bloqueo = (
                "No puedes eliminar este torneo porque "
                "ya tiene registros de competición."
            )

        else:
            motivo_bloqueo = (
                "Solo puedes eliminar torneos pendientes "
                "que no tengan inscripciones ni historial."
            )

        if request.method == "POST":
            messages.error(
                request,
                motivo_bloqueo
            )

            return redirect(
                "torneos_admin"
            )

        return render(
            request,
            "usuarios/eliminar_torneo.html",
            {
                "torneo": torneo,
                "puede_eliminarse": False,
                "motivo_bloqueo": motivo_bloqueo,
            }
        )

    if request.method == "POST":

        nombre_torneo = torneo.nombre

        torneo.delete()

        messages.success(
            request,
            (
                f"El torneo '{nombre_torneo}' "
                "fue eliminado correctamente."
            )
        )

        return redirect("torneos_admin")

    return render(
        request,
        "usuarios/eliminar_torneo.html",
        {
            "torneo": torneo,
            "puede_eliminarse": True,
            "motivo_bloqueo": "",
        }
    )



# =========================================================
# CONFIGURACIÓN DE INSCRIPCIONES
# =========================================================

@login_required
def configurar_inscripciones(request):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    if request.method == "POST":

        form = ConfiguracionInscripcionForm(
            request.POST
        )

        if form.is_valid():

            configuracion = form.save()

            messages.success(
                request,
                (
                    "La configuración de inscripciones "
                    f"para el torneo "
                    f"'{configuracion.torneo.nombre}' "
                    "fue creada correctamente."
                )
            )

            return redirect(
                "inscripciones_admin"
            )

    else:

        form = ConfiguracionInscripcionForm()

    return render(
        request,
        "usuarios/configurar_inscripciones.html",
        {
            "form": form
        }
    )


@login_required
def inscripciones_admin(request):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    configuraciones = (
        ConfiguracionInscripcion.objects
        .select_related("torneo")
        .order_by(
            "torneo__fecha_inicio"
        )
    )

    # -------------------------------------------------
    # COMPROBAR SI YA SE REALIZÓ EL SORTEO
    # -------------------------------------------------

    for configuracion in configuraciones:

        configuracion.sorteo_realizado = (
            ConfiguracionCompeticion.objects.filter(
                torneo_id=configuracion.torneo_id,
                sorteo_realizado=True
            ).exists()
        )

    return render(
        request,
        "usuarios/inscripciones_admin.html",
        {
            "configuraciones":
                configuraciones
        }
    )


@login_required
def abrir_inscripciones(
    request,
    configuracion_id
):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    configuracion = get_object_or_404(
        ConfiguracionInscripcion,
        id=configuracion_id
    )

    if request.method == "POST":

        # -------------------------------------------------
        # BLOQUEAR APERTURA SI YA SE REALIZÓ EL SORTEO
        # -------------------------------------------------

        sorteo_realizado = (
            ConfiguracionCompeticion.objects.filter(
                torneo_id=configuracion.torneo_id,
                sorteo_realizado=True
            ).exists()
        )

        if sorteo_realizado:

            messages.error(
                request,
                (
                    "No se pueden abrir las inscripciones "
                    "porque el sorteo de este torneo "
                    "ya fue realizado."
                )
            )

            return redirect(
                "inscripciones_admin"
            )

        configuracion.inscripciones_abiertas = True

        configuracion.save(
            update_fields=[
                "inscripciones_abiertas",
                "actualizado_en"
            ]
        )

        # -------------------------------------------------
        # ACTUALIZAR ESTADO DEL TORNEO
        # -------------------------------------------------

        torneo = configuracion.torneo

        torneo.estado = "inscripciones_abiertas"

        torneo.save(
            update_fields=[
                "estado",
                "actualizado_en"
            ]
        )

        messages.success(
            request,
            (
                "Las inscripciones del torneo "
                f"'{torneo.nombre}' "
                "fueron abiertas correctamente."
            )
        )

    return redirect(
        "inscripciones_admin"
    )


@login_required
def cerrar_inscripciones(
    request,
    configuracion_id
):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    configuracion = get_object_or_404(
        ConfiguracionInscripcion,
        id=configuracion_id
    )

    if request.method == "POST":

        configuracion.inscripciones_abiertas = False

        configuracion.save(
            update_fields=[
                "inscripciones_abiertas",
                "actualizado_en"
            ]
        )

        # -------------------------------------------------
        # ACTUALIZAR ESTADO DEL TORNEO
        # -------------------------------------------------

        torneo = configuracion.torneo

        torneo.estado = "inscripciones_cerradas"

        torneo.save(
            update_fields=[
                "estado",
                "actualizado_en"
            ]
        )

        messages.success(
            request,
            (
                "Las inscripciones del torneo "
                f"'{torneo.nombre}' "
                "fueron cerradas correctamente."
            )
        )

    return redirect(
        "inscripciones_admin"
    )


@login_required
def editar_configuracion_inscripcion(
    request,
    configuracion_id
):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    configuracion = get_object_or_404(
        ConfiguracionInscripcion,
        id=configuracion_id
    )

    if request.method == "POST":

        form = ConfiguracionInscripcionForm(
            request.POST,
            instance=configuracion
        )

        if form.is_valid():

            configuracion_actualizada = form.save()

            messages.success(
                request,
                (
                    "La configuración de inscripciones "
                    f"del torneo "
                    f"'{configuracion_actualizada.torneo.nombre}' "
                    "fue actualizada correctamente."
                )
            )

            return redirect(
                "inscripciones_admin"
            )

    else:

        form = ConfiguracionInscripcionForm(
            instance=configuracion
        )

    return render(
        request,
        "usuarios/editar_configuracion_inscripcion.html",
        {
            "form": form,
            "configuracion": configuracion
        }
    )


@login_required
def eliminar_configuracion_inscripcion(
    request,
    configuracion_id
):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    configuracion = get_object_or_404(
        ConfiguracionInscripcion,
        id=configuracion_id
    )

    if request.method == "POST":

        nombre_torneo = (
            configuracion.torneo.nombre
        )

        configuracion.delete()

        messages.success(
            request,
            (
                "La configuración de inscripciones "
                f"del torneo '{nombre_torneo}' "
                "fue eliminada correctamente."
            )
        )

        return redirect(
            "inscripciones_admin"
        )

    return render(
        request,
        "usuarios/eliminar_configuracion_inscripcion.html",
        {
            "configuracion":
                configuracion
        }
    )

# =========================================================
# CONFIGURACIÓN DE COMPETICIÓN - ADMIN
# =========================================================

@login_required
def configurar_competicion(request):

    if request.user.rol != "admin":
        messages.error(
            request,
            "No tienes permisos para acceder a esta sección."
        )
        return redirect("inicio")

    if request.method == "POST":

        form = ConfiguracionCompeticionForm(
            request.POST
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                (
                    "La configuración de competición "
                    "se guardó correctamente."
                )
            )

            return redirect(
                "configuraciones_competicion"
            )

    else:

        form = ConfiguracionCompeticionForm()

    return render(
        request,
        "usuarios/configurar_competicion.html",
        {
            "form": form
        }
    )

# =========================================================
# LISTADO DE CONFIGURACIONES DE COMPETICIÓN - ADMIN
# =========================================================

@login_required
def configuraciones_competicion(request):

    if request.user.rol != "admin":
        messages.error(
            request,
            "No tienes permisos para acceder a esta sección."
        )
        return redirect("inicio")

    configuraciones = (
        ConfiguracionCompeticion.objects
        .select_related("torneo")
        .order_by("-creado_en")
    )

    return render(
        request,
        "usuarios/configuraciones_competicion.html",
        {
            "configuraciones": configuraciones
        }
    )

# =========================================================
# VER CONFIGURACIÓN DE COMPETICIÓN - ADMIN
# =========================================================

@login_required
def ver_configuracion_competicion(request, configuracion_id):

    if request.user.rol != "admin":
        messages.error(
            request,
            "No tienes permisos para acceder a esta sección."
        )
        return redirect("inicio")

    configuracion = get_object_or_404(
        ConfiguracionCompeticion.objects.select_related(
            "torneo"
        ),
        id=configuracion_id
    )

    return render(
    request,
    "usuarios/ver_configuracion_competicion.html",
    {
        "configuracion": configuracion,
        "inscripciones_abiertas": (
            configuracion.torneo
            .configuracion_inscripcion
            .inscripciones_abiertas
        )
    }
)
# =========================================================
# REALIZAR SORTEO DE EQUIPOS
# =========================================================

@login_required
def realizar_sorteo(request, configuracion_id):

    if request.user.rol != "admin":

        messages.error(
            request,
            "No tienes permisos para realizar el sorteo."
        )

        return redirect(
            "inicio"
        )

    configuracion = get_object_or_404(
        ConfiguracionCompeticion.objects.select_related(
            "torneo"
        ),
        id=configuracion_id
    )

    torneo = configuracion.torneo

    # -----------------------------------------------------
    # SOLO SE PERMITE REALIZAR EL SORTEO UNA VEZ
    # -----------------------------------------------------

    if configuracion.sorteo_realizado:

        messages.error(
            request,
            "El sorteo de este torneo ya fue realizado."
        )

        return redirect(
            "ver_configuracion_competicion",
            configuracion_id=configuracion.id
        )

    # -----------------------------------------------------
    # LAS INSCRIPCIONES DEBEN ESTAR CERRADAS
    # -----------------------------------------------------

    try:

        configuracion_inscripcion = (
            torneo.configuracion_inscripcion
        )

    except ConfiguracionInscripcion.DoesNotExist:

        messages.error(
            request,
            (
                "Este torneo no tiene una configuración "
                "de inscripciones."
            )
        )

        return redirect(
            "ver_configuracion_competicion",
            configuracion_id=configuracion.id
        )

    if configuracion_inscripcion.inscripciones_abiertas:

        messages.error(
            request,
            (
                "No puedes realizar el sorteo mientras "
                "las inscripciones estén abiertas."
            )
        )

        return redirect(
            "ver_configuracion_competicion",
            configuracion_id=configuracion.id
        )

    # -----------------------------------------------------
    # OBTENER EQUIPOS ACEPTADOS
    # -----------------------------------------------------

    inscripciones_aceptadas = (
        Inscripcion.objects
        .filter(
            torneo=torneo,
            estado="aceptada"
        )
        .select_related("equipo")
    )

    equipos = [
        inscripcion.equipo
        for inscripcion in inscripciones_aceptadas
    ]

    # -----------------------------------------------------
    # DEBEN EXISTIR COMO MÍNIMO 4 EQUIPOS
    # -----------------------------------------------------

    if len(equipos) < 4:

        messages.error(
            request,
            (
                "No se puede realizar el sorteo. "
                "Debe haber mínimo 4 equipos aceptados."
            )
        )

        return redirect(
            "ver_configuracion_competicion",
            configuracion_id=configuracion.id
        )

    # -----------------------------------------------------
    # NO PUEDE HABER MÁS GRUPOS QUE EQUIPOS
    # -----------------------------------------------------

    if configuracion.cantidad_grupos > len(equipos):

        messages.error(
            request,
            (
                "No se puede realizar el sorteo porque "
                "la cantidad de grupos es mayor que "
                "la cantidad de equipos aceptados."
            )
        )

        return redirect(
            "ver_configuracion_competicion",
            configuracion_id=configuracion.id
        )

    # -----------------------------------------------------
    # CREAR FASE DE GRUPOS
    # -----------------------------------------------------

    fase_grupos, creada = FaseTorneo.objects.get_or_create(
        torneo=torneo,
        tipo="grupos",
        defaults={
            "nombre": "Fase de grupos",
            "orden": 1,
            "activa": True,
            "creada_automaticamente": True
        }
    )

    # -----------------------------------------------------
    # CREAR LOS GRUPOS
    # -----------------------------------------------------

    grupos = []

    for numero in range(
        1,
        configuracion.cantidad_grupos + 1
    ):

        grupo, creada = Grupo.objects.get_or_create(
            fase=fase_grupos,
            numero=numero,
            defaults={
                "nombre": f"Grupo {numero}"
            }
        )

        grupos.append(grupo)

    # -----------------------------------------------------
    # MEZCLAR EQUIPOS ALEATORIAMENTE
    # -----------------------------------------------------

    import random

    random.shuffle(equipos)

    # -----------------------------------------------------
    # DISTRIBUIR EQUIPOS EQUILIBRADAMENTE
    # -----------------------------------------------------

    for indice, equipo in enumerate(equipos):

        grupo = grupos[
            indice % len(grupos)
        ]

        EquipoGrupo.objects.get_or_create(
            grupo=grupo,
            equipo=equipo
        )

    # -----------------------------------------------------
    # MARCAR EL SORTEO COMO REALIZADO
    # -----------------------------------------------------

    configuracion.sorteo_realizado = True
    configuracion.save(
        update_fields=[
            "sorteo_realizado",
            "actualizado_en"
        ]
    )

    messages.success(
        request,
        (
            "El sorteo se realizó correctamente. "
            "Los equipos fueron distribuidos entre "
            "los grupos."
        )
    )

    return redirect(
        "ver_configuracion_competicion",
        configuracion_id=configuracion.id
    )

@login_required
def ver_grupos_competicion(request, configuracion_id):

    if request.user.rol != "admin":
        messages.error(
            request,
            "No tienes permisos para acceder a esta sección."
        )
        return redirect("inicio")

    configuracion = get_object_or_404(
        ConfiguracionCompeticion.objects.select_related("torneo"),
        id=configuracion_id
    )

    torneo = configuracion.torneo

    try:
        fase_grupos = FaseTorneo.objects.get(
            torneo=torneo,
            tipo="grupos"
        )
    except FaseTorneo.DoesNotExist:
        messages.error(
            request,
            "Todavía no se ha realizado el sorteo."
        )
        return redirect(
            "ver_configuracion_competicion",
            configuracion_id=configuracion.id
        )

    grupos = (
        Grupo.objects
        .filter(fase=fase_grupos)
        .prefetch_related(
            "equipos_grupo__equipo"
        )
        .order_by("numero")
    )

    return render(
        request,
        "usuarios/ver_grupos_competicion.html",
        {
            "configuracion": configuracion,
            "torneo": torneo,
            "fase_grupos": fase_grupos,
            "grupos": grupos,
        }
    )

# =========================================================
# GENERAR PARTIDOS DE LA FASE DE GRUPOS
# =========================================================

@login_required
def generar_partidos(request, configuracion_id):

    if request.user.rol != "admin":
        return redirect("usuario_dashboard")

    configuracion = get_object_or_404(
        ConfiguracionCompeticion.objects.select_related(
            "torneo"
        ),
        id=configuracion_id
    )

    torneo = configuracion.torneo

    # -----------------------------------------------------
    # VALIDAR QUE EL SORTEO YA SE HAYA REALIZADO
    # -----------------------------------------------------

    if not configuracion.sorteo_realizado:

        messages.error(
            request,
            "No se pueden generar partidos antes de realizar el sorteo."
        )

        return redirect(
            "ver_configuracion_competicion",
            configuracion_id=configuracion.id
        )

    # -----------------------------------------------------
    # EVITAR GENERAR PARTIDOS MÁS DE UNA VEZ
    # -----------------------------------------------------

    if configuracion.competicion_generada:

        messages.warning(
            request,
            "Los partidos de esta competición ya fueron generados."
        )

        return redirect(
            "ver_grupos_competicion",
            configuracion_id=configuracion.id
        )

    # -----------------------------------------------------
    # OBTENER LA FASE DE GRUPOS
    # -----------------------------------------------------

    fase_grupos = get_object_or_404(
        FaseTorneo,
        torneo=torneo,
        tipo="grupos"
    )

    grupos = (
        Grupo.objects
        .filter(fase=fase_grupos)
        .prefetch_related(
            "equipos_grupo__equipo"
        )
        .order_by("numero")
    )

    # -----------------------------------------------------
    # GENERAR LOS PARTIDOS
    # -----------------------------------------------------

    numero_partido = (
        Partido.objects
        .filter(torneo=torneo)
        .count()
        + 1
    )

    partidos_creados = 0

    with transaction.atomic():

        for grupo in grupos:

            equipos = [
                equipo_grupo.equipo
                for equipo_grupo
                in grupo.equipos_grupo.all()
            ]

            # ---------------------------------------------
            # CADA EQUIPO JUEGA CONTRA LOS DEMÁS
            # ---------------------------------------------

            for indice in range(len(equipos)):

                equipo_local = equipos[indice]

                for siguiente in range(
                    indice + 1,
                    len(equipos)
                ):

                    equipo_visitante = equipos[siguiente]

                    Partido.objects.create(
                        torneo=torneo,
                        fase=fase_grupos,
                        grupo=grupo,
                        equipo_local=equipo_local,
                        equipo_visitante=equipo_visitante,
                        numero=numero_partido,
                        estado="pendiente"
                    )

                    numero_partido += 1
                    partidos_creados += 1

        # -------------------------------------------------
        # MARCAR COMPETICIÓN COMO GENERADA
        # -------------------------------------------------

        configuracion.competicion_generada = True

        configuracion.save(
            update_fields=[
                "competicion_generada"
            ]
        )

    messages.success(
        request,
        (
            f"Se generaron correctamente "
            f"{partidos_creados} partidos."
        )
    )

    return redirect(
        "ver_grupos_competicion",
        configuracion_id=configuracion.id
    )
# =========================================================
# LISTA DE TORNEOS - MÓDULO PARTIDOS
# =========================================================

@login_required
def partidos_torneos_admin(request):

    if request.user.rol != "admin":

        return redirect(
            "usuario_dashboard"
        )

    torneos = (
        Torneo.objects
        .all()
        .order_by(
            "-fecha_inicio"
        )
    )

    return render(
        request,
        "usuarios/partidos_torneos_admin.html",
        {
            "torneos": torneos,
        }
    )

# =========================================================
# VER PARTIDOS DE LA COMPETICIÓN
# =========================================================


@login_required
def partidos_admin(request, torneo_id):

    if request.user.rol != "admin":
        return redirect("usuario_dashboard")

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id
    )

    # Verificar que el torneo tenga configuración.
    configuracion = (
        ConfiguracionCompeticion.objects
        .filter(torneo=torneo)
        .first()
    )

    if configuracion is None:
        messages.warning(
            request,
            (
                f"El torneo '{torneo.nombre}' todavía no tiene "
                "una configuración de competición. "
                "Debes configurarla antes de consultar los partidos."
            )
        )

        return redirect(
            "configurar_competicion"
        )

    partidos = (
        Partido.objects
        .filter(torneo=torneo)
        .select_related(
            "fase",
            "grupo",
            "equipo_local",
            "equipo_visitante",
            "resultado",
        )
        .order_by("numero")
    )

    return render(
        request,
        "usuarios/partidos_admin.html",
        {
            "torneo": torneo,
            "configuracion": configuracion,
            "partidos": partidos,
        }
    )

# =========================================================
# PROGRAMAR PARTIDO
# =========================================================


@login_required
def programar_partido(request, partido_id):

    if request.user.rol != "admin":
        return redirect("usuario_dashboard")

    partido = get_object_or_404(
        Partido.objects.select_related(
            "torneo",
            "equipo_local",
            "equipo_visitante",
            "grupo",
            "fase",
        ),
        id=partido_id,
    )

    # No permitir modificar partidos jugados o cancelados.
    if partido.estado in ["jugado", "cancelado"]:
        messages.warning(
            request,
            "No puedes programar ni editar un partido "
            "que ya está jugado o cancelado.",
        )
        return redirect(
            "partidos_admin",
            torneo_id=partido.torneo.id,
        )

    if request.method == "POST":

        # Guardar los datos anteriores para detectar cambios.
        estado_anterior = partido.estado
        fecha_anterior = partido.fecha
        hora_anterior = partido.hora

        form = ProgramarPartidoForm(
            request.POST,
            instance=partido,
        )

        if form.is_valid():

            partido = form.save(commit=False)
            partido.estado = "programado"
            partido.save()

            # Detectar programación inicial o reprogramación.
            es_reprogramacion = (
                estado_anterior == "programado"
                and (
                    fecha_anterior != partido.fecha
                    or hora_anterior != partido.hora
                )
            )

            es_programacion_inicial = (
                estado_anterior != "programado"
            )

            # Enviar correo solamente si se programó por primera
            # vez o si cambió la fecha u hora de un partido.
            if es_programacion_inicial or es_reprogramacion:

                responsables = [
                    partido.equipo_local.responsable,
                    partido.equipo_visitante.responsable,
                ]

                destinatarios = list(
                    dict.fromkeys(
                        responsable.correo.strip()
                        for responsable in responsables
                        if responsable.correo
                        and responsable.correo.strip()
                    )
                )

                fecha_texto = (
                    partido.fecha.strftime("%d/%m/%Y")
                    if partido.fecha
                    else "Sin fecha"
                )

                hora_texto = (
                    partido.hora.strftime("%H:%M")
                    if partido.hora
                    else "Sin hora"
                )

                if es_reprogramacion:
                    asunto = (
                        f"ViveSport: cambio de horario - "
                        f"{partido.torneo.nombre}"
                    )

                    introduccion = (
                        "La fecha u hora de tu partido ha sido modificada."
                    )
                else:
                    asunto = (
                        f"ViveSport: partido programado - "
                        f"{partido.torneo.nombre}"
                    )

                    introduccion = (
                        "Tu partido ha sido programado correctamente."
                    )

                mensaje = (
                    "Hola.\n\n"
                    f"{introduccion}\n\n"
                    f"Torneo: {partido.torneo.nombre}\n"
                    f"Partido: {partido.numero}\n"
                    f"Equipo local: {partido.equipo_local.nombre}\n"
                    f"Equipo visitante: "
                    f"{partido.equipo_visitante.nombre}\n"
                    f"Fecha: {fecha_texto}\n"
                    f"Hora: {hora_texto}\n\n"
                    "Ingresa a ViveSport para consultar "
                    "la información de la competición.\n\n"
                    "ViveSport"
                )

                enviar_correo_vivesport(
                    asunto=asunto,
                    mensaje=mensaje,
                    destinatarios=destinatarios,
                )

            if es_reprogramacion:
                mensaje_confirmacion = (
                    f"El partido {partido.numero} fue reprogramado "
                    "correctamente."
                )
            else:
                mensaje_confirmacion = (
                    f"El partido {partido.numero} "
                    "fue guardado correctamente."
                )

            messages.success(
                request,
                mensaje_confirmacion,
            )

            return redirect(
                "partidos_admin",
                torneo_id=partido.torneo.id,
            )

    else:
        form = ProgramarPartidoForm(
            instance=partido,
        )

    return render(
        request,
        "usuarios/programar_partido.html",
        {
            "form": form,
            "partido": partido,
        },
    )

# =========================================================
# RESULTADOS - ADMIN
# =========================================================

@login_required
def resultados_admin(request):

    if request.user.rol != "admin":
        return redirect("inicio")

    torneos = Torneo.objects.order_by("nombre")

    torneo_seleccionado = request.GET.get("torneo", "")

    partidos = (
        Partido.objects
        .filter(
            estado="jugado",
            resultado__isnull=False
        )
        .select_related(
            "torneo",
            "equipo_local",
            "equipo_visitante",
            "grupo",
            "fase",
            "resultado"
        )
        .order_by(
            "-fecha",
            "-hora",
            "-numero"
        )
    )

    # Filtrar resultados por torneo seleccionado.
    if torneo_seleccionado:
        if (
            torneo_seleccionado.isdigit()
            and torneos.filter(
                pk=torneo_seleccionado
            ).exists()
        ):
            partidos = partidos.filter(
                torneo_id=torneo_seleccionado
            )
        else:
            torneo_seleccionado = ""

    return render(
        request,
        "usuarios/resultados_admin.html",
        {
            "partidos": partidos,
            "torneos": torneos,
            "torneo_seleccionado": torneo_seleccionado,
        }
    )
# =========================================================
# DETALLE DE UN RESULTADO - ADMIN
# =========================================================

@login_required
def detalle_resultado_admin(request, partido_id):

    if request.user.rol != "admin":
        return redirect("inicio")

    partido = get_object_or_404(
        Partido.objects.select_related(
            "torneo",
            "equipo_local",
            "equipo_visitante",
            "grupo",
            "fase",
            "resultado",
        ),
        id=partido_id,
        estado="jugado",
        resultado__isnull=False,
    )

    # Jugadores registrados como participantes del encuentro.
    participaciones = (
        ParticipacionPartido.objects
        .filter(partido=partido)
        .select_related("jugador", "equipo")
        .order_by(
            "equipo__nombre",
            "jugador__nombre",
            "jugador__apellido",
        )
    )

    # Los goles solo corresponden a partidos de fútbol.
    goles = (
        Gol.objects
        .filter(partido=partido)
        .select_related("jugador", "equipo")
        .order_by("minuto", "id")
    )

    # Tarjetas registradas para ambos equipos.
    tarjetas = (
        Tarjeta.objects
        .filter(partido=partido)
        .select_related("jugador", "equipo")
        .order_by("minuto", "id")
    )

    return render(
        request,
        "usuarios/detalle_resultado_admin.html",
        {
            "partido": partido,
            "participaciones": participaciones,
            "goles": goles,
            "tarjetas": tarjetas,
            "es_futbol": partido.torneo.deporte == "futbol",
        },
    )
# =========================================================
# REGISTRAR RESULTADO DEL PARTIDO
# =========================================================

@login_required
def registrar_resultado(request, partido_id):

    if request.user.rol != "admin":
        return redirect("inicio")

    partido = get_object_or_404(
        Partido.objects.select_related(
            "torneo",
            "equipo_local",
            "equipo_visitante",
            "grupo",
            "fase"
        ),
        id=partido_id
    )

    if partido.estado != "programado":
        messages.warning(
            request,
            (
                "Solo puedes registrar el resultado "
                "de un partido que esté programado."
            )
        )
        return redirect(
            "partidos_admin",
            torneo_id=partido.torneo.id
        )

    es_futbol = partido.torneo.deporte == "futbol"
    es_deporte_sets = partido.torneo.deporte in [
        "voleibol",
        "tenis_mesa",
    ]
    jugadores_local = (
        IntegranteEquipo.objects
        .filter(equipo=partido.equipo_local)
        .order_by("nombre", "apellido")
    )

    jugadores_visitante = (
        IntegranteEquipo.objects
        .filter(equipo=partido.equipo_visitante)
        .order_by("nombre", "apellido")
    )

        # Datos serializables para el template
    jugadores_local_json = list(
        jugadores_local.values(
            "id",
            "nombre",
            "apellido"
        )
    )

    jugadores_visitante_json = list(
        jugadores_visitante.values(
            "id",
            "nombre",
            "apellido"
        )
    )

    jugadores_local_ids = set(
        jugadores_local.values_list("id", flat=True)
    )

    jugadores_visitante_ids = set(
        jugadores_visitante.values_list("id", flat=True)
    )

    if request.method == "POST":

        # =====================================================
        # PARTICIPACIÓN
        # =====================================================

        jugadores_local_post = request.POST.getlist(
            "jugadores_local"
        )

        jugadores_visitante_post = request.POST.getlist(
            "jugadores_visitante"
        )

        ids_local = set()
        ids_visitante = set()

        errores = []

        for jugador_id in jugadores_local_post:

            try:
                ids_local.add(int(jugador_id))
            except (TypeError, ValueError):
                errores.append(
                    "La selección de jugadores del equipo local no es válida."
                )

        for jugador_id in jugadores_visitante_post:

            try:
                ids_visitante.add(int(jugador_id))
            except (TypeError, ValueError):
                errores.append(
                    "La selección de jugadores del equipo visitante no es válida."
                )

        if not ids_local.issubset(jugadores_local_ids):
            errores.append(
                "Se detectó un jugador inválido en la selección del equipo local."
            )

        if not ids_visitante.issubset(jugadores_visitante_ids):
            errores.append(
                "Se detectó un jugador inválido en la selección del equipo visitante."
            )

        # =====================================================
        # VARIABLES PARA GOLES Y TARJETAS
        # =====================================================

        goles_local_ids = []
        goles_visitante_ids = []

        tarjetas_local = []
        tarjetas_visitante = []

        if es_futbol:

            # =================================================
            # GOLES LOCAL
            # =================================================

            goles_local_post = request.POST.getlist(
                "goles_local"
            )

            for jugador_id in goles_local_post:

                try:
                    jugador_id = int(jugador_id)
                except (TypeError, ValueError):
                    errores.append(
                        "Se detectó un goleador inválido en el equipo local."
                    )
                    continue

                if jugador_id not in ids_local:
                    errores.append(
                        "El goleador del equipo local debe estar seleccionado como participante."
                    )
                    continue

                goles_local_ids.append(jugador_id)

            # =================================================
            # GOLES VISITANTE
            # =================================================

            goles_visitante_post = request.POST.getlist(
                "goles_visitante"
            )

            for jugador_id in goles_visitante_post:

                try:
                    jugador_id = int(jugador_id)
                except (TypeError, ValueError):
                    errores.append(
                        "Se detectó un goleador inválido en el equipo visitante."
                    )
                    continue

                if jugador_id not in ids_visitante:
                    errores.append(
                        "El goleador del equipo visitante debe estar seleccionado como participante."
                    )
                    continue

                goles_visitante_ids.append(jugador_id)

            # =================================================
            # TARJETAS LOCAL
            # =================================================

            tarjetas_local_jugadores = request.POST.getlist(
                "tarjetas_local_jugador"
            )

            tarjetas_local_tipos = request.POST.getlist(
                "tarjetas_local_tipo"
            )

            if len(tarjetas_local_jugadores) != len(
                tarjetas_local_tipos
            ):
                errores.append(
                    "La información de las tarjetas del equipo local no es válida."
                )

            cantidad_tarjetas_local = min(
                len(tarjetas_local_jugadores),
                len(tarjetas_local_tipos)
            )

            for i in range(cantidad_tarjetas_local):

                jugador_id = tarjetas_local_jugadores[i]
                tipo = tarjetas_local_tipos[i]

                try:
                    jugador_id = int(jugador_id)
                except (TypeError, ValueError):
                    errores.append(
                        "Se detectó un jugador inválido en las tarjetas del equipo local."
                    )
                    continue

                if jugador_id not in ids_local:
                    errores.append(
                        "El jugador que recibe una tarjeta del equipo local debe estar seleccionado como participante."
                    )
                    continue

                if tipo not in ["amarilla", "roja"]:
                    errores.append(
                        "El tipo de tarjeta del equipo local no es válido."
                    )
                    continue

                tarjetas_local.append(
                    (jugador_id, tipo)
                )

            # =================================================
            # TARJETAS VISITANTE
            # =================================================

            tarjetas_visitante_jugadores = request.POST.getlist(
                "tarjetas_visitante_jugador"
            )

            tarjetas_visitante_tipos = request.POST.getlist(
                "tarjetas_visitante_tipo"
            )

            if len(tarjetas_visitante_jugadores) != len(
                tarjetas_visitante_tipos
            ):
                errores.append(
                    "La información de las tarjetas del equipo visitante no es válida."
                )

            cantidad_tarjetas_visitante = min(
                len(tarjetas_visitante_jugadores),
                len(tarjetas_visitante_tipos)
            )

            for i in range(cantidad_tarjetas_visitante):

                jugador_id = tarjetas_visitante_jugadores[i]
                tipo = tarjetas_visitante_tipos[i]

                try:
                    jugador_id = int(jugador_id)
                except (TypeError, ValueError):
                    errores.append(
                        "Se detectó un jugador inválido en las tarjetas del equipo visitante."
                    )
                    continue

                if jugador_id not in ids_visitante:
                    errores.append(
                        "El jugador que recibe una tarjeta del equipo visitante debe estar seleccionado como participante."
                    )
                    continue

                if tipo not in ["amarilla", "roja"]:
                    errores.append(
                        "El tipo de tarjeta del equipo visitante no es válido."
                    )
                    continue

                tarjetas_visitante.append(
                    (jugador_id, tipo)
                )

            # =================================================
            # VALIDAR LÍMITE DE TARJETAS
            # =================================================

            tarjetas_por_jugador = {}

            todas_las_tarjetas = (
                tarjetas_local +
                tarjetas_visitante
            )

            for jugador_id, tipo in todas_las_tarjetas:

                clave = (
                    jugador_id,
                    tipo
                )

                tarjetas_por_jugador[clave] = (
                    tarjetas_por_jugador.get(
                        clave,
                        0
                    ) + 1
                )

            for (
                jugador_tipo,
                cantidad
            ) in tarjetas_por_jugador.items():

                jugador_id, tipo = jugador_tipo

                if (
                    tipo == "amarilla"
                    and cantidad > 2
                ):
                    errores.append(
                        "Un jugador no puede recibir más de 2 tarjetas amarillas en un mismo partido."
                    )

                if (
                    tipo == "roja"
                    and cantidad > 1
                ):
                    errores.append(
                        "Un jugador no puede recibir más de 1 tarjeta roja en un mismo partido."
                    )

         # =====================================================
        # PARTICIPANTES SELECCIONADOS EXPLÍCITAMENTE
        # =====================================================

        participantes_locales = set(ids_local)

        participantes_visitantes = set(ids_visitante)

        # =====================================================
        # DEBE EXISTIR AL MENOS UN PARTICIPANTE POR EQUIPO
        # =====================================================
        if not participantes_locales:

            errores.append(
                (
                    "Debes seleccionar al menos un jugador "
                    "del equipo local que haya participado "
                    "en el partido."
                )
            )

        if not participantes_visitantes:

            errores.append(
                (
                    "Debes seleccionar al menos un jugador "
                    "del equipo visitante que haya participado "
                    "en el partido."
                )
            )

        # =====================================================
        # MARCADOR
        # =====================================================

        
        # =====================================================
        # MARCADOR Y VALIDACIÓN DE SETS
        # =====================================================

        sets_programados_post = None
        sets_resultados_post = []
        sets_local_ganados = 0
        sets_visitante_ganados = 0

        if es_futbol:

            marcador_local = len(goles_local_ids)
            marcador_visitante = len(goles_visitante_ids)

            datos_resultado = request.POST.copy()
            datos_resultado["marcador_local"] = str(marcador_local)
            datos_resultado["marcador_visitante"] = str(
                marcador_visitante
            )

            form = ResultadoPartidoForm(datos_resultado)

        elif es_deporte_sets:

            # Formato del partido: mejor de 3 o mejor de 5.
            try:
                sets_programados_post = int(
                    request.POST.get("sets_programados", "")
                )
            except (TypeError, ValueError):
                sets_programados_post = None

            if sets_programados_post not in (3, 5):
                errores.append(
                    "Selecciona un formato válido: mejor de 3 o mejor de 5."
                )

            # Los puntos se reciben en campos numerados:
            # puntos_local_1, puntos_visitante_1, etc.
            if sets_programados_post in (3, 5):

                sets_necesarios = sets_programados_post // 2 + 1
                partido_terminado = False

                for numero in range(1, sets_programados_post + 1):

                    puntos_local_raw = request.POST.get(
                        f"puntos_local_{numero}", ""
                    ).strip()

                    puntos_visitante_raw = request.POST.get(
                        f"puntos_visitante_{numero}", ""
                    ).strip()

                    # No se exigen sets posteriores a la victoria.
                    if partido_terminado:
                        if puntos_local_raw or puntos_visitante_raw:
                            errores.append(
                                "No puedes registrar sets posteriores "
                                "a la victoria de un equipo."
                            )
                        continue

                    # Un set sin puntos en ambos campos significa
                    # que no fue diligenciado.
                    if not puntos_local_raw and not puntos_visitante_raw:
                        errores.append(
                            f"Debes registrar el set {numero}; "
                            "el partido aún no tiene un ganador."
                        )
                        break

                    if not puntos_local_raw or not puntos_visitante_raw:
                        errores.append(
                            f"Debes registrar los puntos de ambos equipos "
                            f"en el set {numero}."
                        )
                        break

                    try:
                        puntos_local = int(puntos_local_raw)
                        puntos_visitante = int(puntos_visitante_raw)
                    except (TypeError, ValueError):
                        errores.append(
                            f"Los puntos del set {numero} deben ser "
                            "números enteros."
                        )
                        break

                    if puntos_local < 0 or puntos_visitante < 0:
                        errores.append(
                            f"Los puntos del set {numero} no pueden "
                            "ser negativos."
                        )
                        break

                    if puntos_local == puntos_visitante:
                        errores.append(
                            f"El set {numero} no puede terminar empatado."
                        )
                        break

                    # Objetivo de puntos por deporte.
                    if partido.torneo.deporte == "voleibol":
                        objetivo = (
                            15
                            if numero == sets_programados_post
                            else 25
                        )
                    else:
                        objetivo = 11

                    ganador_puntos = max(
                        puntos_local,
                        puntos_visitante
                    )
                    perdedor_puntos = min(
                        puntos_local,
                        puntos_visitante
                    )

                    # El set termina al alcanzar el objetivo
                    # con diferencia mínima de dos puntos.
                    set_valido = (
                        ganador_puntos == objetivo
                        and ganador_puntos - perdedor_puntos >= 2
                    ) or (
                        ganador_puntos > objetivo
                        and perdedor_puntos >= objetivo -1
                        and ganador_puntos - perdedor_puntos == 2
                    )

                    if not set_valido:
                        errores.append(
                            f"El marcador {puntos_local}-{puntos_visitante} "
                            f"del set {numero} no es válido. "
                            f"El objetivo es {objetivo} puntos, "
                            "con una diferencia mínima de dos."
                        )
                        break

                    sets_resultados_post.append({
                        "numero": numero,
                        "puntos_local": puntos_local,
                        "puntos_visitante": puntos_visitante,
                    })

                    if puntos_local > puntos_visitante:
                        sets_local_ganados += 1
                    else:
                        sets_visitante_ganados += 1

                    if (
                        sets_local_ganados >= sets_necesarios
                        or sets_visitante_ganados >= sets_necesarios
                    ):
                        partido_terminado = True

                if not partido_terminado and not any(
                    "Debes registrar" in error
                    or "posteriores a la victoria" in error
                    or "set " in error.lower()
                    for error in errores
                ):
                    errores.append(
                        "Los sets registrados no son suficientes "
                        "para determinar un ganador."
                    )

            datos_resultado = request.POST.copy()
            datos_resultado["marcador_local"] = str(
                sets_local_ganados
            )
            datos_resultado["marcador_visitante"] = str(
                sets_visitante_ganados
            )

            form = ResultadoPartidoForm(datos_resultado)

        else:

            form = ResultadoPartidoForm(request.POST)

        form_valid = form.is_valid()


        # =====================================================
        # AGREGAR ERRORES PERSONALIZADOS AL FORMULARIO
        # =====================================================

        for error in errores:

            form.add_error(
                None,
                error
            )

        # =====================================================
        # GUARDAR
        # =====================================================

        if form_valid and not form.errors:

            with transaction.atomic():

                
                resultado = form.save(
                    commit=False
                )

                resultado.partido = partido

                if es_deporte_sets:
                    resultado.sets_programados = (
                        sets_programados_post
                    )

                resultado.save()

                # =============================================
                # NOTIFICAR RESULTADO A LOS RESPONSABLES
                # =============================================

                destinatarios_resultado = list(
                    dict.fromkeys(
                        correo.strip()
                        for correo in [
                            partido.equipo_local.responsable.correo,
                            partido.equipo_visitante.responsable.correo,
                        ]
                        if correo and correo.strip()
                    )
                )

                if destinatarios_resultado:

                    asunto_resultado = (
                        f"ViveSport: resultado registrado - "
                        f"{partido.torneo.nombre}"
                    )

                    mensaje_resultado = (
                        "Hola.\n\n"
                        "Se ha registrado el resultado final de tu partido.\n\n"
                        f"Torneo: {partido.torneo.nombre}\n"
                        f"Partido: {partido.numero}\n"
                        f"Equipo local: {partido.equipo_local.nombre}\n"
                        f"Equipo visitante: "
                        f"{partido.equipo_visitante.nombre}\n"
                        f"Marcador final: "
                        f"{resultado.marcador_local} - "
                        f"{resultado.marcador_visitante}\n\n"
                        "Ingresa a ViveSport para consultar "
                        "los detalles del partido.\n\n"
                        "ViveSport"
                    )

                    enviar_correo_vivesport(
                        asunto=asunto_resultado,
                        mensaje=mensaje_resultado,
                        destinatarios=destinatarios_resultado,
                    )

                # =============================================
                # GUARDAR DETALLE DE LOS SETS
                # =============================================

                if es_deporte_sets:

                    SetResultado.objects.bulk_create([
                        SetResultado(
                            resultado=resultado,
                            numero=set_data["numero"],
                            puntos_local=set_data["puntos_local"],
                            puntos_visitante=set_data[
                                "puntos_visitante"
                            ],
                        )
                        for set_data in sets_resultados_post
                    ])


                # =============================================
                # GOLES
                # =============================================

                if es_futbol:

                    for jugador_id in goles_local_ids:

                        jugador = jugadores_local.get(
                            id=jugador_id
                        )

                        gol = Gol(
                            partido=partido,
                            equipo=partido.equipo_local,
                            jugador=jugador,
                            minuto=None
                        )

                        gol.full_clean()

                        gol.save()

                    for jugador_id in goles_visitante_ids:

                        jugador = jugadores_visitante.get(
                            id=jugador_id
                        )

                        gol = Gol(
                            partido=partido,
                            equipo=partido.equipo_visitante,
                            jugador=jugador,
                            minuto=None
                        )

                        gol.full_clean()

                        gol.save()

                    # =========================================
                    # TARJETAS LOCAL
                    # =========================================

                    for jugador_id, tipo in tarjetas_local:

                        jugador = jugadores_local.get(
                            id=jugador_id
                        )

                        tarjeta = Tarjeta(
                            partido=partido,
                            equipo=partido.equipo_local,
                            jugador=jugador,
                            tipo=tipo,
                            minuto=None
                        )

                        tarjeta.full_clean()

                        tarjeta.save()

                    # =========================================
                    # TARJETAS VISITANTE
                    # =========================================

                    for jugador_id, tipo in tarjetas_visitante:

                        jugador = jugadores_visitante.get(
                            id=jugador_id
                        )

                        tarjeta = Tarjeta(
                            partido=partido,
                            equipo=partido.equipo_visitante,
                            jugador=jugador,
                            tipo=tipo,
                            minuto=None
                        )

                        tarjeta.full_clean()

                        tarjeta.save()

                # =============================================
                # PARTICIPANTES LOCAL
                # =============================================

                jugadores_local_participantes = (
                    jugadores_local.filter(
                        id__in=participantes_locales
                    )
                )

                for jugador in jugadores_local_participantes:

                    participacion = ParticipacionPartido(
                        partido=partido,
                        equipo=partido.equipo_local,
                        jugador=jugador
                    )

                    participacion.full_clean()

                    participacion.save()

                # =============================================
                # PARTICIPANTES VISITANTE
                # =============================================

                jugadores_visitante_participantes = (
                    jugadores_visitante.filter(
                        id__in=participantes_visitantes
                    )
                )

                for jugador in jugadores_visitante_participantes:

                    participacion = ParticipacionPartido(
                        partido=partido,
                        equipo=partido.equipo_visitante,
                        jugador=jugador
                    )

                    participacion.full_clean()

                    participacion.save()

                # =============================================
                # PARTIDO JUGADO
                # =============================================

                partido.estado = "jugado"

                partido.save(
                    update_fields=[
                        "estado",
                        "actualizado_en"
                    ]
                )

                # Actualizar el estado del torneo
                # cuando se registra un resultado válido.
                torneo = partido.torneo

                if torneo.estado != "finalizado":
                    torneo.estado = "en_curso"
                    torneo.save(
                        update_fields=[
                            "estado",
                            "actualizado_en"
                        ]
                    )
                # =============================================
                # PROGRESIÓN AUTOMÁTICA DE LA COMPETICIÓN
                # =============================================

                fase_generada = procesar_progresion_torneo(
                    torneo
                )

                if fase_generada:
                    nombres_fases_correo = {
                        "cuartos": "Cuartos de final",
                        "semifinal": "Semifinales",
                        "final": "Final",
                    }

                    nombre_fase_correo = (
                        nombres_fases_correo.get(
                            fase_generada,
                            fase_generada,
                        )
                    )

                    destinatarios = list(
                        Usuario.objects.filter(
                            rol="admin",
                            is_active=True,
                        )
                        .exclude(correo="")
                        .values_list("correo", flat=True)
                        .distinct()
                    )

                    if destinatarios:
                        asunto = (
                            f"ViveSport: nueva fase en {torneo.nombre}"
                        )

                        mensaje = (
                            f"Hola, administrador.\n\n"
                            f"Se ha generado automáticamente la fase "
                            f"{nombre_fase_correo} del torneo "
                            f"{torneo.nombre}.\n\n"
                            f"Los partidos de esta fase están pendientes "
                            f"de programación. Puedes consultarlos en el "
                            f"módulo administrativo de partidos.\n\n"
                            f"ViveSport"
                        )

                        transaction.on_commit(
                            lambda asunto=asunto,
                            mensaje=mensaje,
                            destinatarios=destinatarios: send_mail(
                                asunto,
                                mensaje,
                                None,
                                destinatarios,
                                fail_silently=True,
                            )
                        )


                # =============================================
                # FINALIZAR TORNEO Y NOTIFICAR CAMPEÓN
                # =============================================

                fase_final = FaseTorneo.objects.filter(
                    torneo=torneo,
                    tipo="final",
                ).first()

                if (
                    fase_final
                    and torneo.estado != "finalizado"
                ):
                    partidos_final = list(
                        Partido.objects.filter(
                            fase=fase_final,
                        ).select_related(
                            "equipo_local__responsable",
                            "equipo_visitante__responsable",
                            "resultado",
                        )
                    )

                    final_completa = bool(partidos_final)

                    for partido_final in partidos_final:
                        if (
                            partido_final.estado != "jugado"
                            or not hasattr(partido_final, "resultado")
                            or (
                                partido_final.resultado.marcador_local
                                == partido_final.resultado.marcador_visitante
                            )
                        ):
                            final_completa = False
                            break

                    if final_completa and len(partidos_final) == 1:
                        partido_final = partidos_final[0]
                        resultado_final = partido_final.resultado

                        if (
                            resultado_final.marcador_local
                            > resultado_final.marcador_visitante
                        ):
                            campeon = partido_final.equipo_local
                            subcampeon = partido_final.equipo_visitante
                        else:
                            campeon = partido_final.equipo_visitante
                            subcampeon = partido_final.equipo_local

                        torneo.estado = "finalizado"
                        torneo.save(
                            update_fields=[
                                "estado",
                                "actualizado_en",
                            ]
                        )

                        responsables = list(
                            dict.fromkeys(
                                correo.strip()
                                for correo in [
                                    campeon.responsable.correo,
                                    subcampeon.responsable.correo,
                                ]
                                if correo and correo.strip()
                            )
                        )

                        if responsables:
                            asunto_campeon = (
                                f"ViveSport: torneo finalizado - "
                                f"{torneo.nombre}"
                            )

                            mensaje_campeon = (
                                f"Hola.\n\n"
                                f"El torneo {torneo.nombre} ha finalizado.\n\n"
                                f"¡Felicitaciones al equipo campeón: "
                                f"{campeon.nombre}!\n\n"
                                f"Subcampeón: {subcampeon.nombre}\n"
                                f"Resultado de la final: "
                                f"{resultado_final.marcador_local} - "
                                f"{resultado_final.marcador_visitante}\n\n"
                                f"Gracias por participar en ViveSport.\n\n"
                                f"ViveSport"
                            )

                            transaction.on_commit(
                                lambda asunto=asunto_campeon,
                                mensaje=mensaje_campeon,
                                destinatarios=responsables: (
                                    enviar_correo_vivesport(
                                        asunto=asunto,
                                        mensaje=mensaje,
                                        destinatarios=destinatarios,
                                    )
                                )
                            )

                        messages.success(
                            request,
                            (
                                f"¡Torneo finalizado! El equipo campeón "
                                f"es {campeon.nombre}."
                            )
                        )


                messages.success(
                    request,
                    (
                        f"El resultado del partido "
                        f"{partido.numero} fue registrado correctamente."
                    )
                )

                if fase_generada:
                    nombres_fases = {
                        "cuartos": "cuartos de final",
                        "semifinal": "semifinales",
                        "final": "la final",
                    }

                    messages.success(
                        request,
                        (
                            "Se generaron automáticamente los partidos "
                            f"de {nombres_fases.get(fase_generada, fase_generada)}. "
                            "Ahora puedes programarlos desde el módulo "
                            "de programación de partidos."
                        )
                    )

                return redirect("resultados_admin")

        # =====================================================
        # DATOS PARA MANTENER EL FORMULARIO
        # =====================================================

        goles_local_iniciales = request.POST.getlist(
            "goles_local"
        ) if es_futbol else []

        goles_visitante_iniciales = request.POST.getlist(
            "goles_visitante"
        ) if es_futbol else []

        tarjetas_local_jugadores_iniciales = (
            request.POST.getlist(
                "tarjetas_local_jugador"
            )
            if es_futbol
            else []
        )

        tarjetas_local_tipos_iniciales = (
            request.POST.getlist(
                "tarjetas_local_tipo"
            )
            if es_futbol
            else []
        )

        tarjetas_visitante_jugadores_iniciales = (
            request.POST.getlist(
                "tarjetas_visitante_jugador"
            )
            if es_futbol
            else []
        )

        tarjetas_visitante_tipos_iniciales = (
            request.POST.getlist(
                "tarjetas_visitante_tipo"
            )
            if es_futbol
            else []
        )

        tarjetas_local_iniciales = list(
            zip(
                tarjetas_local_jugadores_iniciales,
                tarjetas_local_tipos_iniciales
            )
        )

        tarjetas_visitante_iniciales = list(
            zip(
                tarjetas_visitante_jugadores_iniciales,
                tarjetas_visitante_tipos_iniciales
            )
        )

    else:

        form = ResultadoPartidoForm()

        goles_local_iniciales = []
        goles_visitante_iniciales = []

        tarjetas_local_iniciales = []
        tarjetas_visitante_iniciales = []

        participantes_locales = set()
        participantes_visitantes = set()

    return render(
        request,
        "usuarios/registrar_resultado.html",
        {
            "form": form,
            "partido": partido,
            "es_futbol": es_futbol,
                        "es_deporte_sets": es_deporte_sets,

            "sets_programados_iniciales": (
                request.POST.get("sets_programados", "")
                if request.method == "POST"
                else ""
            ),

            
            "sets_iniciales": [
                {
                    "numero": numero,
                    "puntos_local": (
                        request.POST.get(
                            f"puntos_local_{numero}", ""
                        )
                        if request.method == "POST"
                        else ""
                    ),
                    "puntos_visitante": (
                        request.POST.get(
                            f"puntos_visitante_{numero}", ""
                        )
                        if request.method == "POST"
                        else ""
                    ),
                }
                for numero in range(1, 6)
            ] if es_deporte_sets else [],

            "jugadores_local": jugadores_local_json,
            "jugadores_visitante": jugadores_visitante_json,

            "goles_local_iniciales":
                goles_local_iniciales,

            "goles_visitante_iniciales":
                goles_visitante_iniciales,

            "tarjetas_local_iniciales":
                tarjetas_local_iniciales,

            "tarjetas_visitante_iniciales":
                tarjetas_visitante_iniciales,

            "participantes_locales":
                participantes_locales,

            "participantes_visitantes":
                participantes_visitantes,
        }
    )
    
# =========================================================
# EDITAR CONFIGURACIÓN DE COMPETICIÓN - ADMIN
# =========================================================
@login_required
def editar_configuracion_competicion(
    request,
    configuracion_id
):

    if request.user.rol != "admin":
        messages.error(
            request,
            "No tienes permisos para acceder a esta sección."
        )
        return redirect("inicio")

    configuracion = get_object_or_404(
        ConfiguracionCompeticion.objects.select_related(
            "torneo"
        ),
        id=configuracion_id
    )

    # -----------------------------------------------------
    # BLOQUEAR EDICIÓN SI EL SORTEO YA FUE REALIZADO
    # -----------------------------------------------------
    if configuracion.sorteo_realizado:

        messages.error(
            request,
            (
                "No puedes editar esta configuración "
                "porque el sorteo ya fue realizado."
            )
        )

        return redirect(
            "ver_configuracion_competicion",
            configuracion_id=configuracion.id
        )

    # -----------------------------------------------------
    # BLOQUEAR EDICIÓN SI LA COMPETICIÓN YA FUE GENERADA
    # -----------------------------------------------------
    if configuracion.competicion_generada:

        messages.error(
            request,
            (
                "No puedes editar esta configuración "
                "porque la competición ya fue generada."
            )
        )

        return redirect(
            "ver_configuracion_competicion",
            configuracion_id=configuracion.id
        )

    # -----------------------------------------------------
    # PROCESAR FORMULARIO
    # -----------------------------------------------------
    if request.method == "POST":

        form = EditarConfiguracionCompeticionForm(
            request.POST,
            instance=configuracion
        )

        if form.is_valid():

            configuracion = form.save()

            messages.success(
                request,
                (
                    "La configuración de competición "
                    "se actualizó correctamente."
                )
            )

            return redirect(
                "configuraciones_competicion"
            )

    else:

        form = EditarConfiguracionCompeticionForm(
            instance=configuracion
        )

    return render(
        request,
        "usuarios/editar_configuracion_competicion.html",
        {
            "form": form,
            "configuracion": configuracion
        }
    )
# =========================================================
# INSCRIPCIONES DE EQUIPOS - ADMIN
# =========================================================

@login_required
def inscripciones_equipos_admin(request):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    inscripciones = (
        Inscripcion.objects
        .select_related(
            "torneo",
            "equipo",
            "responsable"
        )
        .prefetch_related(
            "equipo__integrantes"
        )
        .order_by(
            "-fecha_inscripcion"
        )
    )

    # -----------------------------------------------------
    # ACTUALIZAR BLOQUEO AUTOMÁTICO
    # -----------------------------------------------------

    for inscripcion in inscripciones:

        inscripcion.actualizar_bloqueo_automatico()

    return render(
        request,
        "usuarios/inscripciones_equipos_admin.html",
        {
            "inscripciones":
                inscripciones
        }
    )


# =========================================================
# ACEPTAR INSCRIPCIÓN
# =========================================================


@login_required
def aceptar_inscripcion(
    request,
    inscripcion_id
):

    if request.user.rol != "admin":
        return redirect("inicio")

    inscripcion = get_object_or_404(
        Inscripcion,
        id=inscripcion_id
    )

    if request.method != "POST":
        return redirect(
            "inscripciones_equipos_admin"
        )

    if inscripcion.estado != "pendiente":

        messages.warning(
            request,
            (
                "Esta inscripción ya fue "
                "procesada y no puede "
                "aceptarse nuevamente."
            )
        )

        return redirect(
            "inscripciones_equipos_admin"
        )

    # Aceptar la inscripción sin esperar
    # a que termine el período de edición.
    inscripcion.estado = "aceptada"

    inscripcion.save(
        update_fields=[
            "estado",
            "actualizado_en"
        ]
    )

    enviar_correo_vivesport(
        asunto=(
            f"ViveSport: inscripción aceptada - "
            f"{inscripcion.torneo.nombre}"
        ),
        mensaje=(
            f"Hola {inscripcion.responsable.nombre}.\n\n"
            f"La inscripción de tu equipo "
            f"'{inscripcion.equipo.nombre}' "
            f"ha sido aceptada en el torneo "
            f"'{inscripcion.torneo.nombre}'.\n\n"
            "Puedes ingresar a ViveSport para consultar "
            "la información del torneo y sus próximos partidos.\n\n"
            "ViveSport"
        ),
        destinatarios=[
            inscripcion.responsable.correo
        ],
    )


    messages.success(
        request,
        (
            "La inscripción del equipo "
            f"'{inscripcion.equipo.nombre}' "
            "fue aceptada correctamente."
        )
    )

    return redirect(
        "inscripciones_equipos_admin"
    )



# =========================================================
# RECHAZAR INSCRIPCIÓN
# =========================================================

@login_required
def rechazar_inscripcion(request, inscripcion_id):

    if request.user.rol != "admin":
        return redirect("inicio")

    if request.method != "POST":
        return redirect("inscripciones_equipos_admin")

    inscripcion = get_object_or_404(
        Inscripcion,
        id=inscripcion_id
    )

    if inscripcion.estado != "pendiente":
        messages.warning(
            request,
            "Esta inscripción ya fue procesada y no puede rechazarse nuevamente."
        )
        return redirect("inscripciones_equipos_admin")

    # Rechazar la inscripción pendiente.
    inscripcion.estado = "rechazada"
    inscripcion.save(
        update_fields=[
            "estado",
            "actualizado_en"
        ]
    )

    # Notificar al responsable del equipo por correo.
    enviar_correo_vivesport(
        asunto=(
            f"ViveSport: inscripción rechazada - "
            f"{inscripcion.torneo.nombre}"
        ),
        mensaje=(
            f"Hola {inscripcion.responsable.nombre}.\n\n"
            f"La inscripción de tu equipo "
            f"'{inscripcion.equipo.nombre}' "
            f"ha sido rechazada en el torneo "
            f"'{inscripcion.torneo.nombre}'.\n\n"
            "Puedes ingresar a ViveSport para consultar "
            "la información de la inscripción.\n\n"
            "ViveSport"
        ),
        destinatarios=[
            inscripcion.responsable.correo
        ],
    )

    messages.success(
        request,
        (
            f"La inscripción del equipo "
            f"'{inscripcion.equipo.nombre}' "
            "fue rechazada correctamente."
        )
    )

    return redirect("inscripciones_equipos_admin")

# =========================================================
# EQUIPOS ACEPTADOS - ADMIN
# =========================================================

@login_required
def equipos_admin(request):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    torneos = (
        Torneo.objects
        .all()
        .order_by(
            "fecha_inicio"
        )
    )

    # -----------------------------------------------------
    # Cantidad de equipos aceptados por torneo
    # -----------------------------------------------------

    for torneo in torneos:

        torneo.equipos_aceptados = (
            Inscripcion.objects
            .filter(
                torneo=torneo,
                estado="aceptada"
            )
            .count()
        )

    return render(
        request,
        "usuarios/equipos_admin.html",
        {
            "torneos": torneos
        }
    )


# =========================================================
# EQUIPOS ACEPTADOS DE UN TORNEO - ADMIN
# =========================================================

@login_required
def equipos_torneo_admin(
    request,
    torneo_id
):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id
    )

    inscripciones = (
        Inscripcion.objects
        .filter(
            torneo=torneo,
            estado="aceptada"
        )
        .select_related(
            "equipo",
            "responsable"
        )
        .prefetch_related(
            "equipo__integrantes"
        )
        .order_by(
            "equipo__nombre"
        )
    )

    return render(
        request,
        "usuarios/equipos_torneo_admin.html",
        {
            "torneo": torneo,
            "inscripciones": inscripciones,
        }
    )
# =========================================================
# VER EQUIPO - ADMINISTRADOR
# =========================================================

@login_required
def ver_equipo_admin(request, inscripcion_id):

    if request.user.rol != "admin":
        return redirect("inicio")

    inscripcion = get_object_or_404(
        Inscripcion.objects
        .select_related(
            "torneo",
            "equipo",
            "responsable"
        )
        .prefetch_related(
            "equipo__integrantes"
        ),
        id=inscripcion_id,
        estado="aceptada"
    )

    equipo = inscripcion.equipo

    integrantes = equipo.integrantes.all()

    return render(
        request,
        "usuarios/ver_equipo_admin.html",
        {
            "inscripcion": inscripcion,
            "equipo": equipo,
            "integrantes": integrantes,
        }
    )
# =========================================================
# TORNEOS DISPONIBLES
# =========================================================

@login_required
def torneos_disponibles(request):

    if request.user.rol == "admin":

        return redirect(
            "admin_dashboard"
        )

    torneos = (
        Torneo.objects
        .filter(
            configuracion_inscripcion__inscripciones_abiertas=True
        )
        .select_related(
            "configuracion_inscripcion"
        )
        .order_by(
            "fecha_inicio"
        )
    )

    return render(
        request,
        "usuarios/torneos_disponibles.html",
        {
            "torneos": torneos
        }
    )


# =========================================================
# CREAR EQUIPO
# =========================================================

@login_required
def crear_equipo(
    request,
    torneo_id
):

    if request.user.rol == "admin":

        return redirect(
            "admin_dashboard"
        )

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id
    )

    configuracion = get_object_or_404(
        ConfiguracionInscripcion,
        torneo=torneo
    )

    if not configuracion.inscripciones_abiertas:

        messages.error(
            request,
            (
                "Las inscripciones para este "
                "torneo están cerradas."
            )
        )

        return redirect(
            "torneos_disponibles"
        )

    inscripcion_existente = (
        Inscripcion.objects
        .filter(
            torneo=torneo,
            responsable=request.user
        )
        .first()
    )

    if inscripcion_existente:

        if (
            inscripcion_existente.estado
            == "pendiente"
        ):

            messages.info(
                request,
                (
                    "Ya tienes una inscripción "
                    f"pendiente para el torneo "
                    f"'{torneo.nombre}'."
                )
            )

        elif (
            inscripcion_existente.estado
            == "aceptada"
        ):

            messages.info(
                request,
                (
                    "Ya tienes una inscripción "
                    f"aceptada para el torneo "
                    f"'{torneo.nombre}'."
                )
            )

        elif (
            inscripcion_existente.estado
            == "rechazada"
        ):

            messages.info(
                request,
                (
                    "Ya existe una inscripción "
                    f"registrada para el torneo "
                    f"'{torneo.nombre}' y fue "
                    "rechazada por el administrador."
                )
            )

        return redirect(
            "torneos_disponibles"
        )

    control = (
        ControlInscripcion.objects
        .filter(
            usuario=request.user,
            torneo=torneo
        )
        .first()
    )

    if control and not control.puede_eliminar():

        messages.error(
            request,
            (
                "Ya utilizaste las 2 oportunidades "
                "permitidas para volver a realizar "
                f"la inscripción al torneo "
                f"'{torneo.nombre}'."
            )
        )

        return redirect(
            "torneos_disponibles"
        )

    if request.method == "POST":

        form = EquipoForm(
            request.POST
        )

        if form.is_valid():

            equipo = form.save(
                commit=False
            )

            equipo.responsable = (
                request.user
            )

            equipo.save()

            request.session[
                "equipo_id"
            ] = equipo.id

            request.session[
                "torneo_id"
            ] = torneo.id

            return redirect(
                "agregar_integrantes",
                equipo_id=equipo.id,
                torneo_id=torneo.id
            )

    else:

        form = EquipoForm()

    return render(
        request,
        "usuarios/crear_equipo.html",
        {
            "form": form,
            "torneo": torneo,
            "configuracion":
                configuracion,
        }
    )


# =========================================================
# AGREGAR INTEGRANTES
# =========================================================

@login_required
def agregar_integrantes(
    request,
    torneo_id,
    equipo_id
):

    if request.user.rol == "admin":

        return redirect(
            "admin_dashboard"
        )

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id
    )

    equipo = get_object_or_404(
        Equipo,
        id=equipo_id,
        responsable=request.user
    )

    configuracion = get_object_or_404(
        ConfiguracionInscripcion,
        torneo=torneo
    )

    if not configuracion.inscripciones_abiertas:

        messages.error(
            request,
            (
                "Las inscripciones para este "
                "torneo están cerradas."
            )
        )

        return redirect(
            "torneos_disponibles"
        )

    if Inscripcion.objects.filter(
        torneo=torneo,
        equipo=equipo
    ).exists():

        messages.warning(
            request,
            (
                "Este equipo ya tiene una "
                "inscripción registrada "
                "para este torneo."
            )
        )

        return redirect(
            "torneos_disponibles"
        )

    integrantes = (
        equipo.integrantes
        .all()
        .order_by(
            "nombre",
            "apellido"
        )
    )

    cantidad_integrantes = (
        integrantes.count()
    )

    maximo = (
        configuracion.maximo_integrantes
    )

    if cantidad_integrantes >= maximo:

        messages.info(
            request,
            (
                "El equipo ya alcanzó el "
                "máximo de integrantes permitido."
            )
        )

        return redirect(
            "finalizar_inscripcion",
            torneo_id=torneo.id,
            equipo_id=equipo.id
        )

    if request.method == "POST":

        form = IntegranteEquipoForm(
            request.POST,
            equipo=equipo
        )

        if form.is_valid():

            integrante = form.save(
                commit=False
            )

            integrante.equipo = equipo

            integrante.save()

            messages.success(
                request,
                (
                    f"El integrante "
                    f"{integrante.nombre} "
                    f"{integrante.apellido} "
                    "fue agregado correctamente."
                )
            )

            return redirect(
                "agregar_integrantes",
                torneo_id=torneo.id,
                equipo_id=equipo.id
            )

    else:

        form = IntegranteEquipoForm(
            equipo=equipo
        )

    return render(
        request,
        "usuarios/agregar_integrantes.html",
        {
            "form": form,
            "torneo": torneo,
            "equipo": equipo,
            "configuracion":
                configuracion,
            "integrantes":
                integrantes,
            "cantidad_integrantes":
                cantidad_integrantes,
        }
    )


# =========================================================
# ELIMINAR INTEGRANTE
# =========================================================

@login_required
def eliminar_integrante(
    request,
    torneo_id,
    equipo_id,
    integrante_id
):

    if request.user.rol == "admin":

        return redirect(
            "admin_dashboard"
        )

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id
    )

    equipo = get_object_or_404(
        Equipo,
        id=equipo_id,
        responsable=request.user
    )

    configuracion = get_object_or_404(
        ConfiguracionInscripcion,
        torneo=torneo
    )

    if not configuracion.inscripciones_abiertas:

        messages.error(
            request,
            (
                "Las inscripciones para este "
                "torneo están cerradas."
            )
        )

        return redirect(
            "torneos_disponibles"
        )

    if Inscripcion.objects.filter(
        torneo=torneo,
        equipo=equipo
    ).exists():

        messages.warning(
            request,
            (
                "Este equipo ya tiene una "
                "inscripción registrada y "
                "no puede ser modificado."
            )
        )

        return redirect(
            "torneos_disponibles"
        )

    if request.method != "POST":

        messages.error(
            request,
            "La solicitud no es válida."
        )

        return redirect(
            "agregar_integrantes",
            torneo_id=torneo.id,
            equipo_id=equipo.id
        )

    integrante = get_object_or_404(
        IntegranteEquipo,
        id=integrante_id,
        equipo=equipo
    )

    nombre_integrante = (
        f"{integrante.nombre} "
        f"{integrante.apellido}"
    )

    integrante.delete()

    messages.success(
        request,
        (
            f"El integrante "
            f"{nombre_integrante} "
            "fue eliminado correctamente "
            "del equipo."
        )
    )

    return redirect(
        "agregar_integrantes",
        torneo_id=torneo.id,
        equipo_id=equipo.id
    )


# =========================================================
# AGREGAR RESPONSABLE COMO INTEGRANTE
# =========================================================

@login_required
def agregar_responsable_como_integrante(
    request,
    torneo_id,
    equipo_id
):

    if request.user.rol == "admin":

        return redirect(
            "admin_dashboard"
        )

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id
    )

    equipo = get_object_or_404(
        Equipo,
        id=equipo_id,
        responsable=request.user
    )

    configuracion = get_object_or_404(
        ConfiguracionInscripcion,
        torneo=torneo
    )

    if not configuracion.inscripciones_abiertas:

        messages.error(
            request,
            (
                "Las inscripciones para este "
                "torneo están cerradas."
            )
        )

        return redirect(
            "torneos_disponibles"
        )

    if Inscripcion.objects.filter(
        torneo=torneo,
        equipo=equipo
    ).exists():

        messages.warning(
            request,
            (
                "Este equipo ya tiene una "
                "inscripción registrada."
            )
        )

        return redirect(
            "torneos_disponibles"
        )

    if request.method != "POST":

        messages.error(
            request,
            "La solicitud no es válida."
        )

        return redirect(
            "agregar_integrantes",
            torneo_id=torneo.id,
            equipo_id=equipo.id
        )

    cantidad_integrantes = (
        equipo.integrantes.count()
    )

    if (
        cantidad_integrantes
        >= configuracion.maximo_integrantes
    ):

        messages.error(
            request,
            (
                "No puedes agregarte porque "
                "el equipo ya alcanzó el "
                "máximo de integrantes permitido."
            )
        )

        return redirect(
            "agregar_integrantes",
            torneo_id=torneo.id,
            equipo_id=equipo.id
        )

    usuario = request.user

    responsable_existente = (
        equipo.integrantes.filter(
            nombre__iexact=usuario.nombre.strip(),
            apellido__iexact=usuario.apellido.strip()
        ).exists()
    )

    if responsable_existente:

        messages.info(
            request,
            (
                "Ya estás registrado como "
                "integrante de este equipo."
            )
        )

        return redirect(
            "agregar_integrantes",
            torneo_id=torneo.id,
            equipo_id=equipo.id
        )

    IntegranteEquipo.objects.create(
        equipo=equipo,
        nombre=usuario.nombre,
        apellido=usuario.apellido,
        celular=usuario.celular,
        centro_formacion=usuario.centro_formacion,
        jornada=usuario.jornada,
        ficha=usuario.ficha
    )

    messages.success(
        request,
        (
            f"Se agregó correctamente a "
            f"{usuario.nombre} "
            f"{usuario.apellido} "
            "como integrante del equipo."
        )
    )

    return redirect(
        "agregar_integrantes",
        torneo_id=torneo.id,
        equipo_id=equipo.id
    )


# =========================================================
# FINALIZAR INSCRIPCIÓN
# =========================================================

@login_required
def finalizar_inscripcion(
    request,
    torneo_id,
    equipo_id
):

    if request.user.rol == "admin":

        return redirect(
            "admin_dashboard"
        )

    torneo = get_object_or_404(
        Torneo,
        id=torneo_id
    )

    equipo = get_object_or_404(
        Equipo,
        id=equipo_id,
        responsable=request.user
    )

    configuracion = get_object_or_404(
        ConfiguracionInscripcion,
        torneo=torneo
    )

    if not configuracion.inscripciones_abiertas:

        messages.error(
            request,
            (
                "Las inscripciones para este "
                "torneo están cerradas."
            )
        )

        return redirect(
            "torneos_disponibles"
        )

    integrantes = (
        equipo.integrantes.all()
    )

    cantidad_integrantes = (
        integrantes.count()
    )

    if (
        cantidad_integrantes
        < configuracion.minimo_integrantes
    ):

        messages.error(
            request,
            (
                "El equipo debe tener mínimo "
                f"{configuracion.minimo_integrantes} "
                "integrantes. Actualmente tiene "
                f"{cantidad_integrantes}."
            )
        )

        return redirect(
            "agregar_integrantes",
            torneo_id=torneo.id,
            equipo_id=equipo.id
        )

    if (
        cantidad_integrantes
        > configuracion.maximo_integrantes
    ):

        messages.error(
            request,
            (
                "El equipo no puede superar "
                f"los {configuracion.maximo_integrantes} "
                "integrantes."
            )
        )

        return redirect(
            "agregar_integrantes",
            torneo_id=torneo.id,
            equipo_id=equipo.id
        )

    inscripcion_existente = (
        Inscripcion.objects
        .filter(
            torneo=torneo,
            equipo=equipo
        )
        .first()
    )

    if inscripcion_existente:

        messages.warning(
            request,
            (
                "Este equipo ya tiene una "
                "inscripción registrada."
            )
        )

        return redirect(
            "mis_inscripciones"
        )

    
    inscripcion = Inscripcion.objects.create(
        torneo=torneo,
        equipo=equipo,
        responsable=request.user,
        estado="pendiente",
        ediciones_realizadas=0,
        edicion_bloqueada=False
    )

    notificar_administradores(
        asunto=(
            f"ViveSport: nueva inscripción - "
            f"{torneo.nombre}"
        ),
        mensaje=(
            "Hola, administrador.\n\n"
            f"El equipo '{equipo.nombre}' ha solicitado "
            f"inscribirse en el torneo '{torneo.nombre}'.\n\n"
            f"Responsable: {request.user.nombre} "
            f"{request.user.apellido}\n"
            f"Correo: {request.user.correo}\n\n"
            "Ingresa al módulo administrativo de inscripciones "
            "para revisar la solicitud.\n\n"
            "ViveSport"
        ),
    )


    request.session.pop(
        "equipo_id",
        None
    )

    request.session.pop(
        "torneo_id",
        None
    )

    request.session.pop(
        "equipo_inscripcion_id",
        None
    )

    request.session.pop(
        "torneo_inscripcion_id",
        None
    )

    messages.success(
        request,
        (
            f"La inscripción del equipo "
            f"'{equipo.nombre}' "
            "fue enviada correctamente. "
            "Quedó pendiente de aprobación "
            "por el administrador."
        )
    )

    return redirect(
        "mis_inscripciones"
    )


# =========================================================
# MIS INSCRIPCIONES
# =========================================================

@login_required
def mis_inscripciones(request):

    inscripciones = (
        Inscripcion.objects
        .filter(
            equipo__responsable=request.user
        )
        .select_related(
            "equipo",
            "torneo"
        )
        .prefetch_related(
            "equipo__integrantes"
        )
        .order_by(
            "-fecha_inscripcion"
        )
    )

    # -----------------------------------------------------
    # ACTUALIZAR BLOQUEO AUTOMÁTICO
    # -----------------------------------------------------

    for inscripcion in inscripciones:

        inscripcion.actualizar_bloqueo_automatico()

    return render(
        request,
        "usuarios/mis_inscripciones.html",
        {
            "inscripciones":
                inscripciones,
        }
    )


# =========================================================
# MIS PARTIDOS - USUARIO
# =========================================================

@login_required
def mis_partidos(request):
    equipos_usuario = Equipo.objects.filter(
        responsable=request.user,
        inscripciones__estado="aceptada",
    ).distinct()

    partidos = (
        Partido.objects
        .filter(
            models.Q(equipo_local__in=equipos_usuario)
            | models.Q(equipo_visitante__in=equipos_usuario)
        )
        .select_related(
            "torneo",
            "equipo_local",
            "equipo_visitante",
            "grupo",
            "fase",
            "resultado",
        )
        .order_by("-fecha", "-hora", "-numero")
    )

    return render(
        request,
        "usuarios/mis_partidos.html",
        {
            "partidos": partidos,
        },
    )


# =========================================================
# RESULTADOS - USUARIO
# =========================================================

@login_required
def resultados_usuario(request):
    equipos_usuario = Equipo.objects.filter(
        responsable=request.user,
        inscripciones__estado="aceptada",
    ).distinct()

    partidos = (
        Partido.objects
        .filter(
            models.Q(equipo_local__in=equipos_usuario)
            | models.Q(equipo_visitante__in=equipos_usuario),
            estado="jugado",
            resultado__isnull=False,
        )
        .select_related(
            "torneo",
            "equipo_local",
            "equipo_visitante",
            "grupo",
            "fase",
            "resultado",
        )
        .order_by("-fecha", "-hora", "-numero")
    )

    return render(
        request,
        "usuarios/resultados_usuario.html",
        {
            "partidos": partidos,
        },
    )

# =========================================================
# DETALLE DEL RESULTADO - USUARIO
# =========================================================

@login_required
def detalle_resultado_usuario(request, partido_id):

    if request.user.rol != "usuario":
        return redirect("inicio")

    equipos_usuario = Equipo.objects.filter(
        responsable=request.user,
        inscripciones__estado="aceptada",
    ).distinct()

    partido = get_object_or_404(
        Partido.objects.filter(
            models.Q(equipo_local__in=equipos_usuario)
            | models.Q(equipo_visitante__in=equipos_usuario),
            estado="jugado",
            resultado__isnull=False,
        ).select_related(
            "torneo",
            "equipo_local",
            "equipo_visitante",
            "grupo",
            "fase",
            "resultado",
        ),
        id=partido_id,
    )

    participaciones = (
        ParticipacionPartido.objects
        .filter(partido=partido)
        .select_related("jugador", "equipo")
        .order_by(
            "equipo__nombre",
            "jugador__nombre",
            "jugador__apellido",
        )
    )

    goles = (
        Gol.objects
        .filter(partido=partido)
        .select_related("jugador", "equipo")
        .order_by("id")
    )

    tarjetas = (
        Tarjeta.objects
        .filter(partido=partido)
        .select_related("jugador", "equipo")
        .order_by("id")
    )

    return render(
        request,
        "usuarios/detalle_resultado_usuario.html",
        {
            "partido": partido,
            "participaciones": participaciones,
            "goles": goles,
            "tarjetas": tarjetas,
            "es_futbol": partido.torneo.deporte == "futbol",
        },
    )
# =========================================================
# GRUPOS, CLASIFICACIONES Y ESTADÍSTICAS - USUARIO
# =========================================================

@login_required
def grupos_clasificaciones_usuario(request):
    # Solo se permiten torneos en los que el usuario
    # tenga un equipo responsable con inscripción aceptada.
    torneos_ids = (
        Inscripcion.objects
        .filter(
            equipo__responsable=request.user,
            estado="aceptada",
        )
        .values_list("torneo_id", flat=True)
        .distinct()
    )

    torneos = (
        Torneo.objects
        .filter(
            id__in=torneos_ids,
            configuracion_competicion__sorteo_realizado=True,
        )
        .order_by("nombre")
    )

    # Selección del torneo desde el formulario.
    torneo_id = request.GET.get("torneo", "")
    torneo = None

    if torneo_id and torneo_id.isdigit():
        torneo = torneos.filter(id=int(torneo_id)).first()

    # Si todavía no se ha elegido un torneo, seleccionar
    # el primero disponible para mostrar contenido de entrada.
    if torneo is None:
        torneo = torneos.first()

    
    grupos_clasificacion = []
    tabla_goleadores = []
    tabla_disciplina = []
    fases_eliminatorias = []
    campeon = None
    subcampeon = None
    es_futbol = False

    if torneo:
        es_futbol = torneo.deporte == "futbol"
    

        # -------------------------------------------------
        # FASES ELIMINATORIAS DEL TORNEO
        # -------------------------------------------------

        fases = (
            FaseTorneo.objects
            .filter(
                torneo=torneo,
                tipo__in=["octavos", "cuartos", "semifinal", "final"],
            )
            .order_by("orden", "id")
        )

        for fase in fases:
            partidos_fase = list(
                Partido.objects
                .filter(
                    torneo=torneo,
                    fase=fase,
                )
                .select_related(
                    "equipo_local",
                    "equipo_visitante",
                    "resultado",
                )
                .order_by("numero", "id")
            )

            fases_eliminatorias.append({
                "fase": fase,
                "partidos": partidos_fase,
            })

            # Determinar campeón y subcampeón solo a partir
            # de una final jugada con un marcador definitivo.
            if fase.tipo == "final" and len(partidos_fase) == 1:
                partido_final = partidos_fase[0]

                try:
                    resultado_final = partido_final.resultado
                except ResultadoPartido.DoesNotExist:
                    resultado_final = None

                if (
                    partido_final.estado == "jugado"
                    and resultado_final is not None
                    and (
                        resultado_final.marcador_local
                        != resultado_final.marcador_visitante
                    )
                ):
                    if (
                        resultado_final.marcador_local
                        > resultado_final.marcador_visitante
                    ):
                        campeon = partido_final.equipo_local
                        subcampeon = partido_final.equipo_visitante
                    else:
                        campeon = partido_final.equipo_visitante
                        subcampeon = partido_final.equipo_local


        configuracion = (
            ConfiguracionCompeticion.objects
            .filter(torneo=torneo, sorteo_realizado=True)
            .first()
        )

        fase_grupos = (
            FaseTorneo.objects
            .filter(torneo=torneo, tipo="grupos")
            .first()
        )

        if configuracion and fase_grupos:
            cantidad_clasifican = 0

            if configuracion.cantidad_grupos:
                cantidad_clasifican = (
                    configuracion.equipos_clasifican
                    // configuracion.cantidad_grupos
                )

            grupos = (
                Grupo.objects
                .filter(fase=fase_grupos)
                .prefetch_related("equipos_grupo__equipo")
                .order_by("numero")
            )

            # Mostrar TODOS los grupos del torneo seleccionado,
            # aunque todavía no tengan partidos jugados.
            for grupo in grupos:
                equipos_grupo = (
                    Equipo.objects
                    .filter(grupos_asignados__grupo=grupo)
                    .distinct()
                    .order_by("nombre")
                )

                tabla = []

                partidos_grupo = (
                    Partido.objects
                    .filter(
                        torneo=torneo,
                        grupo=grupo,
                        estado="jugado",
                        resultado__isnull=False,
                    )
                    .select_related(
                        "resultado",
                        "equipo_local",
                        "equipo_visitante",
                    )
                )

                for equipo in equipos_grupo:
                    pj = pg = pe = pp = 0
                    gf = gc = puntos = 0

                    for partido in partidos_grupo:
                        if (
                            partido.equipo_local_id != equipo.id
                            and partido.equipo_visitante_id != equipo.id
                        ):
                            continue

                        resultado = partido.resultado

                        if partido.equipo_local_id == equipo.id:
                            favor = resultado.marcador_local
                            contra = resultado.marcador_visitante
                        else:
                            favor = resultado.marcador_visitante
                            contra = resultado.marcador_local

                        pj += 1
                        gf += favor
                        gc += contra

                        if favor > contra:
                            pg += 1
                            puntos += 3
                        elif favor == contra:
                            pe += 1
                            puntos += 1
                        else:
                            pp += 1

                    tabla.append({
                        "equipo": equipo,
                        "pj": pj,
                        "pg": pg,
                        "pe": pe,
                        "pp": pp,
                        "gf": gf,
                        "gc": gc,
                        "dg": gf - gc,
                        "puntos": puntos,
                        "clasifica": False,
                    })

                # Orden general de la clasificación.
                tabla.sort(
                    key=lambda fila: (
                        -fila["puntos"],
                        -fila["dg"],
                        -fila["gf"],
                        fila["equipo"].nombre.lower(),
                    )
                )

                for posicion, fila in enumerate(tabla, start=1):
                    fila["posicion"] = posicion
                    fila["clasifica"] = (
                        cantidad_clasifican > 0
                        and posicion <= cantidad_clasifican
                    )

                grupos_clasificacion.append({
                    "torneo": torneo,
                    "grupo": grupo,
                    "clasificacion": tabla,
                    "cantidad_clasifican": cantidad_clasifican,
                })

        # -------------------------------------------------
        # MÁXIMOS GOLEADORES Y TABLA DE TARJETAS
        # -------------------------------------------------

        partidos_validos = Partido.objects.filter(
            torneo=torneo,
            estado="jugado",
            resultado__isnull=False,
        )

        ids_partidos_validos = list(
            partidos_validos.values_list("id", flat=True)
        )

        estadisticas = {}

        def obtener_estadisticas(jugador):
            if jugador.id not in estadisticas:
                estadisticas[jugador.id] = {
                    "jugador": jugador,
                    "equipo": jugador.equipo,
                    "goles": 0,
                    "partidos_jugados": 0,
                    "amarillas": 0,
                    "rojas": 0,
                    "puntos_disciplina": 0,
                }

            return estadisticas[jugador.id]

        participaciones = (
            ParticipacionPartido.objects
            .filter(partido_id__in=ids_partidos_validos)
            .select_related("jugador", "equipo")
        )

        for participacion in participaciones:
            datos = obtener_estadisticas(participacion.jugador)
            datos["partidos_jugados"] += 1

        if es_futbol:
            goles = (
                Gol.objects
                .filter(partido_id__in=ids_partidos_validos)
                .select_related("jugador", "equipo")
            )

            for gol in goles:
                datos = obtener_estadisticas(gol.jugador)
                datos["goles"] += 1

        tarjetas = (
            Tarjeta.objects
            .filter(partido_id__in=ids_partidos_validos)
            .select_related("jugador", "equipo")
        )

        for tarjeta in tarjetas:
            datos = obtener_estadisticas(tarjeta.jugador)

            if tarjeta.tipo == "amarilla":
                datos["amarillas"] += 1
                datos["puntos_disciplina"] += 1
            elif tarjeta.tipo == "roja":
                datos["rojas"] += 1
                datos["puntos_disciplina"] += 2

        if es_futbol:
            tabla_goleadores = [
                datos
                for datos in estadisticas.values()
                if datos["goles"] > 0
            ]

            tabla_goleadores.sort(
                key=lambda datos: (
                    -datos["goles"],
                    datos["partidos_jugados"],
                    datos["puntos_disciplina"],
                    (
                        datos["jugador"].nombre
                        + " "
                        + datos["jugador"].apellido
                    ).lower(),
                )
            )

        tabla_disciplina = [
            datos
            for datos in estadisticas.values()
            if datos["amarillas"] > 0 or datos["rojas"] > 0
        ]

        tabla_disciplina.sort(
            key=lambda datos: (
                -datos["puntos_disciplina"],
                -datos["rojas"],
                -datos["amarillas"],
                (
                    datos["jugador"].nombre
                    + " "
                    + datos["jugador"].apellido
                ).lower(),
            )
        )

    return render(
        request,
        "usuarios/grupos_clasificaciones_usuario.html",
        {
            "torneos": torneos,
            "torneo_seleccionado": torneo,
            "grupos_clasificacion": grupos_clasificacion,
            "tabla_goleadores": tabla_goleadores,
            "tabla_disciplina": tabla_disciplina,
            "es_futbol": es_futbol,
            "fases_eliminatorias": fases_eliminatorias,
            "campeon": campeon,
            "subcampeon": subcampeon,

        },
    )




# =========================================================
# EDITAR INSCRIPCIÓN
#
# REGLA:
# SOLO "GUARDAR CAMBIOS" CONSUME UNA EDICIÓN.
# =========================================================

@login_required
def editar_inscripcion(
    request,
    inscripcion_id
):

    if request.user.rol == "admin":

        return redirect(
            "admin_dashboard"
        )

    inscripcion = get_object_or_404(
        Inscripcion,
        id=inscripcion_id,
        responsable=request.user
    )

    equipo = inscripcion.equipo

    torneo = inscripcion.torneo

    configuracion = get_object_or_404(
        ConfiguracionInscripcion,
        torneo=torneo
    )

    # -----------------------------------------------------
    # VERIFICAR INSCRIPCIONES ABIERTAS
    # -----------------------------------------------------

    if not configuracion.inscripciones_abiertas:

        messages.error(
            request,
            (
                "Las inscripciones para este "
                "torneo ya están cerradas."
            )
        )

        return redirect(
            "mis_inscripciones"
        )

    # -----------------------------------------------------
    # VERIFICAR ESTADO
    # -----------------------------------------------------

    if inscripcion.estado != "pendiente":

        if inscripcion.estado == "aceptada":

            messages.error(
                request,
                (
                    "Esta inscripción ya fue "
                    "aceptada por el administrador "
                    "y no puede ser editada."
                )
            )

        elif inscripcion.estado == "rechazada":

            messages.error(
                request,
                (
                    "Esta inscripción fue rechazada "
                    "por el administrador y no puede "
                    "ser editada."
                )
            )

        else:

            messages.error(
                request,
                "Esta inscripción no puede ser editada."
            )

        return redirect(
            "mis_inscripciones"
        )

    # -----------------------------------------------------
    # VERIFICAR LÍMITE DE EDICIONES
    # -----------------------------------------------------

    if not inscripcion.puede_editar():

        messages.error(
            request,
            (
                "Esta inscripción está bloqueada "
                "porque ya utilizaste las "
                "3 ediciones permitidas."
            )
        )

        return redirect(
            "mis_inscripciones"
        )

    integrantes = (
        equipo.integrantes
        .all()
        .order_by(
            "nombre",
            "apellido"
        )
    )

    cantidad_integrantes = (
        integrantes.count()
    )

    # =====================================================
    # POST - GUARDAR CAMBIOS
    # =====================================================

    if request.method == "POST":

        # -------------------------------------------------
        # TRANSACCIÓN
        #
        # Bloqueamos la inscripción mientras se realiza
        # el guardado para evitar problemas si llegan
        # dos solicitudes simultáneas.
        # -------------------------------------------------

        with transaction.atomic():

            inscripcion_bloqueada = (
                Inscripcion.objects
                .select_for_update()
                .get(
                    id=inscripcion.id
                )
            )

            # ---------------------------------------------
            # VOLVER A VALIDAR
            # ---------------------------------------------

            if not inscripcion_bloqueada.puede_editar():

                messages.error(
                    request,
                    (
                        "La inscripción ya no "
                        "puede ser editada."
                    )
                )

                return redirect(
                    "mis_inscripciones"
                )

            # ---------------------------------------------
            # FORMULARIO
            # ---------------------------------------------

            form = EquipoForm(
                request.POST,
                instance=equipo
            )

            # ---------------------------------------------
            # VALIDAR
            #
            # SI FALLA:
            # NO SE CONSUME EDICIÓN.
            # ---------------------------------------------

            if not form.is_valid():

                integrantes_form = (
                    IntegranteEquipoForm(
                        equipo=equipo
                    )
                )

                return render(
                    request,
                    "usuarios/editar_inscripcion.html",
                    {
                        "form": form,
                        "integrantes_form":
                            integrantes_form,
                        "inscripcion":
                            inscripcion_bloqueada,
                        "equipo":
                            equipo,
                        "torneo":
                            torneo,
                        "configuracion":
                            configuracion,
                        "integrantes":
                            integrantes,
                        "cantidad_integrantes":
                            cantidad_integrantes,
                        "ediciones_restantes": (
                            3
                            - inscripcion_bloqueada
                            .ediciones_realizadas
                        ),
                    }
                )

            # ---------------------------------------------
            # GUARDAR CAMBIOS DEL EQUIPO
            # ---------------------------------------------

            form.save()

            # ---------------------------------------------
            # CONSUMIR UNA EDICIÓN
            #
            # ESTE ES EL ÚNICO PUNTO DEL SISTEMA DONDE
            # EL GUARDADO DEL EQUIPO CONSUME UNA EDICIÓN.
            # ---------------------------------------------

            inscripcion_bloqueada.registrar_edicion()

            # ---------------------------------------------
            # ACTUALIZAR OBJETO EN MEMORIA
            # ---------------------------------------------

            inscripcion = (
                inscripcion_bloqueada
            )

        # -------------------------------------------------
        # EDICIONES RESTANTES
        # -------------------------------------------------

        ediciones_restantes = (
            3
            - inscripcion.ediciones_realizadas
        )

        # -------------------------------------------------
        # SI AÚN TIENE EDICIONES
        # -------------------------------------------------

        if ediciones_restantes > 0:

            messages.success(
                request,
                (
                    "Los cambios fueron guardados "
                    "correctamente. "
                    f"Has utilizado "
                    f"{inscripcion.ediciones_realizadas} "
                    "de 3 ediciones. "
                    f"Te quedan "
                    f"{ediciones_restantes} "
                    "ediciones disponibles."
                )
            )

            return redirect(
                "editar_inscripcion",
                inscripcion_id=inscripcion.id
            )

        # -------------------------------------------------
        # SI LLEGÓ A LAS 3 EDICIONES
        # -------------------------------------------------

        messages.success(
            request,
            (
                "Los cambios fueron guardados "
                "correctamente. "
                "Has utilizado las 3 ediciones "
                "permitidas. La inscripción ha "
                "quedado bloqueada."
            )
        )

        return redirect(
            "mis_inscripciones"
        )

    # =====================================================
    # GET
    # =====================================================

    form = EquipoForm(
        instance=equipo
    )

    integrantes_form = (
        IntegranteEquipoForm(
            equipo=equipo
        )
    )

    return render(
        request,
        "usuarios/editar_inscripcion.html",
        {
            "form": form,
            "integrantes_form":
                integrantes_form,
            "inscripcion":
                inscripcion,
            "equipo":
                equipo,
            "torneo":
                torneo,
            "configuracion":
                configuracion,
            "integrantes":
                integrantes,
            "cantidad_integrantes":
                cantidad_integrantes,
            "ediciones_restantes": (
                3
                - inscripcion.ediciones_realizadas
            ),
        }
    )
# =========================================================
# AGREGAR INTEGRANTE DURANTE LA EDICIÓN
# =========================================================

@login_required
def agregar_integrante_edicion(
    request,
    inscripcion_id
):

    if request.user.rol == "admin":

        return redirect(
            "admin_dashboard"
        )

    inscripcion = get_object_or_404(
        Inscripcion,
        id=inscripcion_id,
        responsable=request.user
    )

    torneo = inscripcion.torneo
    equipo = inscripcion.equipo

    configuracion = get_object_or_404(
        ConfiguracionInscripcion,
        torneo=torneo
    )

    # -----------------------------------------------------
    # VERIFICAR QUE LA INSCRIPCIÓN SIGA PENDIENTE
    # -----------------------------------------------------

    if inscripcion.estado != "pendiente":

        messages.error(
            request,
            "Esta inscripción ya no puede ser modificada."
        )

        return redirect(
            "mis_inscripciones"
        )

    # -----------------------------------------------------
    # VERIFICAR QUE LAS INSCRIPCIONES ESTÉN ABIERTAS
    # -----------------------------------------------------

    if not configuracion.inscripciones_abiertas:

        messages.error(
            request,
            "Las inscripciones para este torneo están cerradas."
        )

        return redirect(
            "mis_inscripciones"
        )

    # -----------------------------------------------------
    # VERIFICAR LÍMITE DE EDICIONES
    # -----------------------------------------------------

    if not inscripcion.puede_editar():

        messages.error(
            request,
            (
                "Esta inscripción ya alcanzó el límite "
                "de 3 ediciones y no puede ser modificada."
            )
        )

        return redirect(
            "mis_inscripciones"
        )

    # -----------------------------------------------------
    # OBTENER INTEGRANTES
    # -----------------------------------------------------

    integrantes = (
        equipo.integrantes
        .all()
        .order_by(
            "nombre",
            "apellido"
        )
    )

    cantidad_integrantes = integrantes.count()

    # -----------------------------------------------------
    # VERIFICAR MÁXIMO
    # -----------------------------------------------------

    if cantidad_integrantes >= configuracion.maximo_integrantes:

        messages.warning(
            request,
            (
                "El equipo ya alcanzó el máximo "
                "de integrantes permitido."
            )
        )

        return redirect(
            "editar_inscripcion",
            inscripcion_id=inscripcion.id
        )

    # -----------------------------------------------------
    # FORMULARIO
    # -----------------------------------------------------

    if request.method == "POST":

        form = IntegranteEquipoForm(
            request.POST,
            equipo=equipo
        )

        if form.is_valid():

            integrante = form.save(
                commit=False
            )

            integrante.equipo = equipo

            integrante.save()

            messages.success(
                request,
                (
                    f"El integrante "
                    f"{integrante.nombre} "
                    f"{integrante.apellido} "
                    "fue agregado correctamente."
                )
            )

            return redirect(
                "editar_inscripcion",
                inscripcion_id=inscripcion.id
            )

    else:

        form = IntegranteEquipoForm(
            equipo=equipo
        )

    return render(
        request,
        "usuarios/agregar_integrante_edicion.html",
        {
            "form": form,
            "inscripcion": inscripcion,
            "torneo": torneo,
            "equipo": equipo,
            "configuracion": configuracion,
            "integrantes": integrantes,
            "cantidad_integrantes": cantidad_integrantes,
        }
    )


# =========================================================
# ELIMINAR INTEGRANTE DURANTE LA EDICIÓN
# =========================================================

@login_required
def eliminar_integrante_edicion(
    request,
    inscripcion_id,
    integrante_id
):

    if request.user.rol == "admin":

        return redirect(
            "admin_dashboard"
        )

    inscripcion = get_object_or_404(
        Inscripcion,
        id=inscripcion_id,
        responsable=request.user
    )

    torneo = inscripcion.torneo
    equipo = inscripcion.equipo

    configuracion = get_object_or_404(
        ConfiguracionInscripcion,
        torneo=torneo
    )

    # -----------------------------------------------------
    # SOLO POST
    # -----------------------------------------------------

    if request.method != "POST":

        messages.error(
            request,
            "La solicitud no es válida."
        )

        return redirect(
            "editar_inscripcion",
            inscripcion_id=inscripcion.id
        )

    # -----------------------------------------------------
    # VERIFICAR ESTADO
    # -----------------------------------------------------

    if inscripcion.estado != "pendiente":

        messages.error(
            request,
            "Esta inscripción ya no puede ser modificada."
        )

        return redirect(
            "mis_inscripciones"
        )

    # -----------------------------------------------------
    # VERIFICAR INSCRIPCIONES ABIERTAS
    # -----------------------------------------------------

    if not configuracion.inscripciones_abiertas:

        messages.error(
            request,
            "Las inscripciones para este torneo están cerradas."
        )

        return redirect(
            "mis_inscripciones"
        )

    # -----------------------------------------------------
    # VERIFICAR LÍMITE DE EDICIONES
    # -----------------------------------------------------

    if not inscripcion.puede_editar():

        messages.error(
            request,
            (
                "Esta inscripción ya alcanzó el límite "
                "de 3 ediciones y no puede ser modificada."
            )
        )

        return redirect(
            "mis_inscripciones"
        )

    # -----------------------------------------------------
    # OBTENER INTEGRANTE
    # -----------------------------------------------------

    integrante = get_object_or_404(
        IntegranteEquipo,
        id=integrante_id,
        equipo=equipo
    )

    # -----------------------------------------------------
    # NO PERMITIR BAJAR DEL MÍNIMO
    # -----------------------------------------------------

    cantidad_integrantes = (
        equipo.integrantes.count()
    )

    if cantidad_integrantes <= configuracion.minimo_integrantes:

        messages.warning(
            request,
            (
                "No puedes eliminar este integrante "
                "porque el equipo debe tener como mínimo "
                f"{configuracion.minimo_integrantes} "
                "integrante(s)."
            )
        )

        return redirect(
            "editar_inscripcion",
            inscripcion_id=inscripcion.id
        )

    # -----------------------------------------------------
    # GUARDAR NOMBRE ANTES DE ELIMINAR
    # -----------------------------------------------------

    nombre_integrante = (
        f"{integrante.nombre} "
        f"{integrante.apellido}"
    )

    integrante.delete()

    messages.success(
        request,
        (
            f"El integrante {nombre_integrante} "
            "fue eliminado correctamente."
        )
    )

    # -----------------------------------------------------
    # IMPORTANTE:
    # ESTA ACCIÓN NO CONSUME UNA EDICIÓN
    # -----------------------------------------------------

    return redirect(
        "editar_inscripcion",
        inscripcion_id=inscripcion.id
    )
@login_required
def mis_equipos(request):

    equipos = (
        Equipo.objects
        .filter(
            responsable=request.user
        )
        .prefetch_related(
            "integrantes",
            "inscripciones__torneo"
        )
    )

    return render(
        request,
        "usuarios/mis_equipos.html",
        {
            "equipos": equipos,
        }
    )

@login_required
def ver_equipo(request, equipo_id):

    equipo = get_object_or_404(
        Equipo.objects
        .filter(
            responsable=request.user
        )
        .prefetch_related(
            "integrantes",
            "inscripciones__torneo"
        ),
        id=equipo_id
    )

    return render(
        request,
        "usuarios/ver_equipo.html",
        {
            "equipo": equipo,
        }
    )

# =========================================================
# ELIMINAR INSCRIPCIÓN
# =========================================================

@login_required
def eliminar_inscripcion(
    request,
    inscripcion_id
):

    if request.user.rol == "admin":

        return redirect(
            "admin_dashboard"
        )


    if request.method != "POST":

        messages.error(
            request,
            "La solicitud no es válida."
        )

        return redirect(
            "mis_inscripciones"
        )


    inscripcion = get_object_or_404(
        Inscripcion,
        id=inscripcion_id,
        responsable=request.user
    )


    # -----------------------------------------------------
    # SOLO PENDIENTES
    # -----------------------------------------------------

    if inscripcion.estado != "pendiente":

        if inscripcion.estado == "aceptada":

            messages.error(
                request,
                (
                    "No puedes eliminar esta inscripción "
                    "porque ya fue aceptada por el "
                    "administrador."
                )
            )

        elif inscripcion.estado == "rechazada":

            messages.error(
                request,
                (
                    "No puedes eliminar esta inscripción "
                    "porque fue rechazada y se conserva "
                    "como historial."
                )
            )

        else:

            messages.error(
                request,
                (
                    "Esta inscripción no puede "
                    "ser eliminada."
                )
            )

        return redirect(
            "mis_inscripciones"
        )


    # -----------------------------------------------------
    # VERIFICAR SI LA INSCRIPCIÓN YA ESTÁ DEFINIDA
    # -----------------------------------------------------

    if inscripcion.esta_definida():

        messages.error(
            request,
            (
                "No puedes eliminar esta inscripción "
                "porque ya está definida. "
                "Sus datos son permanentes y no "
                "pueden modificarse ni eliminarse."
            )
        )

        return redirect(
            "mis_inscripciones"
        )


    # -----------------------------------------------------
    # CONTROL DE ELIMINACIONES
    # -----------------------------------------------------

    control, creado = (
        ControlInscripcion.objects
        .get_or_create(
            usuario=request.user,
            torneo=inscripcion.torneo
        )
    )


    if not control.puede_eliminar():

        messages.error(
            request,
            (
                "Ya utilizaste las 2 oportunidades "
                "permitidas para eliminar y volver "
                "a realizar la inscripción en este torneo."
            )
        )

        return redirect(
            "mis_inscripciones"
        )


    # -----------------------------------------------------
    # DATOS
    # -----------------------------------------------------

    nombre_equipo = (
        inscripcion.equipo.nombre
    )

    nombre_torneo = (
        inscripcion.torneo.nombre
    )

    equipo = inscripcion.equipo


    # -----------------------------------------------------
    # REGISTRAR ELIMINACIÓN
    # -----------------------------------------------------

    control.registrar_eliminacion()


    # -----------------------------------------------------
    # ELIMINAR INSCRIPCIÓN
    # -----------------------------------------------------

    inscripcion.delete()


    # -----------------------------------------------------
    # ELIMINAR EQUIPO
    # -----------------------------------------------------

    equipo.delete()


    # -----------------------------------------------------
    # OPORTUNIDADES RESTANTES
    # -----------------------------------------------------

    oportunidades_restantes = (
        2
        - control.eliminaciones_realizadas
    )


    if oportunidades_restantes > 0:

        messages.success(
            request,
            (
                f"La inscripción del equipo "
                f"'{nombre_equipo}' en el torneo "
                f"'{nombre_torneo}' fue eliminada "
                "correctamente. "
                "Puedes realizar una nueva inscripción "
                "desde cero. "
                f"Te queda "
                f"{oportunidades_restantes} "
                "oportunidad de eliminación."
            )
        )

    else:

        messages.success(
            request,
            (
                f"La inscripción del equipo "
                f"'{nombre_equipo}' en el torneo "
                f"'{nombre_torneo}' fue eliminada "
                "correctamente. "
                "Has utilizado las 2 oportunidades "
                "permitidas para eliminar una "
                "inscripción en este torneo."
            )
        )


    return redirect(
        "torneos_disponibles"
    )
# =========================================================
# GRUPOS - ADMIN
# =========================================================

@login_required
def grupos_admin(request):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    configuraciones = (
        ConfiguracionCompeticion.objects
        .select_related(
            "torneo"
        )
        .filter(
            sorteo_realizado=True
        )
        .order_by(
            "torneo__fecha_inicio"
        )
    )

    return render(
        request,
        "usuarios/grupos_admin.html",
        {
            "configuraciones":
                configuraciones,
        }
    )


# =========================================================
# GRUPOS Y CLASIFICACIÓN DE UN TORNEO - ADMIN
# =========================================================

@login_required
def grupos_torneo_admin(
    request,
    configuracion_id
):

    if request.user.rol != "admin":

        return redirect(
            "inicio"
        )

    configuracion = get_object_or_404(
        ConfiguracionCompeticion.objects
        .select_related(
            "torneo"
        ),
        id=configuracion_id
    )

    torneo = configuracion.torneo

    # -----------------------------------------------------
    # VERIFICAR QUE EL SORTEO YA SE HAYA REALIZADO
    # -----------------------------------------------------

    if not configuracion.sorteo_realizado:

        messages.warning(
            request,
            (
                "Los grupos todavía no han sido "
                "generados porque el sorteo no "
                "ha sido realizado."
            )
        )

        return redirect(
            "grupos_admin"
        )

    # -----------------------------------------------------
    # OBTENER FASE DE GRUPOS
    # -----------------------------------------------------

    fase_grupos = get_object_or_404(
        FaseTorneo,
        torneo=torneo,
        tipo="grupos"
    )

    # -----------------------------------------------------
    # OBTENER GRUPOS
    # -----------------------------------------------------

    grupos = (
        Grupo.objects
        .filter(
            fase=fase_grupos
        )
        .prefetch_related(
            "equipos_grupo__equipo"
        )
        .order_by(
            "numero"
        )
    )

    # =====================================================
    # CALCULAR CLASIFICACIÓN
    # =====================================================

    grupos_clasificacion = []

    for grupo in grupos:

        equipos_grupo = list(
            Equipo.objects
            .filter(
                grupos_asignados__grupo=grupo
            )
            .distinct()
            .order_by(
                "nombre"
            )
        )

        clasificacion = []

        # -------------------------------------------------
        # CALCULAR ESTADÍSTICAS DE CADA EQUIPO
        # -------------------------------------------------

        for equipo in equipos_grupo:

            partidos_jugados = (
                Partido.objects
                .filter(
                    grupo=grupo,
                    estado="jugado"
                )
                .filter(
                    models.Q(
                        equipo_local=equipo
                    )
                    |
                    models.Q(
                        equipo_visitante=equipo
                    )
                )
                .select_related(
                    "resultado",
                    "equipo_local",
                    "equipo_visitante"
                )
            )

            pj = 0
            pg = 0
            pe = 0
            pp = 0

            gf = 0
            gc = 0

            puntos = 0
            juego_limpio = 0

            # -------------------------------------------------
            # RECORRER PARTIDOS JUGADOS
            # -------------------------------------------------

            for partido in partidos_jugados:

                if not hasattr(
                    partido,
                    "resultado"
                ):

                    continue

                resultado = partido.resultado

                marcador_local = (
                    resultado.marcador_local
                )

                marcador_visitante = (
                    resultado.marcador_visitante
                )

                pj += 1

                # -------------------------------------------------
                # EQUIPO LOCAL
                # -------------------------------------------------

                if (
                    partido.equipo_local_id
                    == equipo.id
                ):

                    gf += marcador_local

                    gc += marcador_visitante

                    if (
                        marcador_local
                        > marcador_visitante
                    ):

                        pg += 1
                        puntos += 3

                    elif (
                        marcador_local
                        == marcador_visitante
                    ):

                        pe += 1
                        puntos += 1

                    else:

                        pp += 1

                # -------------------------------------------------
                # EQUIPO VISITANTE
                # -------------------------------------------------

                else:

                    gf += marcador_visitante

                    gc += marcador_local

                    if (
                        marcador_visitante
                        > marcador_local
                    ):

                        pg += 1
                        puntos += 3

                    elif (
                        marcador_visitante
                        == marcador_local
                    ):

                        pe += 1
                        puntos += 1

                    else:

                        pp += 1

                # -------------------------------------------------
                # JUEGO LIMPIO
                # -------------------------------------------------

                tarjetas = (
                    partido.tarjetas
                    .filter(
                        equipo=equipo
                    )
                )

                for tarjeta in tarjetas:

                    juego_limpio += (
                        tarjeta
                        .penalizacion_juego_limpio
                    )

            # -------------------------------------------------
            # DIFERENCIA DE GOLES
            # -------------------------------------------------

            dg = gf - gc

            clasificacion.append(
                {
                    "equipo": equipo,
                    "pj": pj,
                    "pg": pg,
                    "pe": pe,
                    "pp": pp,
                    "gf": gf,
                    "gc": gc,
                    "dg": dg,
                    "puntos": puntos,
                    "juego_limpio":
                        juego_limpio,
                }
            )

        # =================================================
        # ORDEN PRINCIPAL
        #
        # 1. PUNTOS
        # 2. JUEGO LIMPIO
        # 3. DIFERENCIA DE GOLES
        # 4. GOLES A FAVOR
        # =================================================

        clasificacion.sort(
            key=lambda item: (
                -item["puntos"],
                -item["juego_limpio"],
                -item["dg"],
                -item["gf"],
            )
        )

        # =================================================
        # DESEMPATE POR ENFRENTAMIENTO DIRECTO
        # =================================================

        i = 0

        while i < len(clasificacion):

            j = i + 1

            while j < len(clasificacion):

                misma_posicion = (
                    clasificacion[j]["puntos"]
                    == clasificacion[i]["puntos"]
                    and
                    clasificacion[j]["juego_limpio"]
                    == clasificacion[i]["juego_limpio"]
                    and
                    clasificacion[j]["dg"]
                    == clasificacion[i]["dg"]
                    and
                    clasificacion[j]["gf"]
                    == clasificacion[i]["gf"]
                )

                if not misma_posicion:

                    break

                j += 1

            # -------------------------------------------------
            # SOLO APLICAR ENFRENTAMIENTO DIRECTO
            # CUANDO HAY DOS O MÁS EQUIPOS EMPATADOS
            # -------------------------------------------------

            if j - i > 1:

                equipos_empatados = (
                    clasificacion[i:j]
                )

                ids_equipos = [
                    item["equipo"].id
                    for item in equipos_empatados
                ]

                enfrentamientos = (
                    Partido.objects
                    .filter(
                        grupo=grupo,
                        estado="jugado"
                    )
                    .filter(
                        models.Q(
                            equipo_local_id__in=
                            ids_equipos
                        )
                        |
                        models.Q(
                            equipo_visitante_id__in=
                            ids_equipos
                        )
                    )
                    .select_related(
                        "resultado"
                    )
                )

                datos_directos = {}

                for item in equipos_empatados:

                    datos_directos[
                        item["equipo"].id
                    ] = {
                        "puntos": 0,
                        "dg": 0,
                        "gf": 0,
                    }

                for partido in enfrentamientos:

                    if not hasattr(
                        partido,
                        "resultado"
                    ):

                        continue

                    local_id = (
                        partido.equipo_local_id
                    )

                    visitante_id = (
                        partido.equipo_visitante_id
                    )

                    # -----------------------------------------
                    # SOLO PARTIDOS ENTRE LOS EMPATADOS
                    # -----------------------------------------

                    if (
                        local_id not in ids_equipos
                        or
                        visitante_id not in ids_equipos
                    ):

                        continue

                    local_score = (
                        partido.resultado
                        .marcador_local
                    )

                    visitante_score = (
                        partido.resultado
                        .marcador_visitante
                    )

                    datos_directos[
                        local_id
                    ]["gf"] += local_score

                    datos_directos[
                        local_id
                    ]["dg"] += (
                        local_score
                        - visitante_score
                    )

                    datos_directos[
                        visitante_id
                    ]["gf"] += visitante_score

                    datos_directos[
                        visitante_id
                    ]["dg"] += (
                        visitante_score
                        - local_score
                    )

                    if local_score > visitante_score:

                        datos_directos[
                            local_id
                        ]["puntos"] += 3

                    elif local_score < visitante_score:

                        datos_directos[
                            visitante_id
                        ]["puntos"] += 3

                    else:

                        datos_directos[
                            local_id
                        ]["puntos"] += 1

                        datos_directos[
                            visitante_id
                        ]["puntos"] += 1

                # ---------------------------------------------
                # ORDENAR EL BLOQUE EMPATADO
                #
                # 5. ENFRENTAMIENTO DIRECTO
                # ---------------------------------------------

                equipos_empatados.sort(
                    key=lambda item: (
                        -datos_directos[
                            item["equipo"].id
                        ]["puntos"],

                        -datos_directos[
                            item["equipo"].id
                        ]["dg"],

                        -datos_directos[
                            item["equipo"].id
                        ]["gf"],

                        item["equipo"].id,
                    )
                )

                clasificacion[
                    i:j
                ] = equipos_empatados

            i = j

        # =================================================
        # POSICIONES
        # =================================================

        for posicion, item in enumerate(
            clasificacion,
            start=1
        ):

            item["posicion"] = posicion

        # =================================================
        # EQUIPOS QUE CLASIFICAN
        # =================================================

        cantidad_clasifican = (
            configuracion.equipos_clasifican
            // configuracion.cantidad_grupos
        )

        for item in clasificacion:

            item["clasifica"] = (
                item["posicion"]
                <= cantidad_clasifican
            )

        grupos_clasificacion.append(
            {
                "grupo": grupo,
                "clasificacion":
                    clasificacion,
                "cantidad_clasifican":
                    cantidad_clasifican,
            }
        )

    # =================================================
    # ESTADÍSTICAS INDIVIDUALES DEL TORNEO
    # =================================================

    from .models import (
        Gol,
        Tarjeta,
        ParticipacionPartido,
    )

    # Solo contar partidos jugados con resultado registrado.
    partidos_validos = Partido.objects.filter(
        torneo=torneo,
        estado="jugado",
        resultado__isnull=False,
    )

    ids_partidos_validos = list(
        partidos_validos.values_list("id", flat=True)
    )

    estadisticas_jugadores = {}

    def obtener_estadisticas(jugador):
        if jugador.id not in estadisticas_jugadores:
            estadisticas_jugadores[jugador.id] = {
                "jugador": jugador,
                "goles": 0,
                "partidos_jugados": 0,
                "amarillas": 0,
                "rojas": 0,
                "puntos_disciplina": 0,
            }

        return estadisticas_jugadores[jugador.id]

    # Partidos en los que participó cada jugador.
    participaciones = ParticipacionPartido.objects.filter(
        partido_id__in=ids_partidos_validos,
    ).select_related("jugador")

    for participacion in participaciones:
        datos = obtener_estadisticas(
            participacion.jugador
        )
        datos["partidos_jugados"] += 1

    # Goles registrados durante el torneo.
    if torneo.deporte == "futbol":
        goles_registrados = Gol.objects.filter(
            partido_id__in=ids_partidos_validos,
        ).select_related("jugador")

        for gol in goles_registrados:
            datos = obtener_estadisticas(gol.jugador)
            datos["goles"] += 1

    # Tarjetas registradas durante el torneo.
    tarjetas_registradas = Tarjeta.objects.filter(
        partido_id__in=ids_partidos_validos,
    ).select_related("jugador")

    for tarjeta in tarjetas_registradas:
        datos = obtener_estadisticas(tarjeta.jugador)

        if tarjeta.tipo == "amarilla":
            datos["amarillas"] += 1
            datos["puntos_disciplina"] += 1

        elif tarjeta.tipo == "roja":
            datos["rojas"] += 1
            datos["puntos_disciplina"] += 2

    # Tabla de goleadores: solo jugadores que marcaron.
    tabla_goleadores = []

    if torneo.deporte == "futbol":
        tabla_goleadores = [
            datos
            for datos in estadisticas_jugadores.values()
            if datos["goles"] > 0
        ]

        tabla_goleadores.sort(
            key=lambda datos: (
                -datos["goles"],
                datos["partidos_jugados"],
                datos["puntos_disciplina"],
                (
                    datos["jugador"].nombre
                    + " "
                    + datos["jugador"].apellido
                ).lower(),
            )
        )

    # Tabla disciplinaria: jugadores que recibieron tarjetas.
    tabla_disciplina = [
        datos
        for datos in estadisticas_jugadores.values()
        if datos["amarillas"] > 0 or datos["rojas"] > 0
    ]

    tabla_disciplina.sort(
        key=lambda datos: (
            -datos["puntos_disciplina"],
            -datos["rojas"],
            -datos["amarillas"],
            (
                datos["jugador"].nombre
                + " "
                + datos["jugador"].apellido
            ).lower(),
        )
    )

    # =================================================
    # FASES ELIMINATORIAS DEL TORNEO
    # =================================================

    fases_eliminatorias = (
        FaseTorneo.objects
        .filter(torneo=torneo)
        .exclude(tipo="grupos")
        .order_by("orden")
    )

    for fase in fases_eliminatorias:
        fase.partidos_fase = (
            Partido.objects
            .filter(fase=fase)
            .select_related(
                "equipo_local",
                "equipo_visitante",
                "resultado",
            )
            .order_by("numero")
        )
    return render(
        request,
        "usuarios/grupos_torneo_admin.html",
        {
            "configuracion":
                configuracion,
            "torneo":
                torneo,
            "fase_grupos":
                fase_grupos,
            "grupos_clasificacion":
                grupos_clasificacion,
            "tabla_goleadores":
                tabla_goleadores,
            "tabla_disciplina": 
                tabla_disciplina,
            "fases_eliminatorias": 
                fases_eliminatorias,
        }
    )


# =========================================================
# CERRAR SESIÓN
# =========================================================

@login_required
def logout_view(request):

    logout(request)

    return redirect(
        "login"
    )
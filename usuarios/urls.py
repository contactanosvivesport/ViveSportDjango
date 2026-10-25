from django.urls import path

from . import views


urlpatterns = [

    # =====================================================
    # AUTENTICACIÓN
    # =====================================================

    path(
        "registro/",
        views.registro,
        name="registro"
    ),

    path(
        "login/",
        views.login_view,
        name="login"
    ),

    path(
        "logout/",
        views.logout_view,
        name="logout"
    ),

    path(
    "recuperar-password/",
    views.solicitar_recuperacion,
    name="solicitar_recuperacion"
    ),

    path(
    "verificar-codigo/",
    views.verificar_codigo_recuperacion,
    name="verificar_codigo_recuperacion"
    ),

    path(
    "restablecer-password/",
    views.restablecer_password,
    name="restablecer_password"
    ),

    # =====================================================
    # PÁGINAS PRINCIPALES
    # =====================================================

    path(
        "inicio/",
        views.inicio,
        name="inicio"
    ),

    path(
        "torneos/disponibles/",
        views.torneos_disponibles,
        name="torneos_disponibles"
    ),


    # =====================================================
    # INSCRIPCIÓN DE EQUIPOS - USUARIO
    # =====================================================

    path(
        "torneos/<int:torneo_id>/crear-equipo/",
        views.crear_equipo,
        name="crear_equipo"
    ),

    path(
        "equipos/<int:equipo_id>/torneo/<int:torneo_id>/agregar-integrantes/",
        views.agregar_integrantes,
        name="agregar_integrantes"
    ),

    path(
        "torneos/<int:torneo_id>/equipos/<int:equipo_id>/agregar-responsable/",
        views.agregar_responsable_como_integrante,
        name="agregar_responsable_como_integrante"
    ),

    path(
        "torneos/<int:torneo_id>/equipos/<int:equipo_id>/integrantes/<int:integrante_id>/eliminar/",
        views.eliminar_integrante,
        name="eliminar_integrante"
    ),

    path(
        "equipos/<int:equipo_id>/torneo/<int:torneo_id>/finalizar-inscripcion/",
        views.finalizar_inscripcion,
        name="finalizar_inscripcion"
    ),

    path(
        "mis-inscripciones/",
        views.mis_inscripciones,
        name="mis_inscripciones"
    ),

    path(
        "mis-equipos/",
        views.mis_equipos,
        name="mis_equipos"
    ),


    path(
        "mis-partidos/",
        views.mis_partidos,
        name="mis_partidos",
    ),

    path(
        "resultados/",
        views.resultados_usuario,
        name="resultados_usuario",
    ),

    path(
    "resultados/<int:partido_id>/",
    views.detalle_resultado_usuario,
    name="detalle_resultado_usuario",
    ),

    path(
        "grupos-clasificaciones/",
        views.grupos_clasificaciones_usuario,
        name="grupos_clasificaciones_usuario",
    ),


    path(
        "mis-equipos/<int:equipo_id>/",
        views.ver_equipo,
        name="ver_equipo"
    ),

    path(
        "mis-inscripciones/editar/<int:inscripcion_id>/",
        views.editar_inscripcion,
        name="editar_inscripcion"
    ),

    path(
        "mis-inscripciones/<int:inscripcion_id>/editar/agregar-integrante/",
        views.agregar_integrante_edicion,
        name="agregar_integrante_edicion"
    ),

    path(
        "mis-inscripciones/<int:inscripcion_id>/editar/eliminar-integrante/<int:integrante_id>/",
        views.eliminar_integrante_edicion,
        name="eliminar_integrante_edicion"
    ),

    path(
        "mis-inscripciones/eliminar/<int:inscripcion_id>/",
        views.eliminar_inscripcion,
        name="eliminar_inscripcion"
    ),


    # =====================================================
    # PANEL ADMINISTRATIVO
    # =====================================================

    path(
        "admin/",
        views.admin_dashboard,
        name="admin_dashboard"
    ),


    # =====================================================
    # EQUIPOS - ADMINISTRADOR
    # =====================================================

    path(
        "admin/equipos/",
        views.equipos_admin,
        name="equipos_admin"
    ),

    path(
        "admin/equipos/torneo/<int:torneo_id>/",
        views.equipos_torneo_admin,
        name="equipos_torneo_admin"
    ),

    path(
        "admin/equipos/<int:inscripcion_id>/",
        views.ver_equipo_admin,
        name="ver_equipo_admin"
    ),


    # =====================================================
    # CRUD DE USUARIOS - ADMIN
    # =====================================================

    # Lista de usuarios

    path(
        "admin/usuarios/",
        views.usuarios_admin,
        name="usuarios_admin"
    ),

    # Crear usuario

    path(
        "admin/usuarios/crear/",
        views.crear_usuario_admin,
        name="crear_usuario_admin"
    ),

    # Ver usuario

    path(
        "admin/usuarios/<int:usuario_id>/",
        views.ver_usuario_admin,
        name="ver_usuario_admin"
    ),

    # Editar usuario

    path(
        "admin/usuarios/<int:usuario_id>/editar/",
        views.editar_usuario_admin,
        name="editar_usuario_admin"
    ),

    # Eliminar usuario

    path(
        "admin/usuarios/<int:usuario_id>/eliminar/",
        views.eliminar_usuario_admin,
        name="eliminar_usuario_admin"
    ),

    # Reactivar usuario
    path(
        "admin/usuarios/<int:usuario_id>/reactivar/",
        views.reactivar_usuario_admin,
        name="reactivar_usuario_admin"
    ),


    # =====================================================
    # CRUD DE TORNEOS - ADMIN
    # =====================================================

    # Lista de torneos

    path(
        "admin/torneos/",
        views.torneos_admin,
        name="torneos_admin"
    ),

    # Crear torneo

    path(
        "admin/torneos/crear/",
        views.crear_torneo,
        name="crear_torneo"
    ),

    # Ver torneo

    path(
        "admin/torneos/<int:torneo_id>/",
        views.ver_torneo_admin,
        name="ver_torneo_admin"
    ),

    # Editar torneo

    path(
        "admin/torneos/<int:torneo_id>/editar/",
        views.editar_torneo,
        name="editar_torneo"
    ),

    # Eliminar torneo

    path(
        "admin/torneos/<int:torneo_id>/eliminar/",
        views.eliminar_torneo,
        name="eliminar_torneo"
    ),


    # =====================================================
    # CONFIGURACIÓN DE INSCRIPCIONES - ADMIN
    # =====================================================

    # Lista de configuraciones

    path(
        "admin/inscripciones/",
        views.inscripciones_admin,
        name="inscripciones_admin"
    ),

    # Configurar inscripciones

    path(
        "admin/inscripciones/configurar/",
        views.configurar_inscripciones,
        name="configurar_inscripciones"
    ),

    # Abrir inscripciones

    path(
        "admin/inscripciones/<int:configuracion_id>/abrir/",
        views.abrir_inscripciones,
        name="abrir_inscripciones"
    ),

    # Cerrar inscripciones

    path(
        "admin/inscripciones/<int:configuracion_id>/cerrar/",
        views.cerrar_inscripciones,
        name="cerrar_inscripciones"
    ),

    # Editar configuración

    path(
        "admin/inscripciones/<int:configuracion_id>/editar/",
        views.editar_configuracion_inscripcion,
        name="editar_configuracion_inscripcion"
    ),

    # Eliminar configuración

    path(
        "admin/inscripciones/<int:configuracion_id>/eliminar/",
        views.eliminar_configuracion_inscripcion,
        name="eliminar_configuracion_inscripcion"
    ),


    # =====================================================
    # CONFIGURACIÓN DE COMPETICIÓN - ADMIN
    # =====================================================

    path(
        "admin/competicion/",
        views.configuraciones_competicion,
        name="configuraciones_competicion"
    ),

    path(
        "admin/competicion/<int:configuracion_id>/",
        views.ver_configuracion_competicion,
        name="ver_configuracion_competicion"
    ),

    path(
        "admin/competicion/<int:configuracion_id>/editar/",
        views.editar_configuracion_competicion,
        name="editar_configuracion_competicion"
    ),

    path(
        "admin/competicion/<int:configuracion_id>/sorteo/",
        views.realizar_sorteo,
        name="realizar_sorteo"
    ),

    path(
        "admin/competicion/<int:configuracion_id>/grupos/",
        views.ver_grupos_competicion,
        name="ver_grupos_competicion"
    ),

    path(
        "admin/competicion/<int:configuracion_id>/generar-partidos/",
        views.generar_partidos,
        name="generar_partidos"
    ),

    path(
    "admin/competicion/partidos/",
    views.partidos_torneos_admin,
    name="partidos_torneos_admin"
    ),

    path(
        "admin/competicion/<int:torneo_id>/partidos/",
        views.partidos_admin,
        name="partidos_admin"
    ),

    path(
        "admin/competicion/partido/<int:partido_id>/programar/",
        views.programar_partido,
        name="programar_partido"
    ),

    path(
        "admin/competicion/partido/<int:partido_id>/resultado/",
        views.registrar_resultado,
        name="registrar_resultado"
    ),

    path(
        "admin/competicion/configurar/",
        views.configurar_competicion,
        name="configurar_competicion"
    ),

    # =====================================================
    # GRUPOS - ADMIN
    # =====================================================

    path(
        "admin/grupos/",
        views.grupos_admin,
        name="grupos_admin"
    ),

    path(
        "admin/grupos/<int:configuracion_id>/",
        views.grupos_torneo_admin,
        name="grupos_torneo_admin"
    ),


    # =====================================================
    # INSCRIPCIONES DE EQUIPOS - ADMIN
    # =====================================================

    # Lista de inscripciones de equipos

    path(
        "admin/inscripciones-equipos/",
        views.inscripciones_equipos_admin,
        name="inscripciones_equipos_admin"
    ),

    # Aceptar inscripción

    path(
        "admin/inscripciones-equipos/<int:inscripcion_id>/aceptar/",
        views.aceptar_inscripcion,
        name="aceptar_inscripcion"
    ),

    # Rechazar inscripción

    path(
        "admin/inscripciones-equipos/<int:inscripcion_id>/rechazar/",
        views.rechazar_inscripcion,
        name="rechazar_inscripcion"
    ),

    path(
        "admin/competicion/resultados/",
        views.resultados_admin,
        name="resultados_admin"
    ),

    path(
    "admin/competicion/resultados/<int:partido_id>/",
    views.detalle_resultado_admin,
    name="detalle_resultado_admin",
    ),

]
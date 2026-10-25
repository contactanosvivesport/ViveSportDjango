
from django.db import models, transaction
from django.core.exceptions import ValidationError

from .models import (
    ConfiguracionCompeticion,
    FaseTorneo,
    Grupo,
    Equipo,
    Partido,
)


TIPOS_SIGUIENTE_FASE = {
    "cuartos": "semifinal",
    "semifinal": "final",
}


NOMBRES_FASES = {
    "cuartos": "Cuartos de final",
    "semifinal": "Semifinales",
    "final": "Final",
}

def activar_fase(fase):
    """
    Deja activa únicamente la fase indicada del torneo.
    """
    FaseTorneo.objects.filter(
        torneo=fase.torneo,
        activa=True,
    ).exclude(
        id=fase.id
    ).update(
        activa=False
    )

    if not fase.activa:
        fase.activa = True
        fase.save(update_fields=["activa"])

        
def obtener_clasificacion_grupo(grupo):
    """
    Calcula la clasificación de un grupo siguiendo los criterios
    utilizados en grupos_torneo_admin.
    """

    equipos = (
        Equipo.objects
        .filter(grupos_asignados__grupo=grupo)
        .distinct()
        .order_by("nombre")
    )

    clasificacion = []

    for equipo in equipos:
        partidos = (
            Partido.objects
            .filter(grupo=grupo, estado="jugado")
            .filter(
                models.Q(equipo_local=equipo)
                | models.Q(equipo_visitante=equipo)
            )
            .select_related("resultado")
            .prefetch_related("tarjetas")
        )

        pj = pg = pe = pp = 0
        gf = gc = puntos = juego_limpio = 0

        for partido in partidos:
            if not hasattr(partido, "resultado"):
                continue

            resultado = partido.resultado
            local = resultado.marcador_local
            visitante = resultado.marcador_visitante

            pj += 1

            if partido.equipo_local_id == equipo.id:
                gf += local
                gc += visitante

                if local > visitante:
                    pg += 1
                    puntos += 3
                elif local == visitante:
                    pe += 1
                    puntos += 1
                else:
                    pp += 1
            else:
                gf += visitante
                gc += local

                if visitante > local:
                    pg += 1
                    puntos += 3
                elif visitante == local:
                    pe += 1
                    puntos += 1
                else:
                    pp += 1

            for tarjeta in partido.tarjetas.filter(equipo=equipo):
                juego_limpio += tarjeta.penalizacion_juego_limpio

        clasificacion.append({
            "equipo": equipo,
            "pj": pj,
            "pg": pg,
            "pe": pe,
            "pp": pp,
            "gf": gf,
            "gc": gc,
            "dg": gf - gc,
            "puntos": puntos,
            "juego_limpio": juego_limpio,
        })

    clasificacion.sort(
        key=lambda item: (
            -item["puntos"],
            -item["juego_limpio"],
            -item["dg"],
            -item["gf"],
        )
    )

    # Desempate por enfrentamiento directo, igual que la tabla actual.
    i = 0

    while i < len(clasificacion):
        j = i + 1

        while j < len(clasificacion):
            primero = clasificacion[i]
            siguiente = clasificacion[j]

            empatados = (
                siguiente["puntos"] == primero["puntos"]
                and siguiente["juego_limpio"] == primero["juego_limpio"]
                and siguiente["dg"] == primero["dg"]
                and siguiente["gf"] == primero["gf"]
            )

            if not empatados:
                break

            j += 1

        if j - i > 1:
            bloque = clasificacion[i:j]
            ids = [item["equipo"].id for item in bloque]

            datos_directos = {
                equipo_id: {"puntos": 0, "dg": 0, "gf": 0}
                for equipo_id in ids
            }

            enfrentamientos = (
                Partido.objects
                .filter(grupo=grupo, estado="jugado")
                .filter(
                    models.Q(equipo_local_id__in=ids)
                    | models.Q(equipo_visitante_id__in=ids)
                )
                .select_related("resultado")
            )

            for partido in enfrentamientos:
                if not hasattr(partido, "resultado"):
                    continue

                local_id = partido.equipo_local_id
                visitante_id = partido.equipo_visitante_id

                if local_id not in ids or visitante_id not in ids:
                    continue

                local = partido.resultado.marcador_local
                visitante = partido.resultado.marcador_visitante

                datos_directos[local_id]["gf"] += local
                datos_directos[local_id]["dg"] += local - visitante

                datos_directos[visitante_id]["gf"] += visitante
                datos_directos[visitante_id]["dg"] += visitante - local

                if local > visitante:
                    datos_directos[local_id]["puntos"] += 3
                elif visitante > local:
                    datos_directos[visitante_id]["puntos"] += 3
                else:
                    datos_directos[local_id]["puntos"] += 1
                    datos_directos[visitante_id]["puntos"] += 1

            bloque.sort(
                key=lambda item: (
                    -datos_directos[item["equipo"].id]["puntos"],
                    -datos_directos[item["equipo"].id]["dg"],
                    -datos_directos[item["equipo"].id]["gf"],
                    item["equipo"].id,
                )
            )

            clasificacion[i:j] = bloque

        i = j

    for posicion, item in enumerate(clasificacion, start=1):
        item["posicion"] = posicion

    return clasificacion


def fase_completa(fase):
    partidos = Partido.objects.filter(fase=fase)

    if not partidos.exists():
        return False

    for partido in partidos:
        if partido.estado != "jugado":
            return False

        if not hasattr(partido, "resultado"):
            return False

        if (
            partido.resultado.marcador_local
            == partido.resultado.marcador_visitante
        ):
            return False

    return True


def ganador_partido(partido):
    if not hasattr(partido, "resultado"):
        return None

    resultado = partido.resultado

    if resultado.marcador_local > resultado.marcador_visitante:
        return partido.equipo_local

    if resultado.marcador_visitante > resultado.marcador_local:
        return partido.equipo_visitante

    return None


@transaction.atomic
def procesar_progresion_torneo(torneo):
    """
    Genera las rondas eliminatorias cuando la fase anterior
    se ha completado. Devuelve el tipo de fase recién creada
    o None si no hay una nueva fase que generar.
    """

    configuracion = (
        ConfiguracionCompeticion.objects
        .filter(torneo=torneo, sorteo_realizado=True)
        .first()
    )

    if not configuracion:
        return None

    total_clasifican = configuracion.equipos_clasifican
    cantidad_grupos = configuracion.cantidad_grupos

    if (
        total_clasifican < 2
        or total_clasifican > 8
        or total_clasifican % cantidad_grupos != 0
    ):
        return None

    fase_grupos = (
        FaseTorneo.objects
        .filter(torneo=torneo, tipo="grupos")
        .first()
    )

    if not fase_grupos:
        return None

    grupos = list(
        Grupo.objects
        .filter(fase=fase_grupos)
        .order_by("numero")
    )

    if len(grupos) != cantidad_grupos:
        return None

    # Primera ronda: solo cuando todos los partidos de grupos
    # están jugados y tienen resultado.
    partidos_grupos = Partido.objects.filter(
        fase=fase_grupos,
        grupo__isnull=False,
    )

    if not partidos_grupos.exists():
        return None

    if partidos_grupos.filter(estado__in=["pendiente", "programado"]).exists():
        return None

    if partidos_grupos.filter(estado="cancelado").exists():
        return None

    if any(
        not hasattr(partido, "resultado")
        for partido in partidos_grupos
    ):
        return None

    # Si ya se generó una fase eliminatoria inicial, no duplicarla.
    tipos_iniciales = {
        2: "final",
        4: "semifinal",
        8: "cuartos",
    }

    tipo_inicial = tipos_iniciales.get(total_clasifican)

    if not tipo_inicial:
        return None

    fase_existente = FaseTorneo.objects.filter(
        torneo=torneo,
        tipo=tipo_inicial,
    ).first()

    if fase_existente:
        fase_actual = fase_existente

        # No activar una fase que ya terminó.
        if not fase_completa(fase_actual):
            activar_fase(fase_actual)
    else:
        por_grupo = total_clasifican // cantidad_grupos
        clasificados_por_grupo = []

        for grupo in grupos:
            tabla = obtener_clasificacion_grupo(grupo)

            if len(tabla) < por_grupo:
                return None

            clasificados_por_grupo.append(
                [item["equipo"] for item in tabla[:por_grupo]]
            )

        # Intercalar posiciones de los grupos para formar cruces.
        clasificados = []

        for posicion in range(por_grupo):
            for lista in clasificados_por_grupo:
                clasificados.append(lista[posicion])

        if len(clasificados) != total_clasifican:
            return None

        orden = (
            FaseTorneo.objects
            .filter(torneo=torneo)
            .order_by("-orden")
            .values_list("orden", flat=True)
            .first()
            or 1
        ) + 1

        fase_actual = FaseTorneo.objects.create(
            torneo=torneo,
            nombre=NOMBRES_FASES[tipo_inicial],
            tipo=tipo_inicial,
            orden=orden,
            activa=True,
            creada_automaticamente=True,
        )

        activar_fase(fase_actual)

        numero = (
            Partido.objects
            .filter(torneo=torneo)
            .order_by("-numero")
            .values_list("numero", flat=True)
            .first()
            or 0
        ) + 1

        for indice in range(total_clasifican // 2):
            local = clasificados[indice]
            visitante = clasificados[total_clasifican - 1 - indice]

            Partido.objects.create(
                torneo=torneo,
                fase=fase_actual,
                grupo=None,
                numero=numero,
                equipo_local=local,
                equipo_visitante=visitante,
                estado="pendiente",
            )
            numero += 1

        return tipo_inicial

    # Si ya existe la fase inicial, solo avanzar si está completa.
    while fase_actual.tipo in TIPOS_SIGUIENTE_FASE:
        if not fase_completa(fase_actual):
            return None

        siguiente_tipo = TIPOS_SIGUIENTE_FASE[fase_actual.tipo]

        fase_siguiente = FaseTorneo.objects.filter(
            torneo=torneo,
            tipo=siguiente_tipo,
        ).first()

        if fase_siguiente:
            fase_actual = fase_siguiente

            if not fase_completa(fase_actual):
                activar_fase(fase_actual)

            continue

        partidos_actuales = list(
            Partido.objects
            .filter(fase=fase_actual)
            .order_by("numero")
        )

        ganadores = [ganador_partido(partido) for partido in partidos_actuales]

        if not ganadores or any(ganador is None for ganador in ganadores):
            return None

        if len(ganadores) % 2 != 0:
            return None

        orden = fase_actual.orden + 1

        fase_siguiente = FaseTorneo.objects.create(
            torneo=torneo,
            nombre=NOMBRES_FASES[siguiente_tipo],
            tipo=siguiente_tipo,
            orden=orden,
            activa=True,
            creada_automaticamente=True,
        )
        
        activar_fase(fase_siguiente)

        numero = (
            Partido.objects
            .filter(torneo=torneo)
            .order_by("-numero")
            .values_list("numero", flat=True)
            .first()
            or 0
        ) + 1

        for indice in range(0, len(ganadores), 2):
            Partido.objects.create(
                torneo=torneo,
                fase=fase_siguiente,
                grupo=None,
                numero=numero,
                equipo_local=ganadores[indice],
                equipo_visitante=ganadores[indice + 1],
                partido_origen_local=partidos_actuales[indice],
                partido_origen_visitante=partidos_actuales[indice + 1],
                estado="pendiente",
            )
            numero += 1

        return siguiente_tipo

    return None

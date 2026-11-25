"""Suggest a Line World composition from the viewer's question and optional records.

Runs offline with Python 3.10+. The intent names are stable keys for other skills.
"""
import argparse
import csv
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Choice:
    target: str
    why: str
    anchor: str
    motion: str
    # Each expression describes one necessary signal. A generic noun alone
    # never identifies a specialised diagram (e.g. "GPU", "datos" or "capas").
    cues: tuple


CHOICES = {
    "object-route": Choice("object-route",
        "El recorrido identifica dónde se encuentra el mismo objeto en cada visita.",
        "Cada estación conserva su posición y el objeto lleva consigo el nombre de la fuente.",
        "Acompaña el objeto hasta la siguiente parada. Sostén su llegada y vuelve a la estación original si se repite.",
        (r"sigue\w*|seguir|rastre\w*|track\w*|follow\w*|viaja\w*|visita\w*|recorr\w*|returns?|regres\w*|travels?|visits?|itinerar\w*",
         r"estaciones?|stations?|paradas?|stops?|waypoints?|ida y vuelta|round trip|regres\w* al?\b|returns? to|vuelve al?\b")),
    "pivot-rotation": Choice("pivot-rotation",
        "Una marca gira a distancia constante de un centro fijo.",
        "El pivote, la longitud del radio y la referencia angular permanecen fijos.",
        "Fija el pivote y la referencia de partida. Gira el brazo y traza el arco hasta completar el ángulo indicado.",
        (r"gir\w*|rot\w*|orbit\w*|barre\w*|barrido|arcos?|arcs?|sweeps?|sweeping|turns?|turning|revolv\w*",
         r"pivots?|pivotes?|radius|radii|radios?|ejes?|axis|axle|hinges?|bisagras?|compas|compass|"
         r"brazo|arm|centro fijo|punto fijo|fixed (?:center|centre|point|pin)|clockwise|horario|aguja|needle")),
    "rigid-rearrangement": Choice("rigid-rearrangement",
        "Se puede comprobar una superficie siguiendo las mismas piezas al reordenarlas.",
        "La unidad de longitud, la escala y las dimensiones de cada pieza permanecen fijas.",
        "Deja reconocible la figura inicial, traslada las piezas y sostén el contorno final junto al área.",
        (r"rectang\w*|losetas?|tiles?", r"reorden\w*|reacomod\w*|rearrang\w*|corta\w*|cut|cuts|cortar", r"area|superficie|cartulina|area conserved")),
    "contact-transfer": Choice("contact-transfer",
        "Un movimiento se transmite por contacto y deja un efecto observable.",
        "El material y el punto de contacto permanecen identificables.",
        "Sigue la pieza impulsada. Revela el efecto al hacer contacto y conserva el resultado al soltar.",
        (r"empuj\w*|presion\w*|press\w*|push\w*", r"marca|relieve|huella|desplaz\w*|imprint\w*|displac\w*")),
    "trajectory-trace": Choice("trajectory-trace",
        "El público debe reconocer cómo la altura de un objeto produce una traza en el tiempo.",
        "La posición y la gráfica comparten la misma altura y el mismo instante.",
        "Sigue el móvil en el plano y prolonga su gráfica con las mismas muestras temporales.",
        (r"trayectori\w*|trajector\w*|movil|moving point|recorrido|motion path|oscilador|oscillator",
         r"traza|trace|grafica|graph|plot|altura en el tiempo|height over time")),
    "interval-refinement": Choice("interval-refinement",
        "Una sucesión de límites acota la misma magnitud con más precisión.",
        "El intervalo inicial y la posición de la ventana ampliada sobre esa escala.",
        "Selecciona el subintervalo y amplíalo antes de presentar el siguiente.",
        (r"intervalos?|intervals?|rangos?|ranges?|tramos?|bounds?", r"anidad\w*|nested|estrech\w*|refin\w*|narrow\w*|acotar|bisec\w*")),
    "pack-fields": Choice("field-packing",
        "Varios campos ocupan posiciones identificables dentro de una estructura.",
        "El emisor, el orden de los campos y las celdas de relleno.",
        "Lleva copias de cada campo a su destino y revela el resultado al completar la cuadrícula.",
        (r"campos?|fields?|bytes?", r"empaquet\w*|empac\w*|pack\w*|memoria|memory|buffer|alineamiento|padding")),
    "preview-layers": Choice("layer-preview",
        "Cada capa aporta un efecto visible a un mismo resultado.",
        "La base y el encuadre de la vista previa.",
        "Abre espacio entre base y cabecera. Añade capas y actualiza la vista al llegar cada una.",
        (r"capas?|layers?|filtros?|filters?", r"vista previa|preview|resultado|result|image|imagen|apariencia|appearance")),
    "extract-layer": Choice("isometric-layers",
        "Una pieza debe reconocerse mientras se separa de un conjunto apilado.",
        "La cara rotulada, la orientación de la pieza y el soporte de destino.",
        "Muestra el soporte antes de trasladar la pieza superior.",
        (r"pila|apilad\w*|stack\w*|isometric\w*|capas?|layers?", r"extra\w*|sac[ar]\w*|separ\w*|desprend\w*|retir\w*|lift\w*|detach\w*|remov\w*|pull\w*")),
    "ordered-passes": Choice("pass-strip",
        "Un orden de operaciones produce un único resultado.",
        "El resultado, el orden de las llamadas y el destino de la tira.",
        "Haz corresponder cada llamada con un nuevo segmento y cierra con un solo envío.",
        (r"pasos?|etapas?|pipeline|secuencia|operaciones|llamadas|steps?|stages?|calls?|passes|operations",
         r"unico envio|solo envio|un solo resultado|un resultado|resultado final|mismo fotograma|single (?:submit|output|frame)|one (?:submit|result|output)|final result")),
    "inspect-item": Choice("module-transfer",
        "El público necesita reconocer de qué lista salió el elemento que ahora inspecciona.",
        "El hueco de origen, los vecinos y el nombre de la pieza.",
        "Traslada una fila al inspector y muestra sus entradas y salidas al llegar.",
        (r"lista|list|fila|row|inventario|inventory|catalogo|catalog|registro|record|modulo|module",
         r"inspect\w*|inspeccion\w*|detalle|detail|puertos?|ports?|entradas y salidas|inputs and outputs|hueco|ranura|slot")),
    "map-points": Choice("vertex-remap",
        "Se debe seguir la misma muestra al cambiar de representación geométrica.",
        "La identidad de cada muestra y su destino antes de dibujar caras.",
        "Mueve los puntos desde la retícula hasta la superficie y después dibuja la malla.",
        (r"puntos?|points?|vertices|reticula|grid|uv", r"superficie|surface|malla|mesh|remap\w*|geometr\w*")),
    "overlapping-subsets": Choice("import-footprint",
        "Se comparan subconjuntos identificables dentro de un mismo universo.",
        "El total, la unidad y el índice de cada celda.",
        "Alterna el subconjunto resaltado sobre la cuadrícula fija. Conserva las celdas compartidas.",
        (r"subconjuntos?|subsets?|grupos?|groups?|modulos?|modules?|segmentos?|segments?",
         r"solap\w*|superpuest\w*|overlap\w*|interseccion\w*|shared cells|celdas compartidas|huella|footprint")),
    "compare-lanes": Choice("command-lanes",
        "Se comparan duraciones de operaciones que llegan a un mismo destino.",
        "El borde de llegada y la posición de los carriles que permanecen iguales.",
        "Abre el contexto desde una llamada y modifica únicamente la barra de la variante.",
        (r"carriles?|lanes?|llamadas?|calls?|comandos?|commands?|pases|passes",
         r"duraci\w*|duration\w*|dur[oa]|duraron|duraban?|duran|last(?:s|ed)?|took|take[sn]?|latenc\w*|tarda\w*|tiempos?|timings?|coste|cost|faster|rapido")),
    "shared-resource": Choice("shared-host",
        "Dos consumidores usan una misma entidad a través de interfaces reconocibles.",
        "La entidad central, sus puertos y la identidad de ambos extremos.",
        "Conecta primero un entorno y luego el otro. Conserva ambos enlaces al abrir las ramas.",
        (r"entornos?|hosts?|clientes?|clients?|procesos?|processes|adaptadores?|adapters?|servicios?|services?|aplicaciones|apps",
         r"compart\w*|shared?|sharing|mism[ao]|same resource|same scene|common resource")),
    "compare-clocks": Choice("split-clock",
        "Hay que distinguir qué trabajo se retrasa y qué cadencia permanece intacta.",
        "La escala común, los pulsos y las columnas que siguen alineadas.",
        "Alinea las dos pistas. Alarga la tarea afectada y conserva los pulsos de la otra.",
        (r"relojes?|clocks?|pistas?|tracks?|cadencia|cadence|ritmo|rhythm|hilos?|threads?|worker|pulsos?|pulses",
         r"retras\w*|delay\w*|alarg\w*|late|overrun\w*|sincroni\w*|synchron\w*|dos relojes|two clocks|pierde un turno|skip\w*")),
    "ring-handoff": Choice("ring-handoff",
        "Al cambiar un miembro del anillo, interesa ver qué claves cambian de propietario.",
        "La posición de las claves, los nodos que permanecen y el sentido de recorrido.",
        "Sitúa los propietarios, incorpora el nuevo nodo y sigue el intervalo que cambia de destino.",
        (r"anillo|ring|hash(?:ing)? (?:consistente|circular)|consistent hash(?:ing)?",
         r"claves?|keys?|reasign\w*|remap\w*|transfer\w*|handoff|propietari\w*|owner\w*|redistrib\w*")),
    "bit-probe": Choice("bit-probe",
        "La consulta depende del estado de las posiciones que un conjunto de funciones selecciona.",
        "Los índices de una única fila de bits y la identidad de cada consulta.",
        "Sigue las proyecciones hasta sus índices, enciende los bits de inserción y comprueba las posiciones de la consulta.",
        (r"bloom|bits?|bitset|bitmaps?|mapa de bits|vector binario",
         r"hash\w*|pertenencia|consulta\w*|membership|probe\w*|query|queries|false positive|falso positivo")),
    "message-ladder": Choice("message-ladder",
        "Importa quién envía cada mensaje y en qué orden responde el otro extremo.",
        "Los dos interlocutores en sus columnas y el orden vertical de los mensajes.",
        "Traza cada flecha desde el emisor y revela su etiqueta antes del siguiente intercambio.",
        (r"mensajes?|messages?|peticion|request|handshake|saludo|negociacion|intercambio|exchange",
         r"respuestas?|repl(?:y|ies)|responses?|ida y vuelta|back and forth|altern\w*|handshake|negociacion|interlocutores|peers?|"
         r"cliente (?:y|al?) (?:el )?servidor|servidor (?:y|al?) (?:el )?cliente|"
         r"client (?:and|to) (?:the )?server|server (?:and|to) (?:the )?client|tls")),
    "detail-callout": Choice("detail-callout",
        "Para leer un elemento compuesto hay que ampliar sus partes sin perder de vista de dónde salió.",
        "El objeto de origen, el enlace al detalle y el orden de sus fragmentos.",
        "Amplía el detalle, identifica sus fragmentos por turno y vuelve al contexto con el conector visible.",
        (r"fragmentos?|fragments?|componentes?|components?|partes|parts|segmentos?|segments?|url|direccion|address",
         r"ampli\w*|agrand\w*|zoom\w*|magnif\w*|callout|desglos\w*|descompon\w*|break down|decompos\w*|annotat\w*|anot\w*")),
    "radix-ladder": Choice("radix-ladder",
        "Cada división produce un resto y leer esos restos al revés reconstruye la representación.",
        "Las columnas de cocientes y restos, la base y el orden inverso de lectura.",
        "Desciende por las divisiones, conserva cada resto en su fila y recoge los símbolos desde la última.",
        (r"base\s*(?:[2-9]|[1-5]\d|6[0-2])|radix|base numerica|number base|sistema de numeracion|positional notation",
         r"conver\w*|divis\w*|divide\w*|restos?|residuos?|remainders?|codific\w*|encod\w*")),
    "token-gate": Choice("token-gate",
        "Cada solicitud consume una unidad disponible o sigue la salida de rechazo.",
        "La reserva de fichas, el punto de decisión y los dos destinos.",
        "Muestra la reserva, pasa cada solicitud por la decisión y descuenta una ficha al admitirla.",
        (r"fichas?|tokens?|cubeta|bucket|reserva|quota|cupo",
         r"admit\w*|rechaz\w*|consum\w*|agota\w*|acept\w*|accept\w*|reject\w*|admis\w*|refill\w*|deny|denied|recarg\w*|rate limit\w*|limita\w*")),
    "resolution-fan": Choice("resolution-fan",
        "Un original genera versiones independientes con distintos tamaños de imagen.",
        "El origen único, la esquina común y el rótulo de cada versión.",
        "Abre las ramas desde la pieza original y revela los marcos de mayor a menor.",
        (r"resoluci\w*|resolutio\w*|calidades|video sizes",
         r"version\w*|variantes?|variants?|gener\w*|produc\w*|renditions?|transcod\w*|frames?|marcos?|escalon\w*")),
    "queue-router": Choice("queue-router",
        "Un criterio asigna cada entrada a una cola y un selector vuelve a reunir las salidas.",
        "El clasificador, la posición de cada cola y el punto común de salida.",
        "Abre los ramales, muestra las colas y sus criterios, y revela después el selector.",
        (r"colas?|queues?|bandejas?|worklists?",
         r"priorid\w*|priorit\w*|clasific\w*|classif\w*|despach\w*|dispatch\w*|enrut\w*|routing|route\w*|selector|schedul\w*")),
    "staged-network": Choice("staged-network",
        "El público debe seguir un recorrido mientras aparecen los componentes de una arquitectura.",
        "Las posiciones de los actores, los puertos de llegada y las conexiones ya explicadas.",
        "Introduce los componentes por etapas y traza la arista o el recorrido de la entidad activa.",
        (r"sistema|system|arquitectura|architecture|servidores?|servers?|nodos?|nodes?|componentes?|components?|servicios?|services?",
         r"por etapas|por turnos|paso a paso|step by step|in stages|in turn|progresiv\w*|progressiv\w*|recorrido|trace the path|recorre\w*|ruta de (?:una? )?(?:peticion|mensaje)|request path")),
    "compare-categories": Choice("data-chart",
        "Se comparan magnitudes de categorías con una medida y una unidad comunes.",
        "El cero, la escala, el orden de las categorías y la barra de referencia.",
        "Mantén visible la categoría de interés mientras entran sus pares. Conserva visibles los valores finales.",
        (r"ranking|ordenar|rank\w*|compar\w+|mayor|menor|largest|highest|smallest|lowest",
         r"categor\w*|region\w*|productos?|products?|tiendas?|stores?|sedes|ciudades|cities|paises|countries|departamentos?|departments?|grupos?|groups?")),
    "trend": Choice("time-series",
        "El espectador necesita leer cómo cambia una medida con el tiempo.",
        "El dominio temporal, la escala y los huecos de observaciones ausentes.",
        "Traza en orden temporal y destaca el instante mencionado conservando todo el contexto.",
        (r"tendencia\w*|trend\w*|evoluci\w*|over time|a lo largo del tiempo|serie temporal|time series|mes a mes|month by month",)),
    "share": Choice("chart-ring",
        "Una parte tiene un denominador conocido y se puede expresar en el intervalo de 0 a 100 %.",
        "El valor, la etiqueta y el total de referencia.",
        "Mantén el porcentaje escrito y recorre el arco que representa esa fracción.",
        (r"cuota|fraccion|proporcion|porcentaje|parte|share|fraction|percentage|portion",
         r"(?:del|de un|of the|of a) (?:total|whole)|denominador|denominator|mercado|market|parte del todo")),
    "composition": Choice("part-to-whole",
        "Varias partes disjuntas deben leerse contra el mismo total.",
        "La unidad, el denominador y el color de cada parte.",
        "Presenta una barra apilada completa y destaca por turno la parte nombrada.",
        (r"distribu\w*|repart\w*|desglos\w*|composi\w*|breakdown|divid\w*|split",
         r"total|presupuesto|budget|whole")),
    "lookup": Choice("static-comparison",
        "La tarea consiste en leer valores o estados que conviene tener visibles a la vez.",
        "Las etiquetas, unidades, posiciones y cifras exactas.",
        "Mantén la tabla o las vistas alineadas. Deja tiempo para recorrerlas.",
        (r"valor(?:es)? exacto(?:s)?|cifras? exactas?|consultar (?:una |la )?cifra|consultar valores|cuanto (?:vendio|costo|gasto|facturo|registro)|how much did|lookup|look up|exact values?|exact numbers?|lado a lado|side by side",)),
    "paired-change": Choice("paired-change",
        "Se comparan dos mediciones de la misma entidad en condiciones identificadas.",
        "La escala compartida, las dos etiquetas de condición y la identidad de cada entidad.",
        "Muestra los dos extremos juntos y resalta la diferencia cuando se mencione.",
        (r"antes y despues|antes frente a despues|before and after|before versus after|pre y post|pre and post",)),
    "relationships": Choice("node-link",
        "Las conexiones explícitas entre entidades o dependencias son lo que el público necesita seguir.",
        "Los nodos, sus nombres y los puntos de conexión.",
        "Dispón primero los nodos y destaca la arista del paso que se explica.",
        (r"dependencias?|dependen(?:cia)? de|depende de|depends? on|dependenc(?:y|ies)|red de conexiones|network of connections|diagrama de flujo|flowchart|jerarquia|hierarchy",)),
    "correlation": Choice("scatter",
        "Se busca una asociación entre dos medidas emparejadas.",
        "Las escalas, sus unidades y la identidad de cada observación.",
        "Coloca un punto por observación y lleva la atención al par comentado.",
        (r"correla\w*|diagrama de dispersion|scatter\w*|asociacion entre dos medidas|relationship between two (?:measures|variables)",)),
    "distribution": Choice("distribution",
        "La pregunta se refiere a la dispersión o frecuencia de una medida.",
        "Los mismos intervalos y la unidad de observación.",
        "Conserva los intervalos y destaca un rango después de mostrar la distribución.",
        (r"histograma|histogram|percentil\w*|percentile\w*|distribucion de (?:frecuencias|edades|tiempos)|frequency distribution",)),
}
SPECIALISTS = {
    "time-series": "line-world-d3", "paired-change": "line-world-motion-direction", "scatter": "line-world-d3",
    "distribution": "line-world-d3", "part-to-whole": "line-world-d3", "node-link": "line-world-mermaid",
}
MISSING = {"", "n/a", "na", "null", "pendiente", "sin dato", "missing", "unknown"}
PERIOD = (r"tiempo|time|dias?|days?|mes(?:es)?|months?|anos?|years?|semanas?|weeks?|"
          r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|"
          r"january|february|march|april|may|june|july|august|september|october|november|december|(?:19|20)\d{2}")
MEASURE = (r"cuanto|cantidad|medicion|medidas?|measurements?|cifras?|valores?|importes?|ventas|ingresos|"
           r"visitas|duracion|latencia|tiempo de espera|numero|sales|revenue|visits|values?|wait time|amount|rates?|cost")
CHANGE = r"evolu\w*|cambi\w*|vari(?:a|o|an|aron)|chang\w*|varies|vary|grew|crecio|disminu\w*|aument\w*"
FIXED_EXAMPLES = {
    "field-packing": "El ejemplo asigna cuatro campos a una cuadrícula de 48 posiciones con relleno predefinido.",
    "layer-preview": "Los chips y los efectos sobre el pabellón ilustran una pila gráfica determinada.",
    "isometric-layers": "Las cinco losas y la trayectoria de la superior vienen dibujadas.",
    "module-transfer": "Se pueden elegir la fila, sus rótulos, sus entradas y sus salidas en la receta.",
    "vertex-remap": "El ejemplo proyecta 375 muestras y crea 672 triángulos de una superficie concreta.",
    "pass-strip": "El ejemplo contiene cuatro pases entre un encoder y un submit y usa una galería de arcos.",
    "import-footprint": "La receta admite un total, una unidad y tres listas de índices con solapamientos.",
    "command-lanes": "Las cuatro duraciones y el cambio de la segunda barra son proporciones fijas del ejemplo.",
    "shared-host": "Los dos adaptadores y los puertos root y surface tienen nombres y comportamientos técnicos.",
    "split-clock": "La plantilla incluye ocho pulsos y el retraso predeterminado de la cuarta tarea.",
}
SYSTEM_INPUTS = {
    "ring-handoff": "La receta admite los rótulos y la clave destacada (keyLabel). La geometría del anillo y la reasignación del ejemplo son fijas.",
    "bit-probe": "Indica la longitud del vector y tres grupos de índices reales en bits.size y bits.groups. El resultado se calcula a partir de las celdas.",
    "message-ladder": "Ordena de uno a seis mensajes por su secuencia registrada en exchanges y asigna a cada uno el índice del emisor, 0 o 1. El espaciado vertical codifica el orden.",
    "detail-callout": "Introduce cuatro fragmentos contiguos en parts, sus cuatro rótulos en labels y el nombre del detalle en focusLabel.",
    "radix-ladder": "Introduce el entero en value y una base de 2 a 62 en base. Los cocientes, restos y caracteres se calculan con esos datos.",
    "token-gate": "Indica cuántas fichas y solicitudes hay en tokens y requests. Cada admisión consume una ficha y la reserva se refleja en pantalla.",
    "resolution-fan": "Introduce el rótulo del original y los de sus siete versiones. Los marcos representan tamaños relativos predefinidos.",
    "queue-router": "La plantilla admite rótulos, una entrada (inputLabel) y hasta tres criterios (criteria). Las tres pilas dibujadas representan clases de prioridad.",
    "staged-network": "Describe nodos y aristas en nodes y edges. Indica identidades, coordenadas, conexiones y los intervalos de aparición o recorrido.",
}
# These cues identify a relationship within the staged layout. Source titles, anchors,
# scene IDs and timecodes come from the installed study and are never inferred from words.
STAGED_SCENE_CUES = {
    "M4lR_Va97cQ": (r"replicas?|replicaci\w*|replication",
                    r"balanceador\w*|load balancer|servicio de proximidad|location.based service|lecturas?|reads?",
                    r"primari[ao]|primary|escrituras?|writes?|busqueda local|nearby"),
    "UC5xf8FbdJc": (r"servidor(?:es)?|servers?|flota|fleet",
                    r"capacidad|capacity|qps|peticiones por segundo|requests per second",
                    r"cuantos?|how many|dimension\w*|flota|fleet|por servidor|per server|fleet size"),
    "7AMRfNKwuYo": (r"resoluciones|resolutions|versiones|versions|variantes|variants|renditions",
                    r"emision|stream\w*|transcod\w*|video",
                    r"pantallas?|screens?|dispositivos?|devices?|reproductores?|players?"),
    "EyMRZpgJUuc": (r"entrevistas?|interviews?|triptico|triptych|tarjetas?|cards?|panels?",
                    r"rondas|rounds|tres (?:tarjetas|paneles|categorias)|three (?:cards|panels|categories)|codigo y diseno|coding and design"),
    "i7twT3x5yv8": (r"chat|mensajeria|messaging|websockets?", r"clientes?|clients?",
                    r"conexi\w*|conect\w*|connect\w*|bidireccional\w*|bidirectional|websockets?|incorpor\w*|join\w*"),
    "4rLW7zg21gI": (r"hilos?|threads?", r"heap|memoria|memory|espacio de direcciones|address space",
                    r"compart\w*|shar\w*|mism[ao]|common|same"),
    "xbgzl2maQUU": (r"prefijos?|prefix(?:es)?|trie", r"arbol(?:es)?|trees?|trie|ramas?|branch\w*|autocomplet\w*"),
    "f6zXyq4VPP8": (r"bus|broker|intermediario|pub.sub", r"eventos?|events?|publicadores?|publishers?|productores?|producers?|subscribers?|suscriptores?"),
    "o-k7h2G3Gco": (r"hitos?|milestones?", r"cronolog\w*|timeline|linea (?:de|del) tiempo|eje|axis|fechas?|dates?|temporal|hoja de ruta|roadmap"),
    "wAMc7NyL4tQ": (r"categorias?|categor(?:y|ies)|parent category", r"recursos?|resources?",
                    r"hij[oa]s?|children|ramas?|branch\w*|agrup\w*|groups?|contiene|contains?|tres|three|desglos\w*"),
    "Dwt8R0KPu7k": (r"claves?|keys?", r"hash\w*|sharding",
                    r"modul[ou]s?|remainder|resto|shards?|particion\w*|partitions?|fragmentos?"),
    "okrR1KXNLtA": (r"mensajes?|messages?|notificaci(?:on|ones)|notifications?|envio|broadcast",
                    r"destinatarios?|recipients?|receptores?|receivers?|grupo|group|audiencia|audience|clientes|clients|usuarios|users",
                    r"difus\w*|broadcast\w*|fan.out|multicast|multiples?|muchos|many|todos|everyone|all|varios|several"),
}
STUDY_RECIPE = "assets/diagramas-bytebytego.json"
STILL = r"sin (?:animaci[oó]n|movimiento)|sin animar|estatic[oa]s?|motionless|static|without (?:motion|animation)|no animation|reduced motion|movimiento reducido"


def normalize(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def match(pattern, text):
    return re.search(r"\b(?:" + pattern + r")\b", text)


@lru_cache(maxsize=1)
def sources():
    doc = json.loads((ROOT / "references" / "patterns.json").read_text(encoding="utf-8-sig"))
    return {row["id"]: row["sources"][0]["url"] for row in doc["patterns"] if row.get("sources")}


@lru_cache(maxsize=1)
def systems_study():
    return json.loads((ROOT / "references/bytebytego-corpus.json").read_text(encoding="utf-8-sig"))


def staged_scenes(text):
    if not text:
        return []
    matches = []
    group_delivery = match(r"mensajes?|messages?|notificaci(?:on|ones)|notifications?", text) and match(
        r"recib\w* (?:el|un) grupo|(?:grupo(?: de chat)?|(?:chat )?group(?: chat)?) (?:recib\w*|receiv\w*|gets?)|"
        r"(?:al|a (?:un|todo el|cada)) grupo|to (?:a |the |every )?(?:group chat|chat group|group of (?:users|recipients))", text)
    for scene in systems_study()["videos"]:
        cues = STAGED_SCENE_CUES.get(scene["video_id"])
        if scene["artifact"] != "staged-network" or not cues:
            continue
        chat_fanout = scene["video_id"] == "okrR1KXNLtA" and (group_delivery or match(
            r"(?:chat|message|notification) fan.out|fan.out (?:de |del |en |for )?(?:chat|mensajes?|notificaciones?)", text))
        if chat_fanout or all(match(cue, text) for cue in cues):
            matches.append(scene)
    return matches


def number_value(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    if isinstance(value, str):
        value = value.strip()
        if re.fullmatch(r"[+-]?\d+,\d+", value):
            value = value.replace(",", ".")
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, OverflowError):
        return None


def numeric(value):
    return number_value(value) is not None


def date_value(value):
    if not isinstance(value, str):
        return False
    # Unambiguous ISO dates and calendar months. A string of digits can be an ID.
    if not re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", value):
        return False
    try:
        date.fromisoformat(value + "-01" if len(value) == 7 else value)
        return True
    except ValueError:
        return False


def read_records(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if path.suffix.lower() == ".json":
            rows = json.load(stream)
        elif path.suffix.lower() == ".csv":
            sample = stream.read(8192)
            stream.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(stream, dialect=dialect)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError("La tabla requiere una cabecera con nombres únicos.")
            rows = list(reader)
        else:
            raise ValueError("Usa una tabla CSV o un JSON con una lista de registros.")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("El JSON debe contener una lista de registros.")
    if any(not isinstance(k, str) or not k.strip() or isinstance(v, (dict, list))
           for row in rows for k, v in row.items()):
        raise ValueError("Cada registro requiere columnas con nombre y valores escalares.")
    return rows


def profile_rows(rows):
    fields = {"row_count": len(rows), "dates": [], "measures": [], "categories": [], "identifiers": [],
              "denominators": [], "percentages": [], "units": [], "out_of_range_percentages": [],
              "missing": {}, "distinct": {}}
    for key in dict.fromkeys(k for row in rows for k in row):
        values = [row[key] for row in rows if key in row and row[key] is not None and str(row[key]).strip().casefold() not in MISSING]
        fields["distinct"][key] = len(set(values))
        if len(values) < len(rows):
            fields["missing"][key] = len(rows) - len(values)
        if not values:
            continue
        name = normalize(key).strip().replace("_", " ").replace("-", " ")
        if match(r"unidad(?:es)?|units?", name) and all(isinstance(v, str) and not numeric(v) for v in values):
            kind = "units"
        elif match(r"denominador|denominator|poblacion base|base population", name):
            kind = "denominators"
        elif match(r"id|uuid|sku|codigo|code|identificador|identifier|postal|zip", name):
            kind = "identifiers"
        elif all(date_value(v) for v in values) or (
            match(r"ano|year", name) and all(re.fullmatch(r"(?:19|20|21)\d\d", str(v)) for v in values)
        ):
            kind = "dates"
        elif all(isinstance(v, str) and v.strip().endswith("%") and numeric(v.strip()[:-1]) for v in values):
            kind = "measures"
            fields["percentages"].append(key)
            if any(not 0 <= number_value(v.strip()[:-1]) <= 100 for v in values):
                fields["out_of_range_percentages"].append(key)
        elif all(numeric(value) for value in values):
            kind = "measures"
            if match(r"porcentaje|percent(?:age)?|pct", name) or "%" in key:
                fields["percentages"].append(key)
                if any(not 0 <= number_value(v) <= 100 for v in values):
                    fields["out_of_range_percentages"].append(key)
        else:
            kind = "categories"
        fields[kind].append(key)
    return fields


def comparable_categories(rows, profile, text):
    def relevant(fields):
        mentioned = [name for name in fields if match(re.escape(normalize(name)) + r"(?:s|es)?", text)]
        return mentioned or fields

    for category in relevant(profile["categories"]):
        for measure in relevant(profile["measures"]):
            seen = set()
            for row in rows:
                group, value = row.get(category), row.get(measure)
                if group is None or str(group).strip().casefold() in MISSING:
                    continue
                if isinstance(value, str):
                    value = value.strip().removesuffix("%")
                if numeric(value):
                    seen.add(group)
                    if len(seen) >= 2:
                        return True
    return False


def edge_list_intent(rows):
    """Recognize only explicit endpoints. Two rows of unrelated nouns are insufficient."""
    names = {normalize(key).strip(): key for row in rows for key in row}
    for left, right in (("from", "to"), ("source", "target"), ("origen", "destino"),
                        ("sender", "receiver"), ("emisor", "receptor")):
        if left not in names or right not in names:
            continue
        pairs = [(row.get(names[left]), row.get(names[right])) for row in rows]
        if not all(a is not None and b is not None and a != b and
                   all(str(v).strip().casefold() not in MISSING for v in (a, b)) for a, b in pairs):
            continue
        order = next((names[k] for k in ("order", "orden", "sequence", "secuencia") if k in names), None)
        messages = any(k in names and all(str(row.get(names[k]) or "").strip() for row in rows)
                       for k in ("mensaje", "message"))
        order_values = [number_value(row.get(order)) for row in rows] if order else []
        if (messages and len(rows) <= 6 and len(set(v for pair in pairs for v in pair)) == 2
                and len(set(pairs)) == 2 and order_values and None not in order_values
                and len(set(order_values)) == len(rows)):
            return {"message-ladder": "La tabla identifica dos interlocutores, mensajes en ambos sentidos y su orden."}
        return {"relationships": f"Las columnas {names[left]} y {names[right]} identifican los extremos de cada conexión."}
    return {}


def structural_hints(profile, rows):
    hints = {}
    if not profile or profile["row_count"] < 2:
        return hints
    edges = edge_list_intent(rows)
    if edges:
        return edges
    columns = {normalize(k).strip(): k for k in profile["distinct"]}
    def column(*aliases):
        return next((columns[a] for a in aliases if a in columns), None)
    clock = column("t","tiempo","time")
    if clock and "x" in columns and "y" in columns:
        points = [tuple(number_value(r.get(k)) for k in (clock,columns["x"],columns["y"])) for r in rows]
        if all(None not in p for p in points) and len({p[0] for p in points}) == len(points):
            return {"trajectory-trace":"Las dos coordenadas vienen identificadas para cada instante registrado."}
    rank,low,high = column("order","orden"),column("low","inferior","min"),column("high","superior","max")
    if rank and low and high and column("step","etapa","paso","stage"):
        intervals = [tuple(number_value(r.get(k)) for k in (rank,low,high)) for r in rows]
        if all(None not in p and p[1]<p[2] for p in intervals) and len({p[0] for p in intervals})==len(intervals):
            intervals.sort()
            pairs = [(a[1:],b[1:]) for a,b in zip(intervals,intervals[1:])]
            if all(a!=b and a[0]<=b[0] and b[1]<=a[1] for a,b in pairs) or all(
                    a!=b and b[0]<=a[0] and a[1]<=b[1] for a,b in pairs):
                return {"interval-refinement":"Los extremos forman intervalos anidados en el orden documentado."}
    if not profile["measures"]:
        return hints
    measures = ", ".join(profile["measures"])
    for dimension, intent in (("dates", "trend"), ("categories", "compare-categories")):
        columns = [name for name in profile[dimension] if profile["distinct"][name] >= 2]
        if columns:
            hints[intent] = f"Columnas de la tabla: {', '.join(columns)} y {measures}."
    return hints


def candidate(intent, evidence, profile, text, scene=None):
    item = CHOICES[intent]
    target = item.target
    if target in SPECIALISTS:
        kind, producer = "specialist", SPECIALISTS[target]
        source = "../" + producer + "/SKILL.md"
    elif intent == "lookup":
        kind, producer, source = "static", "line-world-video", "../line-world-video/references/data-storytelling.md"
    else:
        kind, producer, source = "artifact", "reference-motion", sources()[target]
    reference = None
    fit = "producer"
    next_step = "Prepara las observaciones, las unidades y el encuadre antes de componer la escena."
    if target in SYSTEM_INPUTS:
        fit = "mechanism-reference" if target in {"ring-handoff", "resolution-fan", "queue-router"} else "editable-template"
        next_step = SYSTEM_INPUTS[target]
    elif target in FIXED_EXAMPLES:
        fit = "editable-template" if target in {"module-transfer", "import-footprint"} else "mechanism-reference"
        next_step = FIXED_EXAMPLES[target] + " "
        if fit == "editable-template":
            next_step += "Sustituye los datos del ejemplo y comprueba la correspondencia de las entidades."
        else:
            next_step += "Reutiliza el movimiento. Para otro dominio, adapta el dibujo y el vocabulario antes de exportar."
            measured = (profile and profile["measures"]) or match(
                r"duraciones reales|measured values|mediciones reales|milisegundos?|milliseconds?|"
                r"microsegundos?|microseconds?|nanosegundos?|nanoseconds?|ms|μs|µs|ns", text)
            if measured:
                reference = target
                target = "measured-" + intent
                producer, kind, fit = "line-world-d3", "specialist", "data-driven-adaptation"
                next_step += " Construye marcas a escala con las observaciones reales en line-world-d3."
    elif target == "pivot-rotation":
        fit = "editable-template"
        next_step = ("Indica unit, radius, startAngle y sweepAngle en content. Los ángulos se miden en grados. "
                     "Usa cartesian para partir del este en sentido antihorario o compass para partir del norte en sentido horario.")
    elif target == "object-route":
        fit, next_step = "editable-template", "Introduce el nombre en content.objectLabel y la secuencia en content.stops. Repite el nombre de una estación para regresar a ella."
    elif kind == "static":
        fit, next_step = "static", "Alinea cifras y unidades y reserva una pausa para leer."
    elif kind == "artifact":
        fit, next_step = "editable-template", "Completa la receta con etiquetas, valores y unidades de la fuente."
    result = dict(id=target, kind=kind, producer=producer, intent=intent, why=item.why,
                anchor=item.anchor, motion=item.motion, evidence=evidence, source=source,
                fit=fit, next_step=next_step, reference_artifact=reference)
    if scene:
        result.update(scene_id=scene["scene"], scene_name=scene["name"], recipe=STUDY_RECIPE,
                      why=scene["name"] + ".", anchor=scene["anchor"], motion=scene["observations"][0],
                      source=scene["url"], source_s=scene["source_s"],
                      next_step=f"Inicializa la escena con scripts/generate_motion.py init {scene['scene']} escena.json "
                                "y adapta los nodos y tiempos a tu explicación.")
    elif target == "staged-network":
        result["source"] = systems_study()["playlist"]
    return result


def brief_intents(text, profile, scenes=()):
    matches = {}
    for key, rule in CHOICES.items():
        hits = [match(cue, text) for cue in rule.cues]
        if all(hits):
            matches[key] = "Indicios del brief: " + ", ".join(hit.group() for hit in hits) + "."
    if scenes:
        matches["staged-network"] = "El brief identifica una relación representada en el estudio de sistemas."
        # A shared heap is more specific than a generic shared host. A stream plus its
        # receiving devices explains an additional relationship beyond frame sizes.
        for scene in scenes:
            if scene["video_id"] == "4rLW7zg21gI":
                matches.pop("shared-resource", None)
            elif scene["video_id"] == "7AMRfNKwuYo":
                matches.pop("resolution-fan", None)
    dated = match(PERIOD, text) or (profile and profile["dates"])
    measured = match(MEASURE, text) or (profile and profile["measures"])
    if match(r"sin (?:medidas|mediciones|datos)|no (?:hay|tengo|tenemos) (?:medidas|mediciones|datos)|"
             r"no (?:data|measurements)|without (?:data|measurements)", text):
        measured = False
    if match(CHANGE, text) and dated and measured:
        matches["trend"] = "El brief vincula un cambio de la medida con un período."
    elif "trend" in matches and match(r"evolu\w*", text) and not (dated or measured):
        del matches["trend"]
    category = profile and any(re.search(r"\b" + re.escape(normalize(name)) + r"(?:s|es)?\b", text)
                               for name in profile["categories"])
    ranking = match(r"ranking|rank\w*|(?:vendio|registro|facturo|tuvo) (?:mas|menos)|"
                    r"(?:most|fewest|largest|highest|lowest|mayor|menor)", text)
    by_group = category and match(r"por|by|per|segun", text)
    compare = category and match(r"compar\w+", text)
    if profile and profile["categories"] and (compare or measured and by_group or ranking and profile["measures"]):
        matches["compare-categories"] = "La pregunta compara grupos y la tabla incluye una dimensión categórica."
    if "lookup" in matches and not (ranking or by_group):
        return {"lookup": matches["lookup"]}
    if "compare-lanes" in matches:
        matches.pop("compare-categories", None)
    if "paired-change" in matches:
        matches.pop("trend", None)
    if "trajectory-trace" in matches:
        matches.pop("trend", None)
    if set(matches) & SYSTEM_INPUTS.keys():
        # Numeric operands (bit indices, tokens, order, radix) describe the mechanism.
        # Switch to a chart only when the question asks for a measured outcome.
        metric = match(r"latenc\w*|duraci\w*|durations?|cost[oe]s?|costs?|throughput|rendimiento|"
                       r"tasas?|rates?|porcentajes?|percentages?|percentil\w*|percentile\w*|"
                       r"tiempos? de espera|wait times?|memoria consumida|memory usage|frecuencias?|frequenc\w*", text)
        if metric:
            if match(r"compar\w*|rank\w*|ordenar|mayor|menor|highest|lowest", text) and match(r"por|entre|by|between|across|per", text):
                matches.setdefault("compare-categories", "El brief pide comparar una medida entre grupos.")
            if match(r"cifra exacta|exact figure|valor medido|observed value", text):
                matches.setdefault("lookup", "El brief pide consultar una observación exacta.")
            measured_intents = {"trend", "compare-categories", "distribution", "share", "composition", "correlation", "paired-change", "lookup"}
            if matches.keys() & measured_intents:
                return {key: evidence for key, evidence in matches.items() if key in measured_intents}
        elif "trend" in matches and not (measured or match(r"trend\w*|tendencia\w*|time series|serie temporal", text)):
            matches.pop("trend")
        if "staged-network" in matches:
            matches.pop("relationships", None)
    return matches


def recommend(brief="", rows=None, intent=None):
    """Return a recommendation, a conditional shortlist, or an editorial question."""
    if intent is not None and intent not in CHOICES:
        raise ValueError("Intención desconocida: " + str(intent))
    text = normalize(brief)
    profile = profile_rows(rows) if rows is not None else None
    hints = structural_hints(profile, rows)
    scenes = staged_scenes(text)
    matches = brief_intents(text, profile, scenes)
    if match(STILL, text):
        selected = {"lookup": "El brief pide una presentación estática o con movimiento reducido."}
    elif intent:
        selected = {intent: "La intención editorial indicada es " + intent + "."}
    elif matches:
        selected = matches
    else:
        selected = hints
    incompatible_denominators = match(
        r"distintos denominadores|different denominators|denominadores (?:diferentes|distintos)|each (?:with )?its own denominator", text)
    if profile:
        incompatible_denominators = incompatible_denominators or any(
            profile["distinct"][key] > 1 for key in profile["denominators"])
    share_conflict = bool(incompatible_denominators and selected.keys() & {"share", "composition"})
    if share_conflict:
        selected = {key: evidence for key, evidence in selected.items() if key not in {"share", "composition"}}
    percentages = re.findall(r"(?<![\w.,])([+-]?\d+(?:[.,]\d+)?)\s*%", text)
    range_conflict = "share" in selected and (
        any(not 0 <= number_value(v) <= 100 for v in percentages)
        or bool(profile and profile["out_of_range_percentages"]))
    if range_conflict:
        selected.pop("share", None)
    incomplete_comparison = bool(rows is not None and "compare-categories" in selected
                                 and not comparable_categories(rows, profile, text))
    if incomplete_comparison:
        selected.pop("compare-categories", None)
    options = []
    for key, evidence in selected.items():
        if key == "staged-network" and scenes:
            options.extend(candidate(key, evidence, profile, text, scene) for scene in scenes)
        else:
            options.append(candidate(key, evidence, profile, text))
    unresolved_question = "¿Qué debe poder identificar el espectador: un cambio, una comparación, una conexión o un valor exacto?"
    result = dict(decision="insufficient", recommendation=None, alternatives=[], question=None, data_profile=profile)
    if len(options) > 1:
        result.update(decision="ambiguous", alternatives=options)
        if {"trend", "compare-categories"} <= selected.keys():
            result["question"] = "¿Interesa seguir el cambio en el tiempo o comparar categorías en un mismo período?"
        else:
            result["question"] = "¿Qué relación debe reconocer primero el espectador? " + " / ".join(
                option["why"] for option in options)
    elif options:
        result.update(decision="recommended", recommendation=options[0])
        if profile and not (matches or intent) and selected.keys() & {"compare-categories", "trend"}:
            result["question"] = "¿Qué medida, unidad y población sostienen esa lectura?"
    else:
        result["question"] = unresolved_question
    if "paired-change" in selected:
        # Two qualitative states can be inspected side by side. Bars need measured endpoints.
        measure = match(MEASURE, text) or (profile and profile["measures"])
        if not measure and not intent:
            result.update(decision="ambiguous", recommendation=None,
                          alternatives=[candidate("lookup", "Se pueden alinear los dos estados.", profile, text),
                                        candidate("paired-change", "Aplicable a dos extremos medidos.", profile, text)])
        if profile and any(profile["distinct"][key] > 1 for key in profile["units"]):
            result.update(decision="insufficient", recommendation=None, alternatives=[])
        result["question"] = "¿Son dos medidas de la misma entidad y unidad, o dos estados cualitativos que deben verse juntos?"
    if "compare-categories" in selected and profile and profile["missing"]:
        result["question"] = "¿Qué valores faltan en " + ", ".join(profile["missing"]) + "? Conserva los huecos y compara solo observaciones válidas."
    if not options and match(r"porcentajes?|percentage|tasa|rate", text):
        result["question"] = "¿Qué representa el 100 % en cada grupo y qué porcentajes quieres comparar?"
    if incomplete_comparison:
        result["question"] = ("¿Hay una misma medida disponible para al menos dos categorías distintas? "
                              "Conserva los valores conocidos y los pendientes en una tabla provisional.")
        if not options:
            result["alternatives"] = [candidate("lookup", "Se pueden consultar las observaciones disponibles.", profile, text)]
    if share_conflict:
        result["question"] = "Los grupos tienen denominadores distintos. ¿Qué población y qué parte quieres mostrar para cada grupo?"
    if range_conflict:
        result["question"] = "Hay porcentajes fuera del intervalo de 0 a 100 %. ¿Se trata de un cambio relativo o de una parte del total?"
    if brief and not match(STILL, text):
        from study_direction import find_direction
        directions=find_direction(brief)
        if directions:
            result["study_directions"]=directions
            if directions[0].get("study") == "3Blue1Brown" and result["decision"] == "insufficient" and not intent:
                first = directions[0]
                if first["relation"] not in CHOICES:
                    result.update(decision="recommended", question=None, recommendation=dict(
                        id=first["relation"], kind="specialist", producer="line-world-hyperframes",
                        intent=first["relation"], why=first["name"], motion=first["transfer"],
                        anchor=first["anchor"], evidence=first["motion"], source=first["url"],
                        fit="study-direction", next_step="Prepara " + ", ".join(first["data_roles"]) + "."))
            if len(directions) == 1 and not rows and result["question"] == unresolved_question:
                roles = directions[0]["data_roles"]
                if roles:
                    fields = ", ".join(f"«{role}»" for role in roles)
                    result["question"] = f"¿Qué valores o columnas de tus datos corresponden a {fields}?"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--brief", default="", help="Pregunta o explicación para el espectador, en español o inglés.")
    parser.add_argument("--data", type=Path, help="Tabla CSV o lista JSON de registros con valores escalares.")
    parser.add_argument("--intent", choices=CHOICES, help="Relación editorial explícita.")
    parser.add_argument("--list-intents", action="store_true", help="Mostrar las intenciones y sus composiciones.")
    parser.add_argument("--json", action="store_true", help="Emitir un informe JSON.")
    args = parser.parse_args(argv)
    if args.list_intents:
        for key, rule in CHOICES.items():
            print(f"{key:22} {rule.target:20} {rule.why}")
        return
    if not (args.brief.strip() or args.data or args.intent):
        parser.error("Indica al menos --brief, --data o --intent.")
    try:
        report = recommend(args.brief, read_records(args.data) if args.data else None, args.intent)
    except (OSError, ValueError, csv.Error) as error:
        parser.error(str(error))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    for item in [c for c in [report["recommendation"], *report["alternatives"]] if c]:
        print(f"{item['id']}  ({item['producer']})\n{item['why']}\nMovimiento: {item['motion']}\n"
              f"Ancla: {item['anchor']}\n{item['evidence']}\nAcción: {item['next_step']}\nReferencia: {item['source']}")
        if item.get("scene_id"):
            print(f"Escena: {item['scene_id']}\nReceta: {item['recipe']}")
    directions = report.get("study_directions", [])
    if report["decision"] != "ambiguous" and len(directions) == 1:
        direction = directions[0]
        print(f"{direction['name']}\n{direction['transfer']}\n{direction['url']}")
    if report["question"]:
        print(report["question"])


if __name__ == "__main__":
    main()

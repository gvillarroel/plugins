"""Look up transferable motion in the local, timed reference study."""
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


CORPUS = Path(__file__).resolve().parents[1] / "references" / "transfer-corpus.json"


@dataclass(frozen=True)
class Rule:
    families: tuple
    cues: tuple


def rule(families, *cues):
    """Each cue supplies independent evidence; alternatives within a cue use |."""
    return Rule(tuple(families.split()), cues)


# New passage keys are semantic relationships. Reconstructed passages have stable
# scene IDs, so a source selection never depends on the order of the index.
RULES = {
    "recursive-spatial-partition": rule("hierarchy",
        r"cuadrantes?|quadrants?|subdivis\w*|subdivid\w*|parcel\w*|teselas?|tiles?",
        r"region\w*|zonas?|superficie|mapa|territor\w*|areas?|images?|map|grid|rejilla|cuadricul\w*|fincas?|farmland|fields?|plots?"),
    "item-reassignment": rule("exchange comparison",
        r"reasign\w*|reassign\w*|reubica\w*|redistrib\w*|traslad\w*|migrat\w*",
        r"muelles?|equipos?|destinos?|grupos?|recipientes?|puertos?|almacenes?|teams?|depots?|destinations?|buckets?|owners?|warehouses?|groups?"),
    "qualitative-tradeoff": rule("comparison parallel-states",
        r"disyuntiva|contrapuest\w*|contrapon\w*|sacrific\w*|trade[ -]?offs?|tension|prioriza\w*|balancear|equilibr\w*|weigh\w*|balanc\w*|versus|frente a",
        r"criterios?|prioridades|cost[eo]s?|calidad|precisi\w*|rapidez|velocidad|criteri\w*|priorit\w*|quality|accuracy|speed|costs?",
        r"entre|frente a|contra|versus|dos|y|between|against|two|and"),
    "time-series-reveal": rule("sequence comparison",
        r"pico\w*|peak\w*|tendencia|trend|evoluc\w*|historical|historico|evolv\w*|fluctu\w*",
        r"tiempo|time|dias?|days?|mensual\w*|monthly|mes\w*|seman\w*|weeks?|horas?|hours?|fechas?|dates?|anual\w*|years?|daily|weekly|hourly|serie\w*"),
    "ordered-segmentation": rule("sequence fan-out",
        r"divid\w*|cort\w*|split\w*|segment\w*|divide\w*|troce\w*",
        r"grabaci\w*|recording\w*|cronograma|continu\w*|tramos?|fragment\w*|grabado|episodes?|clips?|timeline|film|lotes? consecutivos|successive batches"),
    "stacked-category-comparison": rule("comparison group-members",
        r"component\w*|aportes?|aportacion\w*|desglos\w*|descompon\w*|breakdown|contributions?|apilad\w*|stacked|composicion",
        r"categor\w*|regi[oó]n\w*|equipos?|sedes?|departamentos?|productos?|levels?|niveles|teams?|locations?|departments?|products?|rubros?"),
    "selected-route": rule("sequence hierarchy",
        r"elegid\w*|seleccion\w*|escog\w*|chosen|selected|pick\w*|preferred|preferid\w*|tomad[ao]",
        r"rutas?|caminos?|itinerar\w*|trayect\w*|alternativas?|paths?|routes?|itinerar\w*|branches|ramas?"),
    "lane-handoff": rule("exchange sequence",
        r"relev\w*|turnos?|handoffs?|turns?|cambio de guardia|shift change|altern\w*",
        r"equipos?|personas?|actores?|responsab\w*|guardias?|procesos?|teams?|people|actors?|owners?|process\w*|shifts?|employee\w*"),
    "mirrored-transformation": rule("exchange comparison",
        r"transform\w*|codifica\w*|encod\w*|convie\w*|conver\w*|envio|sending",
        r"decod\w*|reconver\w*|recuper\w*|invers\w*|de vuelta|round[ -]?trip|recepci\w*|receiving|recover\w*|reverse\w*"),
    "context-focus-return": rule("hierarchy sequence",
        r"ampli\w*|acerc\w*|zoom\w*|enfoc\w*|focus\w*",
        r"volver|regres\w*|retorn\w*|return\w*|back to|reubicar|recontextual\w*"),
    "context-detail": rule("hierarchy",
        r"detalle|detail|subregi\w*|ampli\w*|zoom\w*|inset",
        r"mapa|map|contexto|overview|miniatura|thumbnail|zona|region\w*|mapa indice"),
    "containment": rule("group-members hierarchy",
        r"agru\w*|group\w*|pertenec\w*|belong\w*|contain\w*|organiza\w*",
        r"departamentos?|capas?|niveles?|bandas?|areas?|departments?|layers?|levels?|teams?|equipos?"),
    "paired-comparison": rule("comparison parallel-states",
        r"dos|amb[ao]s|two|both|antes y despues|before and after",
        r"alternativ\w*|metodos?|variantes?|opciones?|methods?|options?|procedimientos?|approaches|ways|maneras?|workflows?|procesos?|procedures?"),
    "ordered-cards": rule("sequence",
        r"etapas?|steps?|stages?|fases?|phases?|hitos|milestones?",
        r"descripci\w*|descripcion|etiqueta por|describ\w*|explicaci\w*|description\w*|explain\w*|tarjetas?|cards?|titulo|title|brief text"),
    "progressive-table": rule("comparison sequence",
        r"primer\w*|first|menor|lowest|smallest|minim\w*",
        r"umbral|threshold|cumpl\w*|suficien\w*|sufficient|meeting|qualif\w*|que cubr\w*|meets?"),
    "merge-lineage": rule("fan-in",
        r"fusion\w*|concili\w*|reconcil\w*|merge\w*|combin\w*|integr\w*",
        r"version\w*|edicion\w*|revisions?|edits?|variantes?|origen\w*|linaje|provenance|lineage"),
    "partition-sequence": rule("sequence",
        r"fronteras?|boundar\w*|cortes?|splits?|episodios?|episodes?|segment\w*|lotes?|batches",
        r"pistas?|hileras?|series (?:alineadas|paralelas)|synchron\w*|sincron\w*|tracks?|parallel series|aligned series"),
    "repeated-event": rule("sequence exchange",
        r"periodic\w*|rep[ie]t\w*|cada\s+\w+|interval\w*|heartbeat\w*|every \w+|pulsos?",
        r"sensor\w*|ultima (?:lectura|observacion|se[nñ]al)|ultimo (?:estado|registro|aviso)|last (?:reading|state|seen)|latest|timestamps?|sellos? de tiempo|check[ -]?ins?|recepcion\w*|receipts?"),
    "count-threshold": rule("comparison sequence",
        r"aforo|capacidad|cuota\w*|limites?|umbral\w*|quotas?|capacity|limits?|threshold\w*",
        r"conteo|contador|eventos? por|por (?:hora|turno|dia|ventana)|window\w*|por intervalo|count\w*|per (?:hour|shift|day|interval)|ventanas?|ocupacion"),
    "paired-criteria": rule("comparison",
        r"identific\w*|clave\w*|keys?|identit\w*|id",
        r"contenidos?|contents?|huella\w*|fingerprints?",
        r"igual\w*|duplica\w*|mism[ao]s?|sameness|equal\w*|same|dedup\w*"),
    "video-01-staged-network": rule("hierarchy fan-out",
        r"rutas?|enrut\w*|repart\w*|balances?|balanc\w*|route\w*|distribut\w*",
        r"replicas?|lecturas? y escrituras?|reads? and writes?|destinos? especializad\w*|speciali[sz]ed destinations?"),
    "video-02-ring-handoff": rule("exchange",
        r"anillo\w*|rings?",r"propietari\w*|duen\w*|asigna\w*|reasign\w*|reassign\w*|handoff\w*|owner\w*"),
    "video-03-bit-probe": rule("sequence",
        r"bits?|filtro de bloom|bloom filter", r"pertenen\w*|membership|consult\w*|probe\w*|insert\w*|escrib\w*|writes?"),
    "video-04-staged-network": rule("fan-out comparison",
        r"demanda|carga (?:total|prevista)|demand|workload|load", r"capacidad por|per[ -](?:unit|server|worker|machine) capacity|capacity per"),
    "video-05-staged-network": rule("fan-out",
        r"version\w*|variant\w*|rendition\w*|salidas?|outputs?", r"pantallas?|dispositiv\w*|devices?|screens?|medio de entrega|delivery channel"),
    "video-06-staged-network": rule("parallel-states",
        r"rondas?|rounds?|sesiones?|sessions?", r"tarjetas?|cards?|entrevista|interview|paneles|panels"),
    "video-07-staged-network": rule("fan-in",
        r"varios|varias|multiples|multiple|several|many|tres|three",
        r"al mismo|hacia el mismo|un solo|single (?:hub|receiver|destination)|same (?:hub|receiver|destination)|converg\w*|punto comun"),
    "video-08-staged-network": rule("group-members",
        r"compart\w*|shared?|sharing", r"recurso\w*|recinto\w*|espacio|sala\w*|pool|resource\w*|heap|space|rooms?|facility"),
    "video-09-message-ladder": rule("exchange",
        r"mensajes?|invitacion\w*|solicitud\w*|message\w*|requests?|letters?",
        r"respond\w*|respuesta\w*|repl(?:y|ies)|answer\w*|ida y vuelta|intercambi\w*|exchange\w*|entre .+ y|between .+ and"),
    "video-10-detail-callout": rule("hierarchy",
        r"fragment\w*|partes|parts?|campos?|fields?|segments?",
        r"expresion|expression|direccion|address|formula|etiqueta|label|string|texto|cadena|text|url"),
    "video-11-staged-network": rule("hierarchy",
        r"prefij\w*|prefix\w*|antecesor\w*|ancestors?|ramas comunes|shared branch\w*|common branch\w*",
        r"arbol\w*|trees?|ramas?|branches|palabras?|words?|descend\w*"),
    "video-12-staged-network": rule("fan-in fan-out",
        r"productor\w*|emisores?|publishers?|producers?|senders?|origenes|sources?",
        r"consumidor\w*|suscriptor\w*|subscribers?|consumers?|receptor\w*|receivers?",r"bus|canal|channel|intermedi\w*"),
    "video-13-staged-network": rule("sequence",
        r"hitos?|milestones?|eventos?|events?", r"cronolog\w*|calendar\w*|calendario|timeline|histor\w*|resuel\w*|resolve\w*"),
    "video-14-staged-network": rule("hierarchy",
        r"categori\w*|category|collection|coleccion|familia|family", r"recurso\w*|resource\w*|materiales?|materials?|ejemplos?|examples?"),
    "video-15-radix-ladder": rule("sequence",
        r"base [0-9]+|base numerica|numeric base|radix", r"divi\w*|residu\w*|restos?|remainders?|entero\w*|integer\w*|convert\w*"),
    "video-16-staged-network": rule("hierarchy",
        r"claves?|keys?|identificadores?|identifiers?", r"particion\w*|buckets?|shards?|un solo destino|one destination|one node"),
    "video-17-resolution-fan": rule("fan-out",
        r"resoluci\w*|resolution\w*|rendition\w*|formatos?|formats?", r"version\w*|variantes?|variant\w*|original\w*|salidas?|outputs?"),
    "video-18-staged-network": rule("fan-out",
        r"avisos?|mensajes?|notific\w*|entreg\w*|message\w*|notices?|announcement\w*|envia\w*|broadcast\w*",
        r"destinatari\w*|recipients?|varios|varias|multiple|varias sedes|grupo|group|muchos|many"),
    "video-19-token-gate": rule("sequence",
        r"fichas?|tokens?|cupos?|slots?", r"admi\w*|denie\w*|descar\w*|acepta\w*|deni\w*|reject\w*|accept\w*|consum\w*"),
    "video-20-queue-router": rule("fan-in fan-out",
        r"colas?|queues?|trabajos?|jobs?", r"priori\w*|urgencia|urgency|preferencia"),
}

# A known relation from structured data is sufficient for one general example.
# More specific briefs can override these defaults within the compatible family.
FAMILY_EXAMPLES = {
    "fan-out":"video-18-staged-network", "fan-in":"video-07-staged-network",
    "hierarchy":"video-11-staged-network", "sequence":"ordered-cards",
    "exchange":"video-09-message-ladder", "comparison":"stacked-category-comparison",
    "group-members":"containment", "parallel-states":"video-06-staged-network",
}


def normalize(text):
    return "".join(ch for ch in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(ch))


@lru_cache(maxsize=1)
def passages():
    study = json.loads(CORPUS.read_text(encoding="utf-8-sig"))
    found = {}
    for video in study["videos"]:
        for passage in video["passages"]:
            key = passage.get("scene_id") or passage["relation"]
            if key in found:
                raise ValueError(f"Clave de pasaje duplicada: {key}")
            found[key] = (video["video_id"], passage)
    return found


def evidence_for(key):
    video_id, passage = passages()[key]
    start, end = passage["source_s"]
    return {
        "video_id":video_id, "url":f"https://www.youtube.com/watch?v={video_id}&t={int(start)}s",
        "source_s":[start,end], "name":passage["name"], "relation":passage["relation"], "anchor":passage["anchor"],
        "motion":" ".join(passage["observations"]), "transfer":passage["transfer"],
        "limitation":passage.get("limitation", ""), "data_roles":list(passage.get("data_roles", [])),
    }


def find_direction(brief, relation=None):
    """Return up to three compatible, directly sourced directions for the viewer's question."""
    text = normalize(brief or "")
    from math_study import directions
    mathematical = directions(text, relation)
    if mathematical:
        return mathematical
    if relation in RULES:
        return [evidence_for(relation)]
    family = relation if relation in FAMILY_EXAMPLES else None
    matches = []
    for key, rule in RULES.items():
        if family and family not in rule.families:
            continue
        signals = [re.search(r"\b(?:" + cue + r")\b", text, re.IGNORECASE) for cue in rule.cues]
        if all(signals):
            # Prefer constraints with stronger specific phrases when several fit.
            score = (len(signals), sum(len(signal.group()) for signal in signals))
            matches.append((score,key))
    if matches:
        matches.sort(key=lambda row:row[0], reverse=True)
        selected = {}
        for _, key in matches:
            result = evidence_for(key)
            selected.setdefault(result["relation"], result)
            if len(selected) == 3:
                break
        return list(selected.values())
    if family:
        result = evidence_for(FAMILY_EXAMPLES[family])
        if family == "comparison":
            # Only the common baseline and category staging transfer without a component field.
            result.update(
                anchor="El cero, las posiciones de las categorías y la escala común.",
                transfer="Sitúa cada categoría sobre la misma base y revela sus valores en orden. "
                         "La altura final se calcula desde el valor de cada categoría. "
                         "Añade segmentos solo si existen componentes aditivos identificados.",
            )
        return [result]
    return []

"""Retrieve observed mathematical compositions by the relationship a viewer must see."""
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Composition:
    name: str
    families: tuple
    cues: tuple
    roles: tuple
    transfer: str


COMPOSITIONS = {
    "interval-refinement": Composition("Ampliar un intervalo conservando su escala de origen",
        ("interval-refinement",), (r"intervalos?|intervals?|rangos?|ranges?|bounds?|tramos?", r"anidad\w*|nested|acotar|estrech\w*|refin\w*|narrow\w*|bisec\w*"),
        ("etapa", "orden", "límites inferior y superior", "unidad"),
        "Señala los dos extremos dentro del intervalo anterior. Amplía la selección y conserva una referencia al dominio inicial."),
    "trajectory-trace": Composition("Ver un móvil y su gráfica en el mismo instante",
        ("state-and-trace",), (r"trayectori\w*|trajector\w*|movil|moving point|recorrido|motion path|oscilador|oscillator", r"traza|trace|grafica|graph|plot|altura en el tiempo|height over time"),
        ("instante", "posición x e y", "unidad de posición y tiempo"),
        "Mantén visible el móvil mientras la misma muestra prolonga la curva temporal. Identifica el mismo instante en las dos vistas."),
    "geometric-proof": Composition("Construir la relación sobre la figura",
        ("constructed-proof","geometric-construction","geometric-measure","isolate-contact-rule"), (r"geometr\w*|triang\w*|angul\w*|circul\w*|tangenc\w*|tangents?|esferas?|spheres?", r"demostr\w*|prov\w*|proof|constru\w*|deduc\w*|teorema|theorem|intersec\w*"),
        ("figuras de partida", "relación que se quiere demostrar", "construcción auxiliar"),
        "Conserva la figura inicial. Añade una recta, un punto o una superficie auxiliar y destaca qué relación se puede leer al terminar."),
    "orders-of-magnitude": Composition("Cambiar de escala con una referencia legible",
        ("scale-transition","scale-ladder"), (r"escala\w*|scales?|magnitud\w*|magnitudes?|zoom\w*", r"potencias? de (?:diez|10)|powers? of (?:ten|10)|ordenes de magnitud|orders? of magnitude|microscop\w*|macro\w*"),
        ("objeto de referencia", "extensión", "unidad"),
        "Deja reconocer el objeto antes de reducirlo. Actualiza la regla del encuadre para mostrar cuánto espacio ocupa la siguiente vista."),
    "invariant-examples": Composition("Cambiar el ejemplo y conservar la condición",
        ("pose-invariant","conserved-total"), (r"invarian\w*|conserv\w*|permanece|preserv\w*|unchanged", r"curvas?|formas?|shapes?|figuras?|geometr\w*|restricci\w*|cantidades?|quantit\w*|total"),
        ("ejemplos", "magnitud o condición común"),
        "Ensaya configuraciones distintas. Sitúa la marca del invariante en el mismo lugar para que se pueda comprobar en cada pose."),
    "parameter-and-field": Composition("Variar un parámetro y mostrar su efecto sobre un campo",
        ("parameter-field","vector-field","parameter-surface","parameter-grid","physical-to-field","local-basis-to-field"), (r"parametr\w*|parameter\w*|temperatur\w*|temperature", r"campo|fields?|superficie|surfaces?|fase|phase|reticul\w*|lattice"),
        ("parámetro", "muestras del campo", "dominio"),
        "Fija el dominio y su leyenda. Cambia un solo parámetro, actualiza la misma región y deja una pausa para comparar estados."),
    "corresponding-views": Composition("Relacionar dos representaciones del mismo objeto",
        ("linked-views","coordinate-projection","linked-transform-views","domain-extension","commuting-paths"), (r"representa\w*|vistas?|views?|coordenad\w*|coordinat\w*|proyec\w*|project\w*", r"correspond\w*|equival\w*|mism[ao] punto|same point|vincul\w*|enlaz\w*|linked"),
        ("identidad de la muestra", "dos representaciones", "correspondencia"),
        "Elige una muestra reconocible y marca a la vez dónde cae en ambas vistas antes de pasar a otra."),
    "enumerate-configurations": Composition("Construir un espacio de configuraciones",
        ("enumerate-states","accumulating-examples","dimension-table"), (r"combinac\w*|combinat\w*|configur\w*|estados?|states?", r"enumer\w*|contar|count\w*|exhaust\w*|todas|every possible|all possible"),
        ("opciones", "regla de construcción", "estado ya contado"),
        "Conserva el catálogo de casos vistos y transforma una sola elección cada vez. Identifica la regla que genera un caso nuevo."),
    "model-measurement": Composition("Relacionar una medida con la construcción que la explica",
        ("model-to-measure","geometric-measure","flow-through-meter"), (r"medir|medicion\w*|measur\w*|estim\w*", r"radio|radius|distancia|distance|angulo|angle|orbita|orbit|caudal|flow rate"),
        ("referencia conocida","magnitud observada","unidad"),
        "Marca en la figura la longitud, el ángulo o el flujo que se mide. Deja la unidad junto al valor y conserva la referencia mientras se lee."),
    "compare-models": Composition("Contrastar modelos en el mismo marco",
        ("compare-alternatives","lecture-to-shared-axes"), (r"modelos?|models?|hipotesis|hypothes\w*|frecuenc\w*|frequenc\w*",r"compar\w*|contrasta\w*|mismos ejes|same axes|contrap\w*"),
        ("dos hipótesis","misma escala","observación que las distingue"),
        "Fija los ejes y la condición inicial. Conserva la primera hipótesis visible al introducir la segunda y señala dónde divergen."),
    "probability-mass": Composition("Relacionar una categoría con su masa de probabilidad",
        ("weighted-area","linked-distributions","cluster-by-attribute"), (r"probabil\w*|distribu\w*|entrop\w*",r"masas?|mass|pesos?|weights?|areas?|agrup\w*|cluster\w*"),
        ("categoría","probabilidad o frecuencia","total de referencia"),
        "Identifica la partición y después dirige la mirada a cuánto representa cada parte. Mantén el orden de las categorías durante la comparación."),
    "order-and-rank": Composition("Pasar de una secuencia a su orden bajo un criterio",
        ("ordered-list-to-rank","process-stages"), (r"secuencia|sequence|lista|list|pasos?|steps?",r"reorden\w*|reorder\w*|permut\w*|ranking|clasific\w*"),
        ("identidad de los elementos","orden original","criterio y orden final"),
        "Presenta las identidades antes de cambiar el orden. Deja reconocer por separado el elemento seleccionado, su movimiento y su posición final."),
    "historical-focus": Composition("Situar un relato dentro de su cronología",
        ("timeline-speaker","event-timeline","focus-path-in-map"), (r"cronolog\w*|timeline|linea de tiempo|mapa|map",r"histor\w*|testimon\w*|interview|entrevista|ponente|speaker"),
        ("fecha o lugar","evento","persona o evidencia"),
        "Abre con el recorrido completo y centra un acontecimiento cuando la voz introduce a su protagonista. Conserva una referencia al recorrido."),
}

# Bilingual subject terms for passages whose English titles leave out the visual operation.
SUBJECTS = {
    "C8baNzpnZ7o": "potencias de diez órdenes de magnitud escala cósmica powers of ten",
    "IQqtsm-bBRU": "mismo punto coordenadas curva geometría same point coordinates curve",
    "V_uq3v6xK-4": "intersección esferas volumen intersection spheres volume",
    "-j8PzkZ70Lg": "trayectoria móvil posición oscilación traza altura trajectory moving point height",
    "qbsb9DpdZ6s": "prefijo codificación aritmética intervalos arithmetic coding prefix",
}


@lru_cache(maxsize=1)
def corpus():
    path = Path(__file__).resolve().parents[1] / "references" / "3blue1brown-corpus.json"
    return json.loads(path.read_text(encoding="utf-8"))["passages"]


def directions(text, relation=None):
    if relation and relation not in COMPOSITIONS:
        return []
    for key, rule in COMPOSITIONS.items():
        if relation != key and (relation or not all(re.search(r"\b(?:" + cue + r")\b", text) for cue in rule.cues)):
            continue
        passages = [p for p in corpus() if p["family"] in rule.families]
        # Break ties using the entities and actions described in this particular brief.
        def terms(value):
            plain = unicodedata.normalize("NFKD",value.casefold()).encode("ascii","ignore").decode()
            stop = {"entre","sobre","poder","antes","despues","misma","mismo","cuando","tiene","which","using","shows"}
            return {t[:5] for t in re.findall(r"[a-z]{5,}",plain) if t not in stop}
        query = terms(text)
        def score(p):
            description = " ".join([p["title"],p["anchor"],p.get("use",""),SUBJECTS.get(p["video_id"],""),*p["poses"].values()])
            return (-len(query & terms(description)),rule.families.index(p["family"]))
        passages.sort(key=score)
        results = []
        used = set()
        for p in passages:
            if p["video_id"] in used:
                continue
            used.add(p["video_id"])
            results.append(dict(study="3Blue1Brown", video_id=p["video_id"], url=p["url"], source_s=p["source_s"],
                name=rule.name, relation=key, anchor=p["anchor"], motion=p["poses"]["change"], transfer=rule.transfer,
                data_roles=list(rule.roles), poses=p["poses"], evidence_method=p["method"], speech=p.get("speech"),
                observed_detail=p.get("detail"), source_application=p.get("use")))
            if len(results) == 3:
                break
        if results:
            return results
    return []

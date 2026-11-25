"""Keep source phrases with editorial poses before the production voice clock exists."""
from motion_recipe import require


def read_staging(brief, notes):
    def clean(value):
        require(isinstance(value, str) and value.strip(), "Cada indicación de puesta en escena necesita texto.")
        return " ".join(value.split())

    require(isinstance(notes, dict) and set(notes) == {"claim","anchor","poses"},
            "staging requiere claim, anchor y poses.")
    claim, anchor = clean(notes["claim"]), clean(notes["anchor"])
    poses = notes["poses"]
    require(isinstance(poses, list) and len(poses) == 3, "Traza contexto, acción y resultado en tres poses.")
    script = clean(brief).casefold()
    cursor = 0
    result = []
    for role, pose in zip(("context","action","result"), poses):
        require(isinstance(pose, dict) and set(pose) == {"role","phrase","visual"} and pose["role"] == role,
                "Cada pose necesita role, phrase y visual en orden de lectura.")
        phrase, visual = clean(pose["phrase"]), clean(pose["visual"])
        pos = script.find(phrase.casefold(), cursor)
        require(pos >= 0, "Las tres frases deben aparecer en orden en el guion suministrado.")
        cursor = pos + len(phrase.casefold())
        result.append(dict(role=role, phrase=phrase, visual=visual))
    return dict(claim=claim, anchor=anchor, poses=result, timing="script-phrases")

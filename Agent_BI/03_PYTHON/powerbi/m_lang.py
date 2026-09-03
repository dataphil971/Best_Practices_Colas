"""Utilitaires d'inspection légère du code M (Power Query).

Ne construit PAS un AST complet du langage M : uniquement ce dont les règles
Agent BI ont besoin aujourd'hui — localiser un appel de fonction nommé et
récupérer ses arguments de haut niveau en texte brut. Une évolution vers un
vrai parseur M (expressions imbriquées, opérateurs, `let...in`) se fera
règle par règle, à mesure du besoin réel (même principe que
`powerbi/tmdl_parser.py` : ne pas parser une construction "au cas où").

Les commentaires M (`// ligne`, `/* bloc */`) sont retirés avant toute
analyse structurelle (`_strip_m_comments`, appelé par chaque point d'entrée
public) — pas un raffinement optionnel : sur un projet réel appliquant BP-35
(commentaire avant chaque étape complexe), une écrasante majorité des étapes
portent un commentaire précédent, et sans ce retrait `parse_let_steps` ne
reconnaissait AUCUNE étape du fichier (confirmé sur
AI_BAROMETER_BI-CDS.SemanticModel, 2026-08-19 — table F_RESPONSES, 9 étapes
sur 9 perdues avant correction).
"""

import re
from dataclasses import dataclass

_IDENT_CHAR = re.compile(r"[A-Za-z0-9_]")


@dataclass
class MFunctionCall:
    """Un appel `Fonction(arg1, arg2, ...)` localisé dans du texte M brut."""

    function_name: str
    raw_arguments: list[str]


@dataclass
class MStep:
    """Une étape `Nom = Expression` d'un bloc `let ... in ...`.

    `line_offset` est le nombre de sauts de ligne entre le DÉBUT du code M et
    le début de cette étape (0 pour la première ligne du `let`). Combiné à
    `PartitionDef.m_source_line` / `ExpressionDef.m_source_line`, il donne le
    numéro de ligne ABSOLU de l'étape dans le fichier TMDL — c'est ce qui
    permet de dire « à telle étape, ligne N » plutôt que « quelque part dans
    cette requête ».
    """

    name: str
    raw_name: str
    expression: str
    line_offset: int = 0


def _skip_string_literal(text: str, start: int) -> int:
    """`start` pointe sur le `"` ouvrant ; retourne l'index juste après le `"`
    fermant. Une paire `""` à l'intérieur de la chaîne est un `"` littéral
    échappé (convention M), pas une fin de chaîne."""
    i = start + 1
    n = len(text)
    while i < n:
        if text[i] == '"':
            if i + 1 < n and text[i + 1] == '"':
                i += 2
                continue
            return i + 1
        i += 1
    return n  # chaîne non terminée : on s'arrête à la fin du texte, sans lever d'exception.


def _split_top_level_arguments(text: str, open_paren_index: int) -> tuple[list[str], int]:
    """`open_paren_index` pointe sur le `(` ouvrant d'un appel. Retourne
    (arguments bruts de premier niveau, index juste après le `)` fermant
    correspondant), en respectant l'imbrication des parenthèses / crochets /
    accolades et le contenu des chaînes (une virgule dans une chaîne ou un
    appel imbriqué ne sépare pas deux arguments)."""
    i = open_paren_index + 1
    n = len(text)
    depth = 1
    current: list[str] = []
    args: list[str] = []

    while i < n and depth > 0:
        ch = text[i]

        if ch == '"':
            j = _skip_string_literal(text, i)
            current.append(text[i:j])
            i = j
            continue

        if ch in "([{":
            depth += 1
            current.append(ch)
            i += 1
            continue

        if ch in ")]}":
            depth -= 1
            i += 1
            if depth == 0:
                break
            current.append(ch)
            continue

        if ch == "," and depth == 1:
            args.append("".join(current).strip())
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    tail = "".join(current).strip()
    if tail or args:
        args.append(tail)
    return args, i


def find_function_calls(m_source: str | None, function_name: str) -> list[MFunctionCall]:
    """Recherche tous les appels `<function_name>(...)` dans `m_source`.

    Ne résout pas les alias/renommages (`let f = Databricks.Catalogs in
    f(...)`, forme `#"Nom Espacé"`) : seul l'appel direct par son nom
    littéral est reconnu — suffisant pour les règles actuelles, qui
    cherchent une fonction connecteur nommée explicitement dans le code M.
    """
    if not m_source:
        return []

    m_source = _strip_m_comments(m_source)
    calls: list[MFunctionCall] = []
    marker = function_name + "("
    search_from = 0

    while True:
        idx = m_source.find(marker, search_from)
        if idx == -1:
            break

        # Ne pas matcher le suffixe d'un identifiant plus long
        # (ex. "MyDatabricks.Catalogs(" ne doit pas matcher "Databricks.Catalogs").
        if idx > 0 and (m_source[idx - 1].isalnum() or m_source[idx - 1] in "_."):
            search_from = idx + 1
            continue

        open_paren = idx + len(function_name)
        raw_arguments, end = _split_top_level_arguments(m_source, open_paren)
        calls.append(MFunctionCall(function_name=function_name, raw_arguments=raw_arguments))
        search_from = end

    return calls


def _strip_m_comments(text: str) -> str:
    """Retire les commentaires M (`// jusqu'à fin de ligne`, `/* bloc */`),
    guillemets respectés (un `//`/`/*` à l'intérieur d'une chaîne littérale
    n'est pas un commentaire). Chaque commentaire est remplacé par des
    espaces (et les retours à la ligne internes à un bloc préservés) plutôt
    que supprimé, pour ne jamais recoller deux tokens qui l'encadraient ni
    décaler les numéros de ligne."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]

        if ch == '"':
            j = _skip_string_literal(text, i)
            out.append(text[i:j])
            i = j
            continue

        if text[i : i + 2] == "//":
            j = text.find("\n", i)
            if j == -1:
                j = n
            out.append(" " * (j - i))
            i = j
            continue

        if text[i : i + 2] == "/*":
            end = text.find("*/", i + 2)
            j = n if end == -1 else end + 2
            out.append("".join("\n" if c == "\n" else " " for c in text[i:j]))
            i = j
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def _at_keyword(text: str, i: int, keyword: str) -> bool:
    """Vrai si `keyword` (ex. "let"/"in") apparaît à l'index `i` en tant que
    MOT entier (pas comme sous-chaîne d'un identifiant plus long, ex. le
    "in" de "Building")."""
    n = len(keyword)
    if text[i : i + n] != keyword:
        return False
    before_ok = i == 0 or not _IDENT_CHAR.match(text[i - 1])
    after_ok = i + n >= len(text) or not _IDENT_CHAR.match(text[i + n])
    return before_ok and after_ok


def _find_top_level_let_block(text: str) -> tuple[int, int] | None:
    """Localise le PREMIER bloc `let ... in` de plus haut niveau.

    Retourne (index du 1er caractère après ce `let`, index du `in` qui lui
    correspond), en respectant les paires `let`/`in` imbriquées (un `let`
    peut apparaître comme valeur à l'intérieur d'une étape de l'étape
    englobante — cf. `each let x = 1 in x`). Les chaînes sont ignorées pour
    ne jamais confondre un `let`/`in` textuel à l'intérieur d'un littéral
    avec un vrai mot-clé.
    """
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch == '"':
            i = _skip_string_literal(text, i)
            continue
        if _at_keyword(text, i, "let"):
            body_start = i + 3
            depth = 1
            j = body_start
            while j < n:
                c = text[j]
                if c == '"':
                    j = _skip_string_literal(text, j)
                    continue
                if _at_keyword(text, j, "let"):
                    depth += 1
                    j += 3
                    continue
                if _at_keyword(text, j, "in"):
                    depth -= 1
                    if depth == 0:
                        return body_start, j
                    j += 2
                    continue
                j += 1
            return None  # `in` jamais trouvé : bloc `let` non refermé.
        i += 1
    return None


def _split_top_level_steps(text: str, body_start: int, in_start: int) -> "list[tuple[str, int]]":
    """Découpe `text[body_start:in_start]` (corps d'un bloc `let`, juste
    avant son `in`) en fragments bruts d'étapes séparés par une virgule de
    premier niveau — imbrication de parenthèses/crochets/accolades ET de
    `let...in` internes respectée (une étape peut elle-même contenir un
    `let` dont les virgules internes ne doivent pas être vues comme des
    séparateurs de l'étape englobante)."""
    i = body_start
    bracket_depth = 0
    let_depth = 0
    current: list[str] = []
    parts: list[tuple[str, int]] = []
    fragment_start = body_start

    while i < in_start:
        ch = text[i]

        if ch == '"':
            j = _skip_string_literal(text, i)
            current.append(text[i:j])
            i = j
            continue

        if _at_keyword(text, i, "let"):
            let_depth += 1
            current.append("let")
            i += 3
            continue

        if _at_keyword(text, i, "in"):
            let_depth -= 1
            current.append("in")
            i += 2
            continue

        if ch in "([{":
            bracket_depth += 1
            current.append(ch)
            i += 1
            continue

        if ch in ")]}":
            bracket_depth -= 1
            current.append(ch)
            i += 1
            continue

        if ch == "," and bracket_depth == 0 and let_depth == 0:
            parts.append(("".join(current), fragment_start))
            current = []
            i += 1
            fragment_start = i
            continue

        current.append(ch)
        i += 1

    tail = "".join(current)
    if tail.strip():
        parts.append((tail, fragment_start))
    return parts


_STEP_NAME_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*", re.DOTALL)


def _split_step_name(raw_step: str) -> tuple[str, str, str] | None:
    """Sépare une étape brute en (nom réel, nom brut, expression).

    Le nom peut être un identifiant simple ou une forme entre guillemets
    `#"Nom avec espaces"` (obligatoire dès que le nom contient un caractère
    hors identifiant M standard)."""
    s = raw_step.lstrip()
    if s.startswith('#"'):
        end = s.find('"', 2)
        if end == -1:
            return None
        raw_name = s[: end + 1]
        rest = s[end + 1 :].lstrip()
        if not rest.startswith("="):
            return None
        return s[2:end], raw_name, rest[1:].strip()

    m = _STEP_NAME_RE.match(s)
    if not m:
        return None
    name = m.group(1)
    return name, name, s[m.end() :].strip()


def parse_let_steps(m_source: str | None) -> list[MStep]:
    """Découpe le PREMIER bloc `let ... in ...` de haut niveau de `m_source`
    en étapes ordonnées. Retourne `[]` si aucun bloc `let` n'est trouvé ou
    si le code n'est pas interprétable comme une suite d'étapes — jamais
    d'exception : au checker appelant de traiter une liste vide comme
    "code non interprétable" (NA), jamais comme "aucune transformation".

    Ne redescend PAS dans les `let` imbriqués à l'intérieur d'une étape :
    l'expression de cette étape reste un bloc de texte brut, exactement
    comme pour une colonne calculée ou une mesure DAX ailleurs dans ce
    moteur — non ré-analysé tant qu'aucune règle n'en a besoin.
    """
    if not m_source:
        return []

    m_source = _strip_m_comments(m_source)
    span = _find_top_level_let_block(m_source)
    if span is None:
        return []
    body_start, in_start = span

    steps: list[MStep] = []
    for raw_step, fragment_start in _split_top_level_steps(m_source, body_start, in_start):
        if not raw_step.strip():
            continue
        parsed = _split_step_name(raw_step)
        if parsed is None:
            continue
        name, raw_name, expression = parsed
        # Le fragment peut commencer par des sauts de ligne/espaces avant le
        # nom réel : on compte les lignes jusqu'au PREMIER caractère non blanc,
        # sinon l'étape serait attribuée à la ligne de la virgule précédente.
        leading = len(raw_step) - len(raw_step.lstrip())
        absolute_start = fragment_start + leading
        line_offset = m_source.count("\n", 0, absolute_start)
        steps.append(
            MStep(
                name=name,
                raw_name=raw_name,
                expression=expression,
                line_offset=line_offset,
            )
        )

    return steps


def parse_type_transform_list(raw_argument: str) -> list[tuple[str, str]]:
    """Découpe le 2e argument d'un `Table.TransformColumnTypes` en paires
    (nom de colonne, type M brut).

    Forme attendue : `{{"COL_A", Int64.Type}, {"COL_B", type text}}` — une
    liste M de paires. Retourne `[]` si la forme n'est pas reconnue (jamais
    d'exception) : au checker appelant de traiter l'absence de paire comme
    "pas de preuve de type", jamais comme "aucune colonne à vérifier".

    Le type est rendu TEL QUEL (`Int64.Type`, `type text`, ...) : c'est au
    checker de le mapper vers le contrat TMDL, et de traiter un type inconnu
    comme non résolu plutôt que de le deviner.
    """
    text = raw_argument.strip()
    if not text.startswith("{"):
        return []

    items, _end = _split_top_level_arguments(text, 0)
    pairs: list[tuple[str, str]] = []
    for item in items:
        item = item.strip()
        if not item.startswith("{"):
            continue
        parts, _ = _split_top_level_arguments(item, 0)
        if len(parts) < 2:
            continue
        name = resolve_m_string_literal(parts[0])
        if name is None:
            # Nom de colonne non littéral (expression, paramètre) : non
            # résolu statiquement, on ne devine pas de quelle colonne il
            # s'agit.
            continue
        m_type = parts[1].strip()
        if m_type:
            pairs.append((name, m_type))
    return pairs


def resolve_m_string_literal(raw_argument: str) -> str | None:
    """Si `raw_argument` est un littéral chaîne M (`"..."`), retourne sa
    valeur (guillemets internes `""` dépliés en `"`). Sinon (paramètre,
    expression, identifiant, concaténation...), retourne `None` : ce n'est
    PAS une valeur résolue statiquement — ne jamais deviner sa valeur."""
    text = raw_argument.strip()
    if len(text) < 2 or text[0] != '"' or text[-1] != '"':
        return None
    return text[1:-1].replace('""', '"')

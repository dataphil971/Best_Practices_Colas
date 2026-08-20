"""Extraction des références de colonnes dans du code DAX.

Ne construit PAS un AST DAX : uniquement ce dont BP-07 a besoin — distinguer
les références QUALIFIÉES (`Table[Colonne]`, résolues de façon fiable) des
références NON QUALIFIÉES (`[Nom]`, ambiguës par nature).

Cette distinction est le cœur de l'exigence de
Agent_BI/01_ALGORITHMES/07_RemoveUnusedFields.md :

  * §6 interdit d'utiliser un simple regex comme mécanisme unique de
    résolution — c'est-à-dire d'attribuer arbitrairement une référence à une
    colonne ;
  * §7 impose qu'une référence non résolue `[Amount]` ne soit JAMAIS
    attribuée à toutes les colonnes nommées `Amount`, et que cette ambiguïté
    « empêche un KO pour toute colonne candidate potentiellement concernée ».

L'approche retenue respecte les deux : une référence qualifiée est un usage
prouvé ; une référence non qualifiée n'est jamais convertie en usage, elle
devient un BLOQUEUR qui interdit de conclure « inutilisée » pour toute
colonne portant ce nom. Aucune attribution arbitraire n'a donc lieu.

Un vrai parseur DAX resterait supérieur (il résoudrait certaines références
non qualifiées au lieu de les bloquer, produisant plus de KO légitimes) :
l'implémentation actuelle est délibérément plus prudente, jamais plus
permissive.
"""

import re
from typing import List, Set, Tuple

# `Table[Colonne]` ou `'Nom de table'[Colonne]`.
_QUALIFIED_REFERENCE = re.compile(
    r"(?:'([^']+)'|([A-Za-z_][A-Za-z0-9_]*))\[([^\]]+)\]"
)

# `[Nom]` non précédé d'un identifiant de table ni d'un `]` (ce qui
# exclut la partie `[Colonne]` d'une référence qualifiée déjà captée).
_UNQUALIFIED_REFERENCE = re.compile(r"(?<![\w'\]])\[([^\]]+)\]")


def strip_dax_comments_and_strings(text: str) -> str:
    """Neutralise commentaires (`//`, `--`, `/* */`) et littéraux chaîne.

    Remplacés par des espaces plutôt que supprimés, pour ne jamais recoller
    deux tokens qui les encadraient (et préserver les sauts de ligne d'un
    commentaire bloc). Sans ce nettoyage, un nom de colonne cité dans un
    commentaire ou dans une chaîne compterait comme un usage réel.
    """
    out: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        char = text[i]

        if char == '"':
            j = i + 1
            while j < n:
                if text[j] == '"':
                    if j + 1 < n and text[j + 1] == '"':
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append(" " * (j - i))
            i = j
            continue

        if text[i:i + 2] in ("//", "--"):
            j = text.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
            continue

        if text[i:i + 2] == "/*":
            end = text.find("*/", i + 2)
            j = n if end == -1 else end + 2
            out.append("".join("\n" if c == "\n" else " " for c in text[i:j]))
            i = j
            continue

        out.append(char)
        i += 1

    return "".join(out)


def extract_column_references(dax: str) -> Tuple[Set[Tuple[str, str]], Set[str]]:
    """Retourne (références qualifiées, noms non qualifiés).

    - qualifiées : ensemble de (table, colonne) — usages PROUVÉS ;
    - non qualifiées : ensemble de noms bruts — AMBIGUS, à traiter comme des
      bloqueurs, jamais comme des usages.
    """
    if not dax:
        return set(), set()

    cleaned = strip_dax_comments_and_strings(dax)

    qualified: Set[Tuple[str, str]] = set()
    for match in _QUALIFIED_REFERENCE.finditer(cleaned):
        table = match.group(1) or match.group(2)
        qualified.add((table, match.group(3)))

    unqualified: Set[str] = {
        match.group(1) for match in _UNQUALIFIED_REFERENCE.finditer(cleaned)
    }

    return qualified, unqualified

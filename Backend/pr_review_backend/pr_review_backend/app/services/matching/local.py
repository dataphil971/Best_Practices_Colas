"""
Fournisseur de correspondance LOCAL (défaut) — moteur sémantique porté du
prototype (Lot 5, §6.2).

Pipeline fidèle au prototype :

  1. NORMALISATION : minuscules, suppression des accents (NFD), ponctuation,
     tokens d'une seule lettre et mots-vides FR/EN retirés.
  2. CANONICALISATION par familles de synonymes métier (Power BI / DAX / Power
     Query) : chaque variante est réduite au premier terme de sa famille
     (« measures » → « mesure », « cacher » → « masquer »…).
  3. PONDÉRATION IDF sur le référentiel : idf(t) = ln((N+1)/(df+0.5)) + 1. Les
     tokens rares et distinctifs pèsent davantage.
  4. SCORE : 0.5 · Jaccard pondéré + 0.5 · couverture pondérée du sens de la règle
     de référence (identique à la formule du prototype).

Détection de statut (OK/KO/Partiel/N-A) à partir de valeurs libres.

Aucune dépendance réseau ; fonctionne immédiatement, gratuitement.
"""
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from app.models.enums import ItemStatus
from app.services.matching.base import (
    MatchProvider,
    MatchResult,
    RuleRef,
    verdict_for,
    THRESHOLD_PROBABLE,
)

_LEXICON_PATH = Path(__file__).resolve().parents[2] / "data" / "matching_lexicon.json"

# Seuils de PRÉ-REMPLISSAGE (repris du prototype) : on applique un statut si le
# meilleur score est franc (≥ 0.30) OU s'il se détache nettement du second
# (≥ 0.18 et écart ≥ 0.10). Zone ambiguë : ≥ 0.14 mais sous ces conditions.
PREFILL_STRONG = 0.30
PREFILL_MARGIN_MIN = 0.18
PREFILL_MARGIN_GAP = 0.10
AMBIGUOUS_MIN = 0.14


@lru_cache(maxsize=1)
def _load_lexicon() -> tuple[frozenset, dict]:
    data = json.loads(_LEXICON_PATH.read_text(encoding="utf-8"))
    stopwords = frozenset(data["stopwords"])
    # canonical: chaque terme d'une famille pointe vers le 1er terme (canonique).
    canonical: dict[str, str] = {}
    for family in data["synonym_families"]:
        if not family:
            continue
        head = family[0]
        for term in family:
            canonical[term] = head
    return stopwords, canonical


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def tokenize(text: str) -> list[str]:
    """Normalise puis canonicalise un texte en une liste de tokens."""
    stopwords, canonical = _load_lexicon()
    lowered = _strip_accents((text or "").lower())
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    tokens = []
    for tok in cleaned.split():
        if len(tok) <= 1 or tok in stopwords:
            continue
        canon = canonical.get(tok)
        tokens.append(_strip_accents(canon) if canon else tok)
    return tokens


def _build_idf(referential_texts: list[str]) -> dict[str, float]:
    """idf(t) = ln((N+1)/(df+0.5)) + 1, calculé sur le référentiel."""
    import math

    n = len(referential_texts) or 1
    df: dict[str, int] = {}
    for text in referential_texts:
        for tok in set(tokenize(text)):
            df[tok] = df.get(tok, 0) + 1
    return {tok: math.log((n + 1) / (count + 0.5)) + 1 for tok, count in df.items()}


def _weighted_score(a_text: str, b_text: str, idf: dict[str, float]) -> float:
    """
    Score de similarité pondéré (formule du prototype) :
      0.5 · (intersection pondérée / union pondérée)   [Jaccard pondéré]
    + 0.5 · (poids couverts de la règle réf. / poids total de la règle réf.)
    """
    a = tokenize(a_text)
    b = tokenize(b_text)
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)

    inter_w = union_w = 0.0
    for tok in set(a) | set(b):
        w = idf.get(tok, 1.0)
        union_w += w
        if tok in sa and tok in sb:
            inter_w += w

    ref_total_w = covered_w = 0.0
    for tok in sb:  # b = texte de la règle de référence
        w = idf.get(tok, 1.0)
        ref_total_w += w
        if tok in sa:
            covered_w += w

    jaccard = (inter_w / union_w) if union_w else 0.0
    coverage = (covered_w / ref_total_w) if ref_total_w else 0.0
    return 0.5 * jaccard + 0.5 * coverage


# ------------------------------------------------------------------ statut
# Motifs de détection de statut, du plus spécifique au plus général.
_NA_PATTERNS = ("n/a", "na", "non applicable", "sans objet", "s/o", "non concerne")
_PARTIAL_PATTERNS = ("partiel", "partiellement", "en partie", "partial", "moyen", "à améliorer")
_OK_PATTERNS = ("ok", "oui", "yes", "true", "vrai", "conforme", "fait", "done", "x", "✓", "v")
_KO_PATTERNS = ("ko", "non", "no", "false", "faux", "non conforme", "nok", "à faire", "todo")


class LocalMatchProvider:
    """Fournisseur local, sans réseau. `name = 'local'`."""

    name = "local"

    def match_rules(
        self,
        imported_texts: list[str],
        referential: list[RuleRef],
    ) -> list[MatchResult]:
        ref_texts = [r.text for r in referential]
        idf = _build_idf(ref_texts)
        results: list[MatchResult] = []

        for idx, imported in enumerate(imported_texts):
            scored = sorted(
                (
                    (ref, _weighted_score(imported, ref.text, idf))
                    for ref in referential
                ),
                key=lambda pair: pair[1],
                reverse=True,
            )
            if not scored:
                results.append(MatchResult(idx, None, 0.0, "new"))
                continue

            best_ref, best = scored[0]
            second = scored[1][1] if len(scored) > 1 else 0.0

            if best >= PREFILL_STRONG or (best >= PREFILL_MARGIN_MIN and best - second >= PREFILL_MARGIN_GAP):
                results.append(
                    MatchResult(idx, best_ref.rule_version_id, round(best, 4),
                                verdict_for(best))
                )
            elif best >= AMBIGUOUS_MIN:
                # Cas ambigu : on renvoie le candidat, mais sans l'appliquer.
                results.append(
                    MatchResult(idx, best_ref.rule_version_id, round(best, 4), "probable")
                )
            else:
                results.append(MatchResult(idx, None, round(best, 4), "new"))
        return results

    def detect_status(self, raw: str) -> ItemStatus | None:
        if raw is None:
            return None
        value = _strip_accents(str(raw).strip().lower())
        if not value:
            return None
        # Ordre : N/A et Partiel d'abord (plus spécifiques), puis OK/KO.
        if any(p in value for p in _NA_PATTERNS):
            return ItemStatus.na
        if any(p in value for p in _PARTIAL_PATTERNS):
            return ItemStatus.partial
        # Correspondance exacte prioritaire pour éviter que 'v' matche 'vrai' etc.
        if value in _OK_PATTERNS:
            return ItemStatus.ok
        if value in _KO_PATTERNS:
            return ItemStatus.ko
        if any(value.startswith(p) or p in value for p in _KO_PATTERNS):
            return ItemStatus.ko
        if any(value.startswith(p) or p in value for p in _OK_PATTERNS):
            return ItemStatus.ok
        return None

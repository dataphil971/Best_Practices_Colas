"""
Fournisseur de correspondance IA (optionnel, activable par l'admin) — Lot 5, §6.3.

L'appel se fait côté serveur, dans le worker, jamais depuis le navigateur. On
n'envoie au modèle QUE les libellés de règles et de lignes — jamais de données
d'entreprise sensibles. Le secret (clé/jeton) n'est pas stocké ici : il est
résolu à l'exécution depuis le coffre via `secret_ref`.

Fournisseurs supportés (adaptateurs derrière la même interface) :
  - 'mistral'    : endpoint EU (par défaut côté IA) ;
  - 'enterprise' : IA interne (endpoint privé OpenAI-compatible) ;
  - 'openai', 'azure' : disponibles au besoin.

REPLI : si l'appel IA échoue ou dépasse le délai, on retombe automatiquement sur
le fournisseur local. L'import n'échoue jamais totalement.
"""
from __future__ import annotations

from app.models.enums import ItemStatus
from app.services.matching.base import MatchResult, RuleRef, verdict_for
from app.services.matching.local import LocalMatchProvider


class AIMatchProvider:
    """
    Adaptateur générique pour un fournisseur IA OpenAI-compatible.

    En l'absence de configuration réseau complète (endpoint + secret résolu), ou
    en cas d'erreur, il délègue TOUT au fournisseur local. C'est ce repli qui
    garantit qu'un import aboutit toujours.
    """

    def __init__(
        self,
        provider: str,
        *,
        endpoint: str | None = None,
        model: str | None = None,
        secret: str | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.name = provider
        self.endpoint = endpoint
        self.model = model
        self._secret = secret
        self.timeout = timeout_seconds
        self._fallback = LocalMatchProvider()

    # -- Détection de statut : on réutilise l'heuristique locale (robuste, gratuite).
    def detect_status(self, raw: str) -> ItemStatus | None:
        return self._fallback.detect_status(raw)

    def _is_operational(self) -> bool:
        """Vrai si l'on dispose du minimum pour appeler l'IA."""
        return bool(self.endpoint and self._secret)

    def match_rules(
        self,
        imported_texts: list[str],
        referential: list[RuleRef],
    ) -> list[MatchResult]:
        if not self._is_operational():
            # Pas de config exploitable → repli local silencieux.
            return self._fallback.match_rules(imported_texts, referential)
        try:
            return self._call_ai(imported_texts, referential)
        except Exception:
            # Repli : l'import n'échoue jamais totalement (§6.3).
            return self._fallback.match_rules(imported_texts, referential)

    # ------------------------------------------------------------------
    def _call_ai(
        self,
        imported_texts: list[str],
        referential: list[RuleRef],
    ) -> list[MatchResult]:
        """
        Appel réel au modèle (OpenAI-compatible). Envoie UNIQUEMENT les libellés
        de règles et de lignes, attend un JSON structuré
        {imported_index → rule_version_id + confiance}.

        L'appel HTTP concret est volontairement encapsulé et tolérant : toute
        anomalie remonte en exception et déclenche le repli local dans
        `match_rules`. Le batching et le cache (maîtrise du coût) se branchent ici.
        """
        import json
        import httpx

        # Prompt strict : correspondance libellé↔règle, réponse JSON pure.
        ref_catalog = [
            {"rule_version_id": r.rule_version_id, "text": r.text} for r in referential
        ]
        system = (
            "Tu es un moteur de correspondance. On te donne un référentiel de "
            "règles (id + libellé) et des lignes importées. Pour chaque ligne, "
            "renvoie le rule_version_id de la règle la plus proche et une confiance "
            "[0,1]. Réponds UNIQUEMENT par un JSON: "
            '{"matches":[{"imported_index":int,"rule_version_id":str|null,"confidence":float}]}.'
        )
        user = json.dumps(
            {"referential": ref_catalog, "imported": imported_texts},
            ensure_ascii=False,
        )

        headers = {"Authorization": f"Bearer {self._secret}",
                   "Content-Type": "application/json"}
        payload = {
            "model": self.model or "mistral-small-latest",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self.endpoint, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        valid_ids = {r.rule_version_id for r in referential}

        by_index: dict[int, MatchResult] = {}
        for m in parsed.get("matches", []):
            idx = int(m["imported_index"])
            rvid = m.get("rule_version_id")
            conf = float(m.get("confidence", 0.0))
            if rvid not in valid_ids:
                rvid = None
            by_index[idx] = MatchResult(idx, rvid, round(conf, 4), verdict_for(conf))

        # Complète les index manquants par un repli local ciblé.
        missing = [i for i in range(len(imported_texts)) if i not in by_index]
        if missing:
            local_all = self._fallback.match_rules(imported_texts, referential)
            for i in missing:
                by_index[i] = local_all[i]

        return [by_index[i] for i in range(len(imported_texts))]

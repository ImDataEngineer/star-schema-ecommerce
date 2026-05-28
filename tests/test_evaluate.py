"""IAmDataEng — rubric d'évaluation pour `modeling.star-schema-ecommerce`.

Six checks déterministes. Chaque check qui échoue produit un message
pédagogique en français pointant la cause probable.

L'ordre :
    1. adr_present         — la décision d'archi est documentée
    2. fk_coverage_static  — chaque FK sur fct_order_lines a un test relationships
    3. sqlfluff_passes     — style SQL propre, dialecte postgres
    4. dbt_build_passes    — tous les models compilent ET tous les tests dbt passent
                              (cela inclut les 3 singular tests et les generic tests)
    5. grain_unique        — vérification croisée sur la table matérialisée
    6. conformed_customer  — vérification croisée : dim_customer commun aux 2 facts

Les checks 4-6 sont redondants au sens "dbt test" — c'est volontaire. dbt teste
sur ses modèles refs ; pytest re-teste sur l'artefact persisté en base. Si l'un
des deux passe et pas l'autre, on a un bug d'écriture quelque part.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import psycopg2
import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADR_PATH = PROJECT_ROOT / "docs" / "adr" / "001-star-vs-snowflake-vs-obt.md"
MARTS_SCHEMA_PATH = PROJECT_ROOT / "models" / "marts" / "_schema.yml"

# Surrogate FKs we expect on fct_order_lines. The check verifies that each of
# these columns appears in the schema.yml AND has a `relationships` test.
EXPECTED_FACT_FKS = {
    "sk_customer",
    "sk_product",
    "sk_channel",
    "sk_country_ship",
    "order_date_key",
    "ship_date_key",
}

# Sentence required to be ABSENT in the ADR: the stub uses this placeholder,
# the learner must replace it.
ADR_PLACEHOLDER_SENTINEL = "ADR placeholder — replace before submission"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pg_connect() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ.get("PGUSER", "rundle"),
        password=os.environ.get("PGPASSWORD", "rundle_dev_password"),
        dbname=os.environ.get("PGDATABASE", "rundle_warehouse"),
    )


def _run(cmd: list[str], cwd: Path = PROJECT_ROOT, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# Module-scoped fixture: build the warehouse ONCE for the whole test session.
# Each check then queries the persisted tables or static files.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def built_warehouse():
    """Run `dbt build` end-to-end. Yields nothing; downstream tests query Postgres directly."""
    # dbt build does deps + run + test. We pin --profiles-dir to the in-repo .dbt/
    # so CI works without any user-level config.
    result = _run(
        ["dbt", "build", "--profiles-dir", ".dbt", "--target", "ci"],
        env_extra={"DBT_PROFILES_DIR": str(PROJECT_ROOT / ".dbt")},
    )
    if result.returncode != 0:
        pytest.fail(
            "Le `dbt build` a échoué.\n"
            f"stdout:\n{result.stdout[-4000:]}\n"
            f"stderr:\n{result.stderr[-2000:]}\n"
            "Astuce : lance `dbt build --profiles-dir .dbt` en local pour voir "
            "quel modèle ou quel test casse. Le premier test rouge dans la sortie "
            "dbt est ton point de départ, pas le dernier."
        )
    yield


# ---------------------------------------------------------------------------
# Check 1 — adr_present
# Static check; runs independently of dbt build.
# ---------------------------------------------------------------------------


def test_adr_present():
    """L'ADR doit exister, ne pas être vide, et le placeholder doit avoir été retiré."""
    if not ADR_PATH.exists():
        pytest.fail(
            f"Le fichier {ADR_PATH.relative_to(PROJECT_ROOT)} n'existe pas. "
            "Le projet exige un Architecture Decision Record défendant le choix "
            "star vs snowflake vs One Big Table. Le squelette est fourni dans "
            "docs/adr/001-star-vs-snowflake-vs-obt.md — remplis-le."
        )
    content = ADR_PATH.read_text(encoding="utf-8")
    if len(content.strip()) < 200:
        pytest.fail(
            "L'ADR est trop court (< 200 caractères). Un ADR qui tient sur une ligne "
            "n'est pas un ADR, c'est un commentaire. Documente Context / Decision / "
            "Consequences / Alternatives Considered (format MADR)."
        )
    if ADR_PLACEHOLDER_SENTINEL in content:
        pytest.fail(
            f"L'ADR contient encore le marqueur de stub : '{ADR_PLACEHOLDER_SENTINEL}'. "
            "Remplace le stub par ta vraie décision. Un ADR sans contenu réel ne sert "
            "qu'à faire passer le check 1 — pas l'entretien."
        )
    # Light structural check — the four MADR sections SHOULD be there in some form.
    expected_sections = ["Context", "Decision", "Consequences", "Alternatives"]
    missing = [s for s in expected_sections if s.lower() not in content.lower()]
    if missing:
        pytest.fail(
            f"L'ADR ne mentionne pas les sections MADR suivantes : {missing}. "
            "Le format MADR (Markdown Architecture Decision Record) attend au minimum "
            "Context, Decision, Consequences, Alternatives Considered. Sans 'Alternatives', "
            "ton ADR est un journal intime, pas une décision."
        )


# ---------------------------------------------------------------------------
# Check 2 — fk_coverage_static
# Reads models/marts/_schema.yml and confirms every expected FK column on
# fct_order_lines has a `relationships` test. This runs without dbt build.
# ---------------------------------------------------------------------------


def test_fk_coverage_static():
    """Chaque FK de fct_order_lines doit avoir un test `relationships` dans _schema.yml."""
    if not MARTS_SCHEMA_PATH.exists():
        pytest.fail(
            f"Fichier introuvable : {MARTS_SCHEMA_PATH.relative_to(PROJECT_ROOT)}. "
            "C'est ici que tu déclares les tests sur les modèles."
        )

    with MARTS_SCHEMA_PATH.open("r", encoding="utf-8") as f:
        schema = yaml.safe_load(f)

    models = {m["name"]: m for m in schema.get("models", [])}
    if "fct_order_lines" not in models:
        pytest.fail(
            "Le modèle `fct_order_lines` n'est pas déclaré dans models/marts/_schema.yml. "
            "Ajoute son entrée avec une `description` qui explicite le grain "
            "(une ligne par (order_id, line_number)) et la liste des colonnes."
        )

    fact = models["fct_order_lines"]
    declared_columns = {c["name"]: c for c in fact.get("columns", [])}

    missing_columns = EXPECTED_FACT_FKS - declared_columns.keys()
    if missing_columns:
        pytest.fail(
            f"Colonnes FK manquantes dans la déclaration de fct_order_lines : "
            f"{sorted(missing_columns)}. Chaque FK surrogate (sk_*) et chaque date_key "
            "doit apparaître dans _schema.yml AVEC un test `relationships` vers le bon dim. "
            "Sans cette déclaration, dbt ne peut pas tester l'intégrité référentielle."
        )

    missing_relationships = []
    for fk in EXPECTED_FACT_FKS:
        col = declared_columns[fk]
        tests = col.get("tests", []) or []
        has_relationships = any(
            isinstance(t, dict) and "relationships" in t for t in tests
        )
        if not has_relationships:
            missing_relationships.append(fk)

    if missing_relationships:
        pytest.fail(
            f"Les colonnes suivantes de fct_order_lines n'ont PAS de test `relationships` "
            f"dans _schema.yml : {sorted(missing_relationships)}. "
            "Exemple de test à ajouter sous une colonne sk_channel :\n\n"
            "  - name: sk_channel\n"
            "    tests:\n"
            "      - not_null\n"
            "      - relationships:\n"
            "          to: ref('dim_channel')\n"
            "          field: sk_channel\n\n"
            "Note : order_date_key ET ship_date_key pointent TOUS LES DEUX vers "
            "ref('dim_date') — c'est ça, le role-playing."
        )


# ---------------------------------------------------------------------------
# Check 3 — sqlfluff_passes
# Lint the models directory against the committed .sqlfluff config.
# ---------------------------------------------------------------------------


def test_sqlfluff_passes():
    """sqlfluff lint sur models/ doit retourner 0."""
    result = _run(
        ["sqlfluff", "lint", "models/", "--dialect", "postgres"],
    )
    if result.returncode != 0:
        # First ~40 lines of stdout usually contain the offending file and rule.
        snippet = "\n".join(result.stdout.splitlines()[:40])
        pytest.fail(
            "sqlfluff a relevé des violations de style.\n"
            f"Extrait :\n{snippet}\n\n"
            "Lance `sqlfluff fix models/` en local pour auto-corriger ce qui peut l'être, "
            "puis re-lint pour voir ce qui reste. La config est dans `.sqlfluff` à la racine — "
            "ne la modifie pas pour faire passer le test, corrige ton SQL."
        )


# ---------------------------------------------------------------------------
# Check 4 — dbt_build_passes
# Implicit via the `built_warehouse` fixture — if dbt build failed, the
# fixture would have called pytest.fail. This test asserts the fixture ran.
# ---------------------------------------------------------------------------


def test_dbt_build_passes(built_warehouse):
    """dbt build (run + test) doit passer sans erreur. La fixture l'a exécuté."""
    # If we reached this line, the fixture succeeded. This test exists so the
    # rubric explicitly lists "dbt build" as a check rather than burying it
    # inside another test's setup.
    assert True


# ---------------------------------------------------------------------------
# Check 5 — grain_unique
# Cross-check on the persisted fact: (order_id, line_number) must be unique.
# Redundant with the singular dbt test tests/grain_order_line.sql — that's the
# point. We assert the same invariant from a different angle.
# ---------------------------------------------------------------------------


def test_grain_unique(built_warehouse):
    """fct_order_lines doit avoir un row count == COUNT(DISTINCT (order_id, line_number))."""
    with _pg_connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM marts.fct_order_lines")
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT order_id, line_number FROM marts.fct_order_lines) sub"
        )
        distinct = cur.fetchone()[0]

    if total == 0:
        pytest.fail(
            "marts.fct_order_lines est vide. Soit ton modèle de fact ne produit "
            "aucune ligne (vérifie les WHERE false du squelette), soit la jointure "
            "vers dim_customer drop toutes les lignes. Lance `dbt run --select fct_order_lines` "
            "et inspecte le SQL compilé dans target/run/."
        )
    if total != distinct:
        delta = total - distinct
        pytest.fail(
            f"Grain violé sur fct_order_lines : {total} lignes au total, "
            f"{distinct} couples (order_id, line_number) distincts (+{delta} doublons).\n"
            "Cause la plus fréquente : tu as joint dim_customer (ou dim_product) sans avoir "
            "dédupliqué le dim sur sa clé naturelle. Si dim_customer a 2 lignes pour le même "
            "customer_id (par exemple parce que tu as UNION ALL un sentinel 'unknown' deux fois), "
            "chaque ligne du fact est doublée. Vérifie que tes dims passent leur test `unique` "
            "sur la clé naturelle ET la clé surrogate."
        )


# ---------------------------------------------------------------------------
# Check 6 — conformed_customer
# Every sk_customer in fct_returns MUST resolve in dim_customer (the SAME dim).
# This is the conformed-dim invariant materialised across two facts.
# ---------------------------------------------------------------------------


def test_conformed_customer(built_warehouse):
    """sk_customer présent dans fct_returns doit être joinable depuis dim_customer."""
    with _pg_connect() as conn, conn.cursor() as cur:
        # Detect: any sk_customer in fct_returns not present in dim_customer?
        cur.execute(
            """
            select count(*)
            from marts.fct_returns fr
            left join marts.dim_customer dc
                on dc.sk_customer = fr.sk_customer
            where dc.sk_customer is null
            """
        )
        orphan_count = cur.fetchone()[0]

    if orphan_count > 0:
        pytest.fail(
            f"{orphan_count} ligne(s) de fct_returns ont un sk_customer absent de dim_customer.\n"
            "C'est exactement le bug que le critère de 'dimensions conformées' empêche : "
            "tu as construit dim_customer en filtrant les clients 'inactifs', mais fct_returns "
            "référence ces mêmes clients. Soit tu ne filtres jamais dim_customer par activité "
            "(préférence Kimball), soit tu ajoutes un sentinel 'unknown customer' partagé par "
            "les deux facts. Une troisième option — créer dim_customer_active vs dim_customer_all "
            "— est exactement ce que les dimensions conformées interdisent."
        )

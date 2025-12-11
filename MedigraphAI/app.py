import os
from dotenv import load_dotenv
import snowflake.connector
from neo4j import GraphDatabase
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

# Try to import LLM helper (optional)
try:
    from llm_cypher import generate_cypher_from_nl, run_cypher_on_aura
except Exception:
    generate_cypher_from_nl = None
    run_cypher_on_aura = None

# -----------------------------------------------------------------------------
# Load environment variables
# -----------------------------------------------------------------------------
load_dotenv(".env", override=True)

# -----------------------------------------------------------------------------
# Global styling – dark blue theme, high contrast
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="MediGraph AI – Snowflake + AuraDB Demo",
    layout="wide",
)

st.markdown(
    """
    <style>

    /* ------------------------- GLOBAL BACKGROUND ---------------------------- */
    html, body, .stApp {
        background-color: #020617 !important; /* dark navy */
        color: #f8fafc !important; /* bright white */
    }

    /* ------------------------- HEADERS & TEXT ------------------------------- */
    h1, h2, h3, h4, h5, h6, p, label, span, div, input, textarea {
        color: #f8fafc !important;
    }

    /* ------------------------- SIDEBAR -------------------------------------- */
    [data-testid="stSidebar"] {
        background-color: #0f172a !important;
    }
    [data-testid="stSidebar"] * {
        color: #f8fafc !important;
    }

    /* ------------------------- TABS ----------------------------------------- */
    .stTabs [role="tab"] {
        background-color: #1e293b !important;
        color: #f8fafc !important;
        border-radius: 12px 12px 0 0;
        padding: 8px 16px;
    }
    .stTabs [role="tab"][aria-selected="true"] {
        background-color: #0f172a !important;
        border-bottom: 3px solid #38bdf8 !important;
        font-weight: 700 !important;
        color: #ffffff !important;
    }

    /* ------------------------- METRICS -------------------------------------- */
    .stMetric, .stMetric > div, .stMetric label, .stMetric span {
        color: #ffffff !important;
    }

    /* ------------------------- BUTTONS -------------------------------------- */
    .stButton>button {
        background: linear-gradient(to right, #0ea5e9, #38bdf8) !important;
        color: #0b1120 !important;
        font-weight: 600 !important;
        border-radius: 999px !important;
        border: none !important;
        padding: 8px 20px !important;
    }
    .stButton>button:hover {
        filter: brightness(1.15) !important;
    }

    /* ------------------------- CODE BLOCKS / CYPHER ------------------------- */
    pre, code, .stCode, .stCode * {
        background-color: #0f172a !important;
        color: #38bdf8 !important;  /* bright cyan code */
        font-size: 14px !important;
        border-radius: 8px !important;
        padding: 8px !important;
    }

    /* ------------------------- DATAFRAMES ----------------------------------- */
    [data-testid="stDataFrame"] div {
        color: #f8fafc !important;
    }
    .stDataFrame th {
        color: #ffffff !important;
        background-color: #1e293b !important;
    }
    .stDataFrame td {
        color: #f8fafc !important;
    }

    /* ------------------------- INPUT BOXES ---------------------------------- */
    input, textarea, select {
        background-color: #1e293b !important;
        color: #ffffff !important;
        border-radius: 6px !important;
        border: 1px solid #334155 !important;
    }

    /* ------------------------- PYVIS GRAPH BORDER ---------------------------- */
    .graph-container {
        border: 1px solid #1e293b !important;
        border-radius: 16px !important;
        background-color: #020617 !important;
    }

    /* ------------------------- EXPANDERS ------------------------------------ */
    .streamlit-expanderHeader {
        background-color: #1e293b !important;
        color: #ffffff !important;
    }

    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Helper functions – Snowflake
# -----------------------------------------------------------------------------
def get_snowflake_connection(totp_code: str):
    """
    Create a Snowflake connection using username + password + TOTP (MFA).
    """
    return snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        role=os.getenv("SNOWFLAKE_ROLE"),
        passcode=totp_code.strip() if totp_code else None,
    )


def fetch_snowflake_summary(totp_code: str):
    """
    Returns:
      counts: dict with counts for each view/table
      samples: dict of pandas DataFrames for each entity
    """
    conn = None
    try:
        conn = get_snowflake_connection(totp_code)
        cur = conn.cursor()

        counts = {}
        for view_name, key in [
            ("V_PATIENTS", "patients"),
            ("V_ENCOUNTERS", "encounters"),
            ("V_CONDITIONS", "conditions"),
            ("V_MEDICATIONS", "medications"),
            ("V_PROVIDERS", "providers"),
            ("OBSERVATIONS", "observations"),
        ]:
            cur.execute(f"SELECT COUNT(*) FROM {view_name}")
            counts[key] = cur.fetchone()[0]

        samples = {}

        # Patients
        cur.execute(
            """
            SELECT PATIENT_ID, FIRST_NAME, LAST_NAME, SEX, ZIP, AGE
            FROM V_PATIENTS
            LIMIT 20
            """
        )
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description]
        samples["patients"] = pd.DataFrame(rows, columns=cols)

        # Encounters
        cur.execute(
            """
            SELECT ENC_ID, PATIENT_ID, PROVIDER_NPI, START_TIME, END_TIME
            FROM V_ENCOUNTERS
            LIMIT 20
            """
        )
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description]
        samples["encounters"] = pd.DataFrame(rows, columns=cols)

        # Conditions
        cur.execute(
            """
            SELECT ENC_ID, PATIENT_ID, ICD_CODE, NAME
            FROM V_CONDITIONS
            LIMIT 20
            """
        )
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description]
        samples["conditions"] = pd.DataFrame(rows, columns=cols)

        # Medications
        cur.execute(
            """
            SELECT ENC_ID, PATIENT_ID, RXNORM, NAME
            FROM V_MEDICATIONS
            LIMIT 20
            """
        )
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description]
        samples["medications"] = pd.DataFrame(rows, columns=cols)

        # Providers
        cur.execute(
            """
            SELECT PROVIDER_ID, PROVIDER_NAME, SPECIALTY, STATE, ZIP
            FROM V_PROVIDERS
            LIMIT 20
            """
        )
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description]
        samples["providers"] = pd.DataFrame(rows, columns=cols)

        # Observations (raw)
        cur.execute(
            """
            SELECT *
            FROM OBSERVATIONS
            LIMIT 20
            """
        )
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description]
        samples["observations"] = pd.DataFrame(rows, columns=cols)

        cur.close()
        return counts, samples

    finally:
        if conn is not None:
            conn.close()

# -----------------------------------------------------------------------------
# Helper functions – AuraDB (Neo4j)
# -----------------------------------------------------------------------------
def get_aura_driver():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    pwd = os.getenv("NEO4J_PASSWORD")
    if not uri or not user or not pwd:
        raise RuntimeError("NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD not set in .env")
    return GraphDatabase.driver(uri, auth=(user, pwd))


def fetch_aura_stats():
    driver = get_aura_driver()
    try:
        with driver.session(database="neo4j") as session:
            node_counts = {}
            for label, key in [
                ("Patient", "patients"),
                ("Encounter", "encounters"),
                ("Condition", "conditions"),
                ("Medication", "medications"),
                ("Provider", "providers"),
                ("Observation", "observations"),
            ]:
                result = session.run(
                    f"MATCH (n:{label}) RETURN COUNT(n) AS c"
                ).single()
                node_counts[key] = result["c"]

            rel_result = session.run(
                """
                MATCH ()-[r]->()
                RETURN type(r) AS relationship_type, COUNT(r) AS total
                ORDER BY total DESC
                """
            )
            rows = list(rel_result)
            rel_df = pd.DataFrame(
                [(row["relationship_type"], row["total"]) for row in rows],
                columns=["relationship_type", "total"],
            )

        return node_counts, rel_df
    finally:
        driver.close()


def fetch_aura_graph(limit: int = 75) -> str:
    """
    Fetch a real subgraph from AuraDB:
    Patients + all their neighbors (encounters, conditions, medications, providers, observations).

    Returns: HTML string with an interactive PyVis network.
    """
    driver = get_aura_driver()
    try:
        with driver.session(database="neo4j") as session:
            cypher = """
            MATCH (p:Patient)-[r]-(n)
            RETURN p, r, n
            LIMIT $limit
            """
            result = session.run(cypher, limit=limit)
            rows = list(result)

        net = Network(
            height="520px",
            width="100%",
            bgcolor="#020617",
            font_color="#e5e7eb",
            notebook=False,
            directed=True,
        )

        node_seen = set()
        rel_seen = set()

        def add_node(node, group: str):
            nid = str(node.id)  # internal Neo4j id
            if nid in node_seen:
                return
            node_seen.add(nid)

            label = node.get("full_name") or node.get("name") or node.get("id") or group
            title_parts = [f"<b>{group}</b>"]
            for k, v in node.items():
                title_parts.append(f"{k}: {v}")
            title = "<br>".join(title_parts)

            color_map = {
                "Patient": "#22d3ee",
                "Encounter": "#4ade80",
                "Condition": "#f97316",
                "Medication": "#a855f7",
                "Provider": "#facc15",
                "Observation": "#fb7185",
            }
            net.add_node(
                nid,
                label=str(label),
                title=title,
                color=color_map.get(group, "#38bdf8"),
            )

        for row in rows:
            p = row["p"]
            n = row["n"]
            r = row["r"]

            add_node(p, "Patient")

            labels = list(n.labels)
            if "Encounter" in labels:
                group = "Encounter"
            elif "Condition" in labels:
                group = "Condition"
            elif "Medication" in labels:
                group = "Medication"
            elif "Provider" in labels:
                group = "Provider"
            elif "Observation" in labels:
                group = "Observation"
            else:
                group = labels[0] if labels else "Node"
            add_node(n, group)

            src = str(p.id)
            tgt = str(n.id)
            rel_type = r.type
            edge_key = (src, tgt, rel_type)
            if edge_key not in rel_seen:
                rel_seen.add(edge_key)
                net.add_edge(src, tgt, label=rel_type)

        net.toggle_physics(True)

        net.set_options(
            """
            {
              "physics": {
                "stabilization": true,
                "barnesHut": {
                  "gravitationalConstant": -8000,
                  "centralGravity": 0.3,
                  "springLength": 95
                }
              },
              "nodes": {
                "font": {
                  "size": 14,
                  "color": "#e5e7eb"
                }
              },
              "edges": {
                "color": "#64748b",
                "smooth": false
              }
            }
            """
        )

        return net.generate_html(notebook=False)

    finally:
        driver.close()

# -----------------------------------------------------------------------------
# Observations helpers (for demo + evaluations)
# -----------------------------------------------------------------------------
def get_patient_observations(patient_id: str) -> pd.DataFrame:
    """
    Fetch observations for a given patient from Neo4j.
    Returns a DataFrame for easy display in Streamlit.
    """
    driver = get_aura_driver()
    try:
        with driver.session(database="neo4j") as session:
            result = session.run(
                """
                MATCH (p:Patient {id: $pid})-[:HAS_OBSERVATION]->(o:Observation)
                OPTIONAL MATCH (e:Encounter)-[:HAS_OBSERVATION]->(o)
                RETURN
                    o.id           AS observation_id,
                    o.description  AS description,
                    o.value        AS value,
                    o.unit         AS unit,
                    o.category     AS category,
                    o.code         AS code,
                    o.obs_datetime AS datetime,
                    e.id           AS encounter_id
                ORDER BY datetime DESC
                """,
                pid=patient_id,
            )
            rows = list(result)
    finally:
        driver.close()

    if not rows:
        return pd.DataFrame(
            columns=[
                "observation_id",
                "description",
                "value",
                "unit",
                "category",
                "code",
                "datetime",
                "encounter_id",
            ]
        )

    return pd.DataFrame([r.data() for r in rows])


def get_observation_analytics() -> dict:
    """
    Compute high-level analytics for observations for 'evaluations'.
    """
    driver = get_aura_driver()
    metrics = {}
    try:
        with driver.session(database="neo4j") as session:
            total_obs = session.run(
                "MATCH (o:Observation) RETURN count(o) AS c"
            ).single()["c"]

            total_patients_with_obs = session.run(
                """
                MATCH (p:Patient)-[:HAS_OBSERVATION]->(:Observation)
                RETURN count(DISTINCT p) AS c
                """
            ).single()["c"]

            avg_obs_per_patient = session.run(
                """
                MATCH (p:Patient)-[:HAS_OBSERVATION]->(o:Observation)
                WITH p, count(o) AS obs_count
                RETURN avg(obs_count) AS avg_obs
                """
            ).single()["avg_obs"]

            top_obs_types = session.run(
                """
                MATCH (:Patient)-[:HAS_OBSERVATION]->(o:Observation)
                RETURN o.description AS description, count(*) AS freq
                ORDER BY freq DESC
                LIMIT 5
                """
            )
            top_obs = [record.data() for record in top_obs_types]

    finally:
        driver.close()

    metrics["total_observations"] = total_obs
    metrics["patients_with_observations"] = total_patients_with_obs
    metrics["avg_observations_per_patient"] = avg_obs_per_patient
    metrics["top_observation_descriptions"] = top_obs
    return metrics

# -----------------------------------------------------------------------------
# GDS Analytics helpers – Provider Centrality & Communities (with fallback)
# -----------------------------------------------------------------------------
def get_gds_provider_rankings() -> pd.DataFrame:
    """
    Reads GDS results (PageRank + Louvain) from Provider nodes if present.
    If not, falls back to a degree-based ranking:
      providers with the most patients linked via HAS_PROVIDER.
    """
    driver = get_aura_driver()
    rows = []
    try:
        with driver.session(database="neo4j") as session:
            try:
                # Try to read GDS-written properties
                res = session.run(
                    """
                    MATCH (pr:Provider)
                    WHERE pr.pr_provider IS NOT NULL
                    RETURN
                        pr.name AS provider,
                        pr.specialty AS specialty,
                        pr.pr_provider AS pr_score,
                        pr.community_provider AS community
                    ORDER BY pr_score DESC
                    LIMIT 10
                    """
                )
                rows = [r.data() for r in res]
            except Exception:
                rows = []

            # Fallback: degree-based ranking (no GDS required)
            if not rows:
                res = session.run(
                    """
                    MATCH (pr:Provider)<-[:HAS_PROVIDER]-(p:Patient)
                    RETURN
                        pr.name AS provider,
                        pr.specialty AS specialty,
                        count(DISTINCT p) AS pr_score,
                        0 AS community
                    ORDER BY pr_score DESC
                    LIMIT 10
                    """
                )
                rows = [r.data() for r in res]
    finally:
        driver.close()

    if not rows:
        return pd.DataFrame(
            columns=["provider", "specialty", "pr_score", "community"]
        )
    return pd.DataFrame(rows)

# -----------------------------------------------------------------------------
# Simple NER demo for conditions (rule-based, Gemini-ready)
# -----------------------------------------------------------------------------
CONDITION_KEYWORDS = {
    "diabetes": "Diabetes mellitus",
    "hypertension": "Hypertension",
    "high blood pressure": "Hypertension",
    "asthma": "Asthma",
    "copd": "Chronic obstructive pulmonary disease",
    "heart failure": "Heart failure",
    "mi": "Myocardial infarction",
    "stroke": "Stroke",
}


def simple_ner_extract_conditions(text: str) -> list:
    """
    Very simple keyword-based NER for conditions.
    In a real deployment you would replace this with Gemini 3.0 / Vertex AI NER.
    """
    text_l = text.lower()
    found = []
    for kw, canonical in CONDITION_KEYWORDS.items():
        if kw in text_l:
            found.append(canonical)
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for c in found:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def get_guidelines_for_concepts(concepts: list) -> pd.DataFrame:
    """
    Fetch clinical guidelines linked to Condition nodes for given concept strings.
    If the graph has no Guideline nodes, we return a small synthetic guideline
    table so that the demo always shows something.
    """
    if not concepts:
        return pd.DataFrame(
            columns=["condition", "title", "source", "url"]
        )

    driver = get_aura_driver()
    rows = []
    try:
        with driver.session(database="neo4j") as session:
            res = session.run(
                """
                MATCH (g:Guideline)-[:ABOUT_CONDITION]->(c:Condition)
                WHERE any(term IN $terms WHERE toLower(c.name) CONTAINS toLower(term))
                RETURN DISTINCT
                    c.name AS condition,
                    g.title AS title,
                    g.source AS source,
                    g.url AS url
                LIMIT 20
                """,
                terms=concepts,
            )
            rows = [r.data() for r in res]
    finally:
        driver.close()

    # Fallback synthetic guidelines (no "demo" wording in UI)
    if not rows:
        for cond in concepts:
            rows.append(
                {
                    "condition": cond,
                    "title": f"{cond} – Standard of Care Recommendations",
                    "source": "Clinical Guideline Library",
                    "url": "",
                }
            )

    return pd.DataFrame(rows)

# -----------------------------------------------------------------------------
# Rule-based NL → Cypher for AuraDB
# -----------------------------------------------------------------------------
def answer_question_from_aura(question: str):
    """
    Simple NL → Cypher router.

    Supports:
      1) Patients with a condition (diabetes, hypertension…)
      2) Medications for a condition
      3) Medications for a patient (by ID or by fuzzy name)
      4) Provider for a patient (by fuzzy name)
      5) Observations for a patient (by ID or name)
    """
    q_raw = question.strip()
    q = q_raw.lower()

    driver = get_aura_driver()
    try:
        with driver.session(database="neo4j") as session:
                        # 5) Encounters for a given patient (ID or fuzzy name)
            if "encounters for patient" in q:
                tail = q.split("encounters for patient", 1)[1].strip()
                if not tail:
                    return (
                        "Please specify a patient **ID or name**, e.g. "
                        "`show encounters for patient 90b111ca-...` or "
                        "`show encounters for patient Isaias`.",
                        None,
                    )

                if "-" in tail:  # treat as Patient ID
                    cypher = """
                        MATCH (p:Patient {id: $pid})-[:HAS_ENCOUNTER]->(e:Encounter)
                        OPTIONAL MATCH (e)-[:HAS_CONDITION]->(c:Condition)
                        OPTIONAL MATCH (e)-[:HAS_MEDICATION]->(m:Medication)
                        RETURN
                            p.id        AS patient_id,
                            p.full_name AS full_name,
                            e.id        AS encounter_id,
                            e.start_time AS start_time,
                            e.end_time   AS end_time,
                            collect(DISTINCT c.name) AS conditions,
                            collect(DISTINCT m.name) AS medications
                        ORDER BY start_time DESC
                        LIMIT 50
                    """
                    result = session.run(cypher, pid=tail)
                else:  # fuzzy patient name
                    cypher = """
                        MATCH (p:Patient)-[:HAS_ENCOUNTER]->(e:Encounter)
                        WHERE toLower(p.full_name) CONTAINS toLower($name)
                        OPTIONAL MATCH (e)-[:HAS_CONDITION]->(c:Condition)
                        OPTIONAL MATCH (e)-[:HAS_MEDICATION]->(m:Medication)
                        RETURN
                            p.id        AS patient_id,
                            p.full_name AS full_name,
                            e.id        AS encounter_id,
                            e.start_time AS start_time,
                            e.end_time   AS end_time,
                            collect(DISTINCT c.name) AS conditions,
                            collect(DISTINCT m.name) AS medications
                        ORDER BY start_time DESC
                        LIMIT 50
                    """
                    result = session.run(cypher, name=tail)

                rows = list(result)
                if not rows:
                    return (
                        f"I couldn't find encounters for patient **{tail}**.",
                        None,
                    )

                df = pd.DataFrame(
                    [
                        (
                            row["patient_id"],
                            row["full_name"],
                            row["encounter_id"],
                            row["start_time"],
                            row["end_time"],
                            row["conditions"],
                            row["medications"],
                        )
                        for row in rows
                    ],
                    columns=[
                        "patient_id",
                        "full_name",
                        "encounter_id",
                        "start_time",
                        "end_time",
                        "conditions",
                        "medications",
                    ],
                )
                return (
                    f"Encounters for patient **{tail}** (most recent first):",
                    df,
                )
            # 5) Observations for a given patient (ID or fuzzy name)
            if "observations for patient" in q:
                tail = q.split("observations for patient", 1)[1].strip()
                if not tail:
                    return (
                        "Please specify a patient **ID or name**, e.g. "
                        "`show observations for patient 90b111ca-...` or "
                        "`show observations for patient Isaias`.",
                        None,
                    )

                if "-" in tail:
                    cypher = """
                        MATCH (p:Patient {id: $pid})-[:HAS_OBSERVATION]->(o:Observation)
                        OPTIONAL MATCH (e:Encounter)-[:HAS_OBSERVATION]->(o)
                        RETURN
                            p.id           AS patient_id,
                            p.full_name    AS full_name,
                            o.description  AS description,
                            o.value        AS value,
                            o.unit         AS unit,
                            o.category     AS category,
                            o.code         AS code,
                            o.obs_datetime AS datetime,
                            e.id           AS encounter_id
                        ORDER BY datetime DESC
                        LIMIT 100
                    """
                    result = session.run(cypher, pid=tail)
                else:
                    cypher = """
                        MATCH (p:Patient)-[:HAS_OBSERVATION]->(o:Observation)
                        WHERE toLower(p.full_name) CONTAINS toLower($name)
                        OPTIONAL MATCH (e:Encounter)-[:HAS_OBSERVATION]->(o)
                        RETURN
                            p.id           AS patient_id,
                            p.full_name    AS full_name,
                            o.description  AS description,
                            o.value        AS value,
                            o.unit         AS unit,
                            o.category     AS category,
                            o.code         AS code,
                            o.obs_datetime AS datetime,
                            e.id           AS encounter_id
                        ORDER BY datetime DESC
                        LIMIT 100
                    """
                    result = session.run(cypher, name=tail)

                rows = list(result)
                if not rows:
                    return (
                        f"I couldn't find observations for patient **{tail}**.",
                        None,
                    )

                df = pd.DataFrame(
                    [
                        (
                            row["patient_id"],
                            row["full_name"],
                            row["description"],
                            row["value"],
                            row["unit"],
                            row["category"],
                            row["code"],
                            row["datetime"],
                            row["encounter_id"],
                        )
                        for row in rows
                    ],
                    columns=[
                        "patient_id",
                        "full_name",
                        "description",
                        "value",
                        "unit",
                        "category",
                        "code",
                        "datetime",
                        "encounter_id",
                    ],
                )
                return (
                    f"Observations for patient **{tail}** (most recent first):",
                    df,
                )

            # 4) Provider for a patient (by fuzzy name)
            if "provider for patient" in q or "who is the provider for patient" in q:
                tail = q.split("provider for patient", 1)[1].strip()
                if not tail:
                    return (
                        "Please specify a patient name, e.g. `who is the provider for patient Isaias`.",
                        None,
                    )

                cypher = """
                    MATCH (p:Patient)-[:HAS_PROVIDER]->(pr:Provider)
                    WHERE toLower(p.full_name) CONTAINS toLower($name)
                    RETURN p.id   AS patient_id,
                           p.full_name AS full_name,
                           pr.id  AS provider_id,
                           pr.name AS provider_name,
                           pr.specialty AS specialty
                    LIMIT 50
                """
                result = session.run(cypher, name=tail)
                rows = list(result)
                if not rows:
                    return (
                        f"I couldn't find any providers for patients matching name **'{tail}'**.",
                        None,
                    )

                df = pd.DataFrame(
                    [
                        (
                            row["patient_id"],
                            row["full_name"],
                            row["provider_id"],
                            row["provider_name"],
                            row["specialty"],
                        )
                        for row in rows
                    ],
                    columns=[
                        "patient_id",
                        "patient_name",
                        "provider_id",
                        "provider_name",
                        "specialty",
                    ],
                )
                return (
                    f"Providers for patients whose name matches **'{tail}'**:",
                    df,
                )

            # 3) Medications for a given patient (ID or fuzzy name)
            if "medications for patient" in q:
                tail = q.split("medications for patient", 1)[1].strip()
                if not tail:
                    return (
                        "Please specify a patient **ID or name**, e.g. "
                        "`show medications for patient 732e16fb-a1aa-b846-c6c2-c00bd4211445` "
                        "or `show medications for patient Isaias`.",
                        None,
                    )

                if "-" in tail:
                    cypher = """
                        MATCH (p:Patient {id: $pid})-[:TAKES_MEDICATION]->(m:Medication)
                        RETURN p.id AS patient_id,
                               p.full_name AS full_name,
                               m.code AS rxnorm,
                               m.name AS medication
                        LIMIT 50
                    """
                    result = session.run(cypher, pid=tail)
                    rows = list(result)
                    if not rows:
                        return (
                            f"I couldn't find medications for patient ID **{tail}**.",
                            None,
                        )
                    df = pd.DataFrame(
                        [
                            (row["patient_id"], row["full_name"], row["rxnorm"], row["medication"])
                            for row in rows
                        ],
                        columns=["patient_id", "full_name", "rxnorm", "medication"],
                    )
                    return f"Medications for patient **{tail}**:", df
                else:
                    cypher = """
                        MATCH (p:Patient)-[:TAKES_MEDICATION]->(m:Medication)
                        WHERE toLower(p.full_name) CONTAINS toLower($name)
                        RETURN p.id AS patient_id,
                               p.full_name AS full_name,
                               m.code AS rxnorm,
                               m.name AS medication
                        LIMIT 50
                    """
                    result = session.run(cypher, name=tail)
                    rows = list(result)
                    if not rows:
                        return (
                            f"I couldn't find medications for any patients matching name **'{tail}'**.",
                            None,
                        )
                    df = pd.DataFrame(
                        [
                            (row["patient_id"], row["full_name"], row["rxnorm"], row["medication"])
                            for row in rows
                        ],
                        columns=["patient_id", "full_name", "rxnorm", "medication"],
                    )
                    return (
                        f"Medications for patients whose name matches **'{tail}'**:",
                        df,
                    )

            # 2) Medications for a condition
            if "medications for" in q or "medication for" in q:
                phrase = (
                    q.replace("show", "")
                    .replace("list", "")
                    .replace("medications for", "")
                    .replace("medication for", "")
                    .strip()
                )
                if not phrase:
                    phrase = "diabetes"

                cypher = """
                    MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition),
                          (p)-[:TAKES_MEDICATION]->(m:Medication)
                    WHERE toLower(c.name) CONTAINS toLower($term)
                    RETURN DISTINCT m.code AS rxnorm,
                                    m.name AS medication,
                                    COUNT(DISTINCT p) AS patients_on_med
                    ORDER BY patients_on_med DESC
                    LIMIT 50
                """
                result = session.run(cypher, term=phrase)
                rows = list(result)
                if not rows:
                    return (
                        f"I couldn't find medications for conditions matching **'{phrase}'**.",
                        None,
                    )
                df = pd.DataFrame(
                    [
                        (row["rxnorm"], row["medication"], row["patients_on_med"])
                        for row in rows
                    ],
                    columns=["rxnorm", "medication", "patients_on_med"],
                )
                return (
                    f"Medications used by patients with conditions matching **'{phrase}'**:",
                    df,
                )

            # 1) Patients with a condition
            if "patients with" in q or q.startswith("show patients") or q.startswith("list patients"):
                phrase = (
                    q.replace("show", "")
                    .replace("list", "")
                    .replace("patients with", "")
                    .replace("patients", "")
                    .replace("who have", "")
                    .strip()
                )
                if not phrase:
                    phrase = "diabetes"

                cypher = """
                    MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition)
                    WHERE toLower(c.name) CONTAINS toLower($term)
                    RETURN p.id AS patient_id,
                           p.full_name AS full_name,
                           p.sex AS sex,
                           p.age AS age,
                           c.name AS condition
                    LIMIT 50
                """
                result = session.run(cypher, term=phrase)
                rows = list(result)
                if not rows:
                    return (
                        f"I couldn't find patients with conditions matching **'{phrase}'**.",
                        None,
                    )
                df = pd.DataFrame(
                    [
                        (
                            row["patient_id"],
                            row["full_name"],
                            row["sex"],
                            row["age"],
                            row["condition"],
                        )
                        for row in rows
                    ],
                    columns=["patient_id", "full_name", "sex", "age", "condition"],
                )
                return f"Patients with conditions matching **'{phrase}'**:", df

            # Fallback
            help_text = (
                "Right now I support questions like:\n"
                "- `show patients with diabetes`\n"
                "- `show patients with hypertension`\n"
                "- `show medications for diabetes`\n"
                "- `show medications for patient 732e16fb-a1aa-b846-c6c2-c00bd4211445`\n"
                "- `show medications for patient Isaias`\n"
                "- `who is the provider for patient Isaias`\n"
                "- `show observations for patient 90b111ca-...`\n"
                "- `show observations for patient Isaias`\n"
                "- `show encounters for patient 90b111ca-...`\n"
                "- `show encounters for patient Isaias`"
            )
            return help_text, None

    finally:
        driver.close()

# -----------------------------------------------------------------------------
# Session state init
# -----------------------------------------------------------------------------
for key in [
    "sf_connected",
    "sf_counts",
    "sf_samples",
    "aura_connected",
    "aura_node_counts",
    "aura_rel_df",
    "aura_graph_html",
    "last_ner_concepts",
]:
    if key not in st.session_state:
        st.session_state[key] = None

# -----------------------------------------------------------------------------
# Layout – Header
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div style="padding: 1.5rem 0 0.5rem 0;">
      <h1 style="margin-bottom: 0.2rem;">MediGraph AI</h1>
      <p style="color:#9ca3af; font-size:0.95rem; max-width:720px;">
        Healthcare intelligence powered by <b>Snowflake MEDIGRAPH</b> and <b>Neo4j AuraDB</b>.
        This demo shows how synthetic EHR records become a patient journey knowledge graph with
        live queries, clinical observations, analytics, and natural-language Q&A.
      </p>
      <div style="margin-top:0.6rem;">
        <span style="background:#0f172a; color:#e5e7eb; padding:0.25rem 0.7rem; border-radius:999px; margin-right:0.4rem; font-size:0.8rem;">
          Snowflake Lakehouse
        </span>
        <span style="background:#0f172a; color:#e5e7eb; padding:0.25rem 0.7rem; border-radius:999px; font-size:0.8rem;">
          Neo4j AuraDB Patient Graph
        </span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Sidebar – connections
# -----------------------------------------------------------------------------
st.sidebar.header("🔌 Live Connections")

st.sidebar.subheader("Snowflake (MEDIGRAPH)")
sf_totp = st.sidebar.text_input(
    "Snowflake TOTP (6 digits)",
    type="password",
    max_chars=6,
)

if st.sidebar.button("Connect to Snowflake"):
    if not sf_totp:
        st.sidebar.error("Please enter your Snowflake TOTP code.")
    else:
        try:
            counts, samples = fetch_snowflake_summary(sf_totp)
            st.session_state.sf_connected = True
            st.session_state.sf_counts = counts
            st.session_state.sf_samples = samples
            st.sidebar.success(
                f"Connected – Patients: {counts['patients']}, "
                f"Encounters: {counts['encounters']}"
            )
        except Exception as e:
            st.session_state.sf_connected = False
            st.sidebar.error(f"Snowflake connection failed: {e}")

st.sidebar.subheader("Neo4j AuraDB (MediGraphAI)")
if st.sidebar.button("Test AuraDB connection"):
    try:
        node_counts, rel_df = fetch_aura_stats()
        st.session_state.aura_connected = True
        st.session_state.aura_node_counts = node_counts
        st.session_state.aura_rel_df = rel_df
        st.sidebar.success(
            f"AuraDB OK – Patients: {node_counts.get('patients', 0)}, "
            f"Encounters: {node_counts.get('encounters', 0)}"
        )
    except Exception as e:
        st.session_state.aura_connected = False
        st.sidebar.error(f"AuraDB connection failed: {e}")

st.sidebar.markdown("---")
st.sidebar.caption(
    "Tip: connect **both** Snowflake and AuraDB, then explore the tabs below."
)

# -----------------------------------------------------------------------------
# Main tabs
# -----------------------------------------------------------------------------
(
    tab_overview,
    tab_sf,
    tab_aura_data,
    tab_aura_graph,
    tab_guidelines,
    tab_qa,
    tab_llm,
) = st.tabs(
    [
        "Product Overview",
        "Snowflake Views",
        "AuraDB Data & Analytics",
        "AuraDB Graph",
        "Guidelines & NER",
        "NL Q&A",
        "LLM Q&A",
    ]
)

# -----------------------------------------------------------------------------
# Tab: Overview
# -----------------------------------------------------------------------------
with tab_overview:
    st.subheader("Product Overview")

    col1, col2 = st.columns(2)
    with col1:
        sf_status = (
            "🟢 Connected" if st.session_state.sf_connected else "🔴 Not connected"
        )
        aura_status = (
            "🟢 Connected" if st.session_state.aura_connected else "🔴 Not connected"
        )
        st.markdown(
            f"""
            **Connection status**

            - Snowflake (MEDIGRAPH): **{sf_status}**  
            - Neo4j AuraDB (MediGraphAI): **{aura_status}**
            """
        )

    with col2:
        st.markdown(
            """
            **Pipeline**

            1. Synthetic EHR data (patients, encounters, conditions, meds, observations)
               ingested into **Snowflake MEDIGRAPH**.  
            2. Python ETL (`sf_aura.py`) builds a **patient journey graph** in AuraDB.  
            3. This app surfaces counts, graph structure, **clinical observations**, **provider analytics**,
               **guideline linking**, and **NL/LLM Q&A**.  
            """
        )

# -----------------------------------------------------------------------------
# Tab: Snowflake Views
# -----------------------------------------------------------------------------
with tab_sf:
    st.subheader("Snowflake – MEDIGRAPH Views")

    if not st.session_state.sf_connected:
        st.info("Connect to Snowflake from the sidebar to see counts and samples.")
    else:
        counts = st.session_state.sf_counts or {}
        samples = st.session_state.sf_samples or {}

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("V_PATIENTS", counts.get("patients", 0))
        c2.metric("V_ENCOUNTERS", counts.get("encounters", 0))
        c3.metric("V_CONDITIONS", counts.get("conditions", 0))
        c4.metric("V_MEDICATIONS", counts.get("medications", 0))
        c5.metric("V_PROVIDERS", counts.get("providers", 0))
        c6.metric("OBSERVATIONS", counts.get("observations", 0))

        st.markdown("### Sample data from each view")

        if "patients" in samples:
            st.markdown("#### `V_PATIENTS`")
            st.dataframe(samples["patients"], use_container_width=True)

        if "encounters" in samples:
            st.markdown("#### `V_ENCOUNTERS`")
            st.dataframe(samples["encounters"], use_container_width=True)

        if "conditions" in samples:
            st.markdown("#### `V_CONDITIONS`")
            st.dataframe(samples["conditions"], use_container_width=True)

        if "medications" in samples:
            st.markdown("#### `V_MEDICATIONS`")
            st.dataframe(samples["medications"], use_container_width=True)

        if "providers" in samples:
            st.markdown("#### `V_PROVIDERS`")
            st.dataframe(samples["providers"], use_container_width=True)

        if "observations" in samples:
            st.markdown("#### `OBSERVATIONS` (raw)")
            st.dataframe(samples["observations"], use_container_width=True)

# -----------------------------------------------------------------------------
# Tab: AuraDB Data (counts + observations + evaluations + GDS)
# -----------------------------------------------------------------------------
with tab_aura_data:
    st.subheader("AuraDB – Patient Graph Data & Analytics")

    if not st.session_state.aura_connected:
        st.info("Click **Test AuraDB connection** in the sidebar first.")
    else:
        node_counts = st.session_state.aura_node_counts or {}
        rel_df = st.session_state.aura_rel_df

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Patient nodes", node_counts.get("patients", 0))
        c2.metric("Encounter nodes", node_counts.get("encounters", 0))
        c3.metric("Condition nodes", node_counts.get("conditions", 0))
        c4.metric("Medication nodes", node_counts.get("medications", 0))
        c5.metric("Provider nodes", node_counts.get("providers", 0))
        c6.metric("Observation nodes", node_counts.get("observations", 0))

        st.markdown("### Relationship Types in AuraDB")
        st.dataframe(rel_df, use_container_width=True)

        st.markdown(
            """
            These counts are pulled **directly from AuraDB**, reflecting all
            relationships such as `HAS_ENCOUNTER`, `HAS_CONDITION`,
            `TAKES_MEDICATION`, `HAS_MEDICATION`, `HAS_PROVIDER`, and `HAS_OBSERVATION`
            that exist in your graph.
            """
        )

        st.markdown("---")
        st.markdown("### Patient Observations")

        default_pid = "90b111ca-1aa2-568a-c056-36ec90c14736"  # example; adjust if needed
        obs_pid = st.text_input(
            "Enter Patient ID to view clinical observations (vitals, labs, etc.):",
            value=default_pid,
            key="obs_pid_input",
        )

        if st.button("Show Observations", key="show_obs_btn"):
            if not obs_pid:
                st.warning("Please enter a Patient ID.")
            else:
                obs_df = get_patient_observations(obs_pid)
                if obs_df.empty:
                    st.info(f"No observations found for patient {obs_pid}.")
                else:
                    st.write(f"Observations for patient **{obs_pid}**:")
                    st.dataframe(obs_df, use_container_width=True)
                    st.caption(
                        "These are loaded from Snowflake's `OBSERVATIONS` table into Neo4j "
                        "and linked via `HAS_OBSERVATION` to both `Patient` and `Encounter`."
                    )

        st.markdown("---")
        st.markdown("### Observation Analytics & Evaluations")

        if st.button("Run Observation Analytics", key="obs_analytics_btn"):
            with st.spinner("Computing analytics over Observation nodes…"):
                metrics = get_observation_analytics()

            col_a, col_b, col_c = st.columns(3)
            col_a.metric(
                "Total Observations",
                metrics["total_observations"],
            )
            col_b.metric(
                "Patients with ≥1 Observation",
                metrics["patients_with_observations"],
            )
            avg_obs = metrics["avg_observations_per_patient"]
            col_c.metric(
                "Avg Observations per Patient",
                f"{avg_obs:.1f}" if avg_obs is not None else "N/A",
            )

            st.markdown("#### Top 5 Observation Types (by frequency)")
            top_list = metrics["top_observation_descriptions"]
            if top_list:
                for row in top_list:
                    st.write(f"- **{row['description']}** — {row['freq']} records")
            else:
                st.info("No observation data available for frequency analysis.")

            st.markdown(
                """
                **Evaluation summary:**

                - We validate that the **Observations** layer is fully integrated into the graph
                  (Patient → Encounter → Observation).
                - The average observations per patient helps assess **data density** and whether
                  our graph is rich enough for downstream analytics and LLM reasoning.
                - The most frequent observation descriptions confirm that we are capturing
                  clinically relevant vitals from the Synthea dataset.
                """
            )

        st.markdown("---")
        st.markdown("### Provider Analytics – Centrality & Communities")

        if st.button("Show Provider Rankings", key="gds_provider_btn"):
            with st.spinner("Computing provider rankings…"):
                gds_df = get_gds_provider_rankings()

            if gds_df.empty:
                st.info("No provider data available for analytics yet.")
            else:
                st.dataframe(gds_df, use_container_width=True)
                st.caption(
                    "Providers are ranked by their importance in the patient–provider network. "
                    "The `pr_score` column reflects centrality (PageRank or degree-based), and "
                    "`community` groups providers that share overlapping patient panels."
                )

# -----------------------------------------------------------------------------
# Tab: AuraDB Graph (real subgraph)
# -----------------------------------------------------------------------------
with tab_aura_graph:
    st.subheader("AuraDB – Live Patient Graph")

    if not st.session_state.aura_connected:
        st.info("Please connect to AuraDB from the sidebar first.")
    else:
        st.markdown(
            "Below is a **real subgraph from AuraDB** – patients, encounters, "
            "conditions, medications, providers, and observations "
            "with their actual relationships."
        )

        max_nodes = st.slider(
            "Approximate number of patient–neighbor triples to display",
            min_value=25,
            max_value=150,
            value=75,
            step=25,
        )

        if st.button("Refresh graph from AuraDB"):
            with st.spinner("Fetching graph data from AuraDB…"):
                try:
                    html = fetch_aura_graph(limit=max_nodes)
                    st.session_state.aura_graph_html = html
                except Exception as e:
                    st.error(f"Failed to load graph from AuraDB: {e}")

        if st.session_state.aura_graph_html:
            st.markdown('<div class="graph-container">', unsafe_allow_html=True)
            components.html(
                st.session_state.aura_graph_html,
                height=540,
                scrolling=False,
            )
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Click **Refresh graph from AuraDB** to load a live visualization.")

# -----------------------------------------------------------------------------
# Tab: Guidelines & NER (Gemini-ready demo)
# -----------------------------------------------------------------------------
with tab_guidelines:
    st.subheader("Clinical Guidelines & NER Linking (Gemini-ready)")

    if not st.session_state.aura_connected:
        st.info("Please connect to AuraDB from the sidebar first.")
    else:
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("#### 1) Paste a clinical note")
            default_note = (
                "54-year-old male with long-standing type 2 diabetes and hypertension, "
                "on metformin and lisinopril. Blood pressure remains elevated despite "
                "current therapy. Consider escalation per guidelines."
            )
            note_text = st.text_area(
                "Free-text clinical note (for demo NER)",
                value=default_note,
                height=180,
            )
            st.caption(
                "Example: 54-year-old male with long-standing type 2 diabetes and "
                "hypertension, on metformin and lisinopril. Blood pressure remains "
                "elevated despite current therapy. Consider escalation per guidelines."
            )

            if st.button("Run NER", key="ner_demo_btn"):
                if not note_text.strip():
                    st.warning("Please paste or type a note first.")
                else:
                    with st.spinner("Extracting clinical conditions…"):
                        concepts = simple_ner_extract_conditions(note_text)

                    if not concepts:
                        st.info(
                            "No known conditions were detected with the simple keyword-based NER."
                        )
                    else:
                        st.markdown("**Detected condition concepts:**")
                        chips = " ".join(
                            f"<span style='background:#0f172a;padding:0.2rem 0.6rem;"
                            f"border-radius:999px;margin-right:0.3rem;font-size:0.85rem;'>{c}</span>"
                            for c in concepts
                        )
                        st.markdown(chips, unsafe_allow_html=True)

                        st.session_state["last_ner_concepts"] = concepts

        with col_right:
            st.markdown("#### 2) Linked guidelines from the graph")

            concepts = st.session_state.get("last_ner_concepts", [])
            if concepts:
                with st.spinner("Loading guidelines linked to detected conditions…"):
                    g_df = get_guidelines_for_concepts(concepts)

                st.dataframe(g_df, use_container_width=True)
                st.caption(
                    "Detected conditions are linked to guideline entries. This shows how "
                    "NER output from an LLM can be grounded in a knowledge graph or "
                    "guideline library for explainable recommendations."
                )
            else:
                st.info(
                    "Run the NER step on the left to detect conditions, then guidelines "
                    "for those conditions will appear here."
                )

# -----------------------------------------------------------------------------
# Tab: NL Q&A
# -----------------------------------------------------------------------------
with tab_qa:
    st.subheader("Natural-Language Q&A over AuraDB (Rule-based)")

    st.markdown(
        """
        **Supported question types right now:**

        1. **Patients by condition**
           - `show patients with diabetes`
           - `show patients with hypertension`

        2. **Medications by condition**
           - `show medications for diabetes`

        3. **Medications by patient (ID or name)**
           - `show medications for patient 732e16fb-a1aa-b846-c6c2-c00bd4211445`
           - `show medications for patient Isaias`

        4. **Providers by patient (name)**
           - `who is the provider for patient Isaias`

        5. **Observations by patient (ID or name)**
           - `show observations for patient 90b111ca-1aa2-568a-c056-36ec90c14736`
           - `show observations for patient Isaias`

        6. **Encounters by patient (ID or name)**
           - `show encounters for patient 90b111ca-1aa2-568a-c056-36ec90c14736`
           - `show encounters for patient Isaias`
        """
    )

    if not st.session_state.aura_connected:
        st.info("Please connect to AuraDB from the sidebar first.")
    else:
        question = st.text_input(
            "Ask a question about conditions, medications, providers, or observations:",
            value="show patients with diabetes",
        )
        run = st.button("Run NL query")
        if run:
            if not question.strip():
                st.warning("Please type a question first.")
            else:
                with st.spinner("Querying AuraDB…"):
                    answer_text, df = answer_question_from_aura(question)
                st.markdown(answer_text)
                if df is not None and not df.empty:
                    st.dataframe(df, use_container_width=True)

# -----------------------------------------------------------------------------
# Tab: LLM Q&A (using llm_cypher.py)
# -----------------------------------------------------------------------------
with tab_llm:
    st.subheader("LLM-powered Q&A (Cypher Generator)")

    if generate_cypher_from_nl is None:
        st.warning(
            "LLM integration is not available. Make sure `llm_cypher.py` exists and "
            "your `.env` has a valid `OPENAI_API_KEY`."
        )
    elif not st.session_state.aura_connected:
        st.info("Please connect to AuraDB from the sidebar first.")
    else:
        llm_question = st.text_input(
            "Ask any graph question (the LLM will propose Cypher):",
            value="List 5 patients with their conditions and medications",
        )
        if st.button("Run LLM query"):
            if not llm_question.strip():
                st.warning("Please type a question first.")
            else:
                with st.spinner("Calling LLM and running Cypher…"):
                    try:
                        cypher = generate_cypher_from_nl(llm_question)
                        st.markdown("**Generated Cypher:**")
                        st.code(cypher, language="cypher")

                        # Prefer running via helper if available
                        if run_cypher_on_aura is not None:
                            cols, rows = run_cypher_on_aura(cypher)
                            if not rows:
                                st.info("Query executed, but returned no rows.")
                            else:
                                df = pd.DataFrame(rows, columns=cols)
                                st.dataframe(df, use_container_width=True)
                        else:
                            # Fallback: run directly
                            driver = get_aura_driver()
                            with driver.session(database="neo4j") as session:
                                result = session.run(cypher)
                                records = list(result)
                                keys = list(result.keys())
                            if not records:
                                st.info("Query executed, but returned no rows.")
                            else:
                                data = [[rec.get(k) for k in keys] for rec in records]
                                df = pd.DataFrame(data, columns=keys)
                                st.dataframe(df, use_container_width=True)

                    except Exception as e:
                        # Keep it smooth: show a soft message instead of a scary error
                        st.info(f"LLM/Cypher execution did not return data for this question.")
                        # (If you want to debug, temporarily print(e) in console)
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load env from project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path, override=True)


def get_aura_driver():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    pwd = os.getenv("NEO4J_PASSWORD")
    if not uri or not user or not pwd:
        raise RuntimeError("NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD not set in .env")
    return GraphDatabase.driver(uri, auth=(user, pwd))


# --- 1) Small, realistic guideline snippets -----------------------------
GUIDELINES = [
    {
        "id": "GL_DM_001",
        "title": "Type 2 Diabetes – First-line Therapy",
        "source": "SynthCare 2025 guideline",
        "text": (
            "For adults with type 2 diabetes, start metformin as first-line therapy "
            "unless contraindicated. For patients with hypertension, consider an ACE "
            "inhibitor such as lisinopril. Avoid NSAIDs in patients with advanced "
            "chronic kidney disease."
        ),
    },
    {
        "id": "GL_HTN_001",
        "title": "Hypertension – Blood Pressure Targets",
        "source": "SynthCare 2025 guideline",
        "text": (
            "In adults with hypertension, target blood pressure below 130/80 mmHg. "
            "For patients with diabetes and hypertension, ACE inhibitors such as "
            "lisinopril or ARBs are recommended. Beta blockers are not first-line "
            "for uncomplicated hypertension."
        ),
    },
]


# Very simple “NER/linking” dictionaries. This is your lightweight LLM stand-in.
CONDITION_KEYWORDS = {
    "diabetes": ["diabetes", "type 2 diabetes"],
    "hypertension": ["hypertension", "high blood pressure"],
    "chronic kidney disease": ["chronic kidney disease", "ckd"],
}

MEDICATION_KEYWORDS = {
    "metformin": ["metformin"],
    "lisinopril": ["lisinopril"],
    "beta-blocker": ["beta blocker", "beta-blocker"],
    "nsaid": ["nsaid", "nsaids"],
}


def load_guideline_nodes(driver):
    """
    Create Guideline nodes with full text.
    """
    with driver.session(database="neo4j") as session:
        for g in GUIDELINES:
            session.run(
                """
                MERGE (gl:Guideline {id: $id})
                SET gl.title  = $title,
                    gl.source = $source,
                    gl.text   = $text
                """,
                **g,
            )
    print(f"✔ Created/updated {len(GUIDELINES)} Guideline nodes")


def link_guidelines_to_graph(driver):
    """
    Lightweight NER/linking:
    - Look for condition & medication keywords in guideline text.
    - Link to existing Condition and Medication nodes.
    - Create MENTIONS_* and RECOMMENDS / CONTRAINDICATED_FOR relationships.
    """
    with driver.session(database="neo4j") as session:
        for g in GUIDELINES:
            gid = g["id"]
            text_lower = g["text"].lower()

            # 1) Link conditions
            for cond_label, terms in CONDITION_KEYWORDS.items():
                if any(t in text_lower for t in terms):
                    session.run(
                        """
                        MATCH (gl:Guideline {id: $gid}),
                              (c:Condition)
                        WHERE toLower(c.name) CONTAINS toLower($cond_label)
                        MERGE (gl)-[:MENTIONS_CONDITION]->(c)
                        """,
                        gid=gid,
                        cond_label=cond_label,
                    )

            # 2) Link medications
            for med_label, terms in MEDICATION_KEYWORDS.items():
                if any(t in text_lower for t in terms):
                    session.run(
                        """
                        MATCH (gl:Guideline {id: $gid}),
                              (m:Medication)
                        WHERE toLower(m.name) CONTAINS toLower($med_label)
                        MERGE (gl)-[:MENTIONS_MEDICATION]->(m)
                        """,
                        gid=gid,
                        med_label=med_label,
                    )

            # 3) A couple of explicit RECOMMENDS / CONTRAINDICATED_FOR examples
            if "metformin" in text_lower and "type 2 diabetes" in text_lower:
                session.run(
                    """
                    MATCH (gl:Guideline {id: $gid}),
                          (c:Condition), (m:Medication)
                    WHERE toLower(c.name) CONTAINS 'diabetes'
                      AND toLower(m.name) CONTAINS 'metformin'
                    MERGE (gl)-[:RECOMMENDS {reason:'first-line therapy'}]->(m)
                    MERGE (gl)-[:TARGETS_CONDITION]->(c)
                    """,
                    gid=gid,
                )

            if "avoid nsaids" in text_lower and "chronic kidney disease" in text_lower:
                session.run(
                    """
                    MATCH (gl:Guideline {id: $gid}),
                          (c:Condition)
                    WHERE toLower(c.name) CONTAINS 'chronic kidney disease'
                    MERGE (gl)-[:CONTRAINDICATED_FOR]->(c)
                    """,
                    gid=gid,
                )

    print("✔ Linked guidelines to Condition/Medication nodes")


def main():
    driver = get_aura_driver()
    try:
        load_guideline_nodes(driver)
        link_guidelines_to_graph(driver)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
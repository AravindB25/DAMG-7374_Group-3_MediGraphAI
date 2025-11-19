import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI

# Load environment variables
load_dotenv(".env", override=True)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -------------------------------------------------------------------
# Neo4j AuraDB helper
# -------------------------------------------------------------------
def get_aura_driver():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    pwd = os.getenv("NEO4J_PASSWORD")

    if not uri or not user or not pwd:
        raise RuntimeError("NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD not set in .env")

    return GraphDatabase.driver(uri, auth=(user, pwd))


# High-level schema hint for the LLM
SCHEMA_HINT = """
You are generating Cypher for Neo4j AuraDB with this schema:

Node labels and key properties:
- Patient(id, full_name, sex, age, zip)
- Encounter(id, start_time, end_time, provider_npi)
- Condition(code, name)
- Medication(code, name)
- Provider(id, name, specialty, state, zip)

Relationships:
- (p:Patient)-[:HAS_ENCOUNTER]->(e:Encounter)
- (p:Patient)-[:HAS_CONDITION]->(c:Condition)
- (p:Patient)-[:TAKES_MEDICATION]->(m:Medication)
- (e:Encounter)-[:HAS_CONDITION]->(c:Condition)
- (e:Encounter)-[:HAS_MEDICATION]->(m:Medication)
- (e:Encounter)-[:HAS_PROVIDER]->(pr:Provider)
- (p:Patient)-[:HAS_PROVIDER]->(pr:Provider)

Rules:
- Always use the properties shown above (id, full_name, code, name, etc.).
- Prefer LOWER CASE functions like toLower() in WHERE filters.
- Return tabular results (no graph-returning queries).
- DO NOT use APOC.
- DO NOT include comments, explanations, or markdown; ONLY return pure Cypher.
"""

# -------------------------------------------------------------------
# LLM → Cypher core function
# -------------------------------------------------------------------
def generate_cypher_from_nl(question: str, model: str | None = None) -> str:
    """
    Use OpenAI to translate a natural-language question into a Cypher query.

    Returns: a Cypher string (no backticks, no markdown).
    """
    if not question or not question.strip():
        raise ValueError("Question is empty")

    chosen_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    prompt = f"""
{SCHEMA_HINT}

User question:
\"\"\"{question.strip()}\"\"\"

You must respond with a SINGLE valid Cypher query only.
Do NOT wrap it in ``` or any other markdown.
"""

    resp = client.chat.completions.create(
        model=chosen_model,
        messages=[
            {"role": "system", "content": "You are an expert Neo4j Cypher generator."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    cypher = resp.choices[0].message.content.strip()

    # Strip ``` fences if the model adds them anyway
    if cypher.startswith("```"):
        cypher = cypher.strip().strip("`")
        # Remove possible "cypher" language tag at the start
        if cypher.lower().startswith("cypher"):
            cypher = cypher[6:].strip()

    return cypher

# -------------------------------------------------------------------
# Backward-compatible wrapper for app.py
# -------------------------------------------------------------------
def generate_cypher_with_llm(question: str, model: str | None = None) -> str:
    """
    Thin wrapper so app.py can call `generate_cypher_with_llm(...)`.

    This simply delegates to `generate_cypher_from_nl`.
    """
    return generate_cypher_from_nl(question, model=model)

# -------------------------------------------------------------------
# Run Cypher on AuraDB
# -------------------------------------------------------------------
def run_cypher_on_aura(cypher: str):
    """
    Execute a Cypher query on AuraDB and return (columns, rows).

    - columns: list of column names
    - rows: list of lists (each row is values in column order)
    """
    if not cypher or not cypher.strip():
        raise ValueError("Cypher query is empty")

    driver = get_aura_driver()
    try:
        with driver.session(database="neo4j") as session:
            result = session.run(cypher)
            records = list(result)
            keys = list(result.keys())

        if not records:
            return keys, []

        rows = []
        for rec in records:
            row = [rec.get(k) for k in keys]
            rows.append(row)

        return keys, rows

    finally:
        driver.close()


# -------------------------------------------------------------------
# Optional: quick CLI test
# -------------------------------------------------------------------
if __name__ == "__main__":
    q = input("Enter a graph question: ").strip()
    if not q:
        print("No question provided.")
        raise SystemExit

    print("\n=== Generating Cypher from LLM ===")
    cypher = generate_cypher_from_nl(q)
    print(cypher)

    print("\n=== Running on AuraDB ===")
    cols, rows = run_cypher_on_aura(cypher)
    print("Columns:", cols)
    print("Rows (first 5):")
    for r in rows[:5]:
        print(r)
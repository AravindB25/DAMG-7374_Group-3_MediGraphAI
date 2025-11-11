import os
from dotenv import load_dotenv

# ---- Load env ----
load_dotenv(".env", override=True)

# -----------------------
# Snowflake connectivity
# -----------------------
def check_snowflake():
    import snowflake.connector as sf
    print("\n=== Snowflake check ===")
    totp = input("Enter Snowflake TOTP (6 digits): ").strip()
    conn = sf.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASsWORD") or os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        host=os.getenv("SNOWFLAKE_HOST"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        authenticator="snowflake",
        passcode=totp,
        role=os.getenv("SNOWFLAKE_ROLE") if os.getenv("SNOWFLAKE_ROLE") else None,
    )
    cur = conn.cursor()
    cur.execute("SELECT current_account(), current_region(), current_warehouse(), current_database(), current_schema()")
    print("✅ Snowflake OK:", cur.fetchone())
    # Optional quick row counts if your views exist
    try:
        for name, sql in [
            ("V_PATIENTS",     "SELECT COUNT(*) FROM V_PATIENTS"),
            ("V_ENCOUNTERS",   "SELECT COUNT(*) FROM V_ENCOUNTERS"),
            ("V_CONDITIONS",   "SELECT COUNT(*) FROM V_CONDITIONS"),
            ("V_MEDICATIONS",  "SELECT COUNT(*) FROM V_MEDICATIONS"),
        ]:
            cur.execute(sql)
            print(f"   {name} rows:", cur.fetchone()[0])
    except Exception as e:
        print("   (View counts skipped):", e)
    cur.close()
    conn.close()

# -----------------------
# Neo4j connectivity
# -----------------------
def check_neo4j():
    print("\n=== Neo4j check ===")
    from neo4j import GraphDatabase
    uri  = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    pwd  = os.getenv("NEO4J_PASSWORD")
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session() as s:
        msg = s.run("RETURN 'Connected to Neo4j ✅' AS msg").single()["msg"]
        print(msg)

        # Ensure basic indexes/constraints exist (idempotent)
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Patient)  REQUIRE p.patient_id IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (pr:Provider) REQUIRE pr.npi IS UNIQUE")
        s.run("CREATE INDEX IF NOT EXISTS FOR (e:Encounter) ON (e.enc_id)")
        s.run("CREATE INDEX IF NOT EXISTS FOR (c:Condition) ON (c.name)")
        s.run("CREATE INDEX IF NOT EXISTS FOR (m:Medication) ON (m.name)")

        # Tiny demo graph (safe to MERGE repeatedly)
        s.run("""
        MERGE (p:Patient {patient_id:'DEMO-P1'})
        MERGE (e:Encounter {enc_id:'DEMO-E1'})
        MERGE (c:Condition {name:'Hypertension'})
        MERGE (m:Medication {name:'Lisinopril'})
        MERGE (p)-[:HAS_ENCOUNTER]->(e)
        MERGE (e)-[:DIAGNOSED]->(c)
        MERGE (e)-[:PRESCRIBED]->(m)
        """)

        # Sanity queries
        count_nodes = s.run("MATCH (n) RETURN count(n) AS n").single()["n"]
        print("Nodes in DB:", count_nodes)
        path = s.run("""
            MATCH (p:Patient)-[:HAS_ENCOUNTER]->(e)-[:DIAGNOSED]->(c:Condition)
            RETURN p.patient_id AS patient, c.name AS condition
            LIMIT 1
        """).single()
        if path:
            print("Sample path:", dict(path))
        else:
            print("No Patient→Encounter→Condition path found yet.")
    driver.close()

if __name__ == "__main__":
    try:
        check_snowflake()
    except Exception as e:
        print("❌ Snowflake error:", e)
    try:
        check_neo4j()
    except Exception as e:
        print("❌ Neo4j error:", e)

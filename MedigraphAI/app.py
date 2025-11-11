import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import snowflake.connector as sf
from neo4j import GraphDatabase
from pyvis.network import Network
import tempfile

# ------------------ Load .env ------------------
load_dotenv(".env", override=True)

# ------------------ Streamlit UI ------------------
st.set_page_config(page_title="🧠 MediGraph AI", layout="wide")
st.title("MediGraph AI – Intelligent Healthcare Knowledge Graph")

st.sidebar.header("🔐 Authentication")
totp_code = st.sidebar.text_input("Enter Snowflake MFA (6 digits):", type="password")
connect_btn = st.sidebar.button("Connect")

sf_conn = None
neo4j_driver = None

# ------------------ Connection Section ------------------
if connect_btn:
    try:
        # ---- Snowflake ----
        st.subheader("✅ Snowflake Connection")
        sf_conn = sf.connect(
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
            database=os.getenv("SNOWFLAKE_DATABASE"),
            schema=os.getenv("SNOWFLAKE_SCHEMA"),
            passcode=totp_code.strip(),  # MFA
        )
        cur = sf_conn.cursor()
        cur.execute("SELECT current_account(), current_region(), current_database(), current_schema()")
        st.success(f"Connected to Snowflake: {cur.fetchone()}")
        cur.close()

        # ---- Neo4j ----
        st.subheader("🧩 Neo4j Graph Connection")
        neo4j_driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
        )

        with neo4j_driver.session(database="neo4j") as s:
            count = s.run("MATCH (n) RETURN COUNT(n) AS c").single()["c"]
            if count == 0:
                st.warning("Neo4j is empty — seeding demo data...")
                s.run("""
                CREATE (p1:Patient {id:'P001', name:'John Doe', age:45}),
                       (p2:Patient {id:'P002', name:'Alice Smith', age:52}),
                       (c1:Condition {name:'Diabetes'}),
                       (c2:Condition {name:'Hypertension'}),
                       (p1)-[:HAS_CONDITION]->(c1),
                       (p2)-[:HAS_CONDITION]->(c2)
                """)
                st.info("✅ Demo data added to Neo4j successfully.")
                count = 4
        st.success(f"Connected to Neo4j ✅ (Nodes: {count})")

    except Exception as e:
        st.error(f"❌ Connection failed: {e}")

else:
    st.info("👈 Enter MFA code and click Connect to start.")

# ------------------ Tabs: Q&A + Visualization ------------------
if sf_conn and neo4j_driver:
    st.markdown("---")
    tab1, tab2 = st.tabs(["💬 Ask a Question", "🕸️ Visualize Graph"])

    # ---------------- Tab 1: Q&A ----------------
    with tab1:
        st.header("💬 Ask a Question")

        question = st.text_input("Try: 'Show patients with Diabetes' or 'List patient demographics'")
        ask_btn = st.button("Ask")

        if ask_btn and question:
            q = question.lower().strip()
            st.markdown(f"🧠 Interpreting your question: _{q}_")

            try:
                # --- Neo4j Condition Data ---
                if "condition" in q or "disease" in q or "diabetes" in q or "hypertension" in q:
                    with neo4j_driver.session(database="neo4j") as s:
                        cypher = """
                        MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition)
                        RETURN p.id AS patient_id, p.name AS patient_name, c.name AS condition
                        """
                        df = pd.DataFrame(s.run(cypher).data())
                        if not df.empty:
                            st.success("✅ Condition Data (from Neo4j):")
                            st.dataframe(df)
                        else:
                            st.warning("No condition data found in Neo4j.")

                # --- Snowflake Encounter Data ---
                elif "encounter" in q or "visit" in q or "appointment" in q:
                    sql = "SELECT * FROM V_ENCOUNTERS LIMIT 10"
                    df = pd.read_sql(sql, sf_conn)
                    st.success("✅ Encounter Data (from Snowflake):")
                    st.dataframe(df)

                # --- Snowflake Patient Data ---
                elif "patient" in q or "age" in q or "gender" in q or "zip" in q:
                    sql = "SELECT * FROM V_PATIENTS LIMIT 10"
                    df = pd.read_sql(sql, sf_conn)
                    st.success("✅ Patient Data (from Snowflake):")
                    st.dataframe(df)

                # --- Snowflake Medication Data ---
                elif "medication" in q or "drug" in q:
                    sql = "SELECT * FROM V_MEDICATIONS LIMIT 10"
                    df = pd.read_sql(sql, sf_conn)
                    st.success("✅ Medication Data (from Snowflake):")
                    st.dataframe(df)

                else:
                    st.warning("Question not recognized — include 'patient', 'condition', 'encounter', or 'medication'.")

            except Exception as e:
                st.error(f"❌ Query failed: {e}")

    # ---------------- Tab 2: Visualization ----------------
    with tab2:
        st.header("🕸️ Patient–Condition Network")

        try:
            with neo4j_driver.session(database="neo4j") as s:
                results = s.run("""
                MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition)
                RETURN p.id AS pid, p.name AS pname, c.name AS cname
                """).data()

            if results:
                net = Network(height="550px", width="100%", bgcolor="#F9F9F9", directed=True)
                for row in results:
                    pid, pname, cname = row["pid"], row["pname"], row["cname"]
                    net.add_node(pid, label=pname, color="#4B9CD3", shape="dot", size=20)
                    net.add_node(cname, label=cname, color="#FF7F50", shape="ellipse", size=15)
                    net.add_edge(pid, cname, title="HAS_CONDITION")

                with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
                    net.save_graph(tmp.name)
                    html = open(tmp.name, "r", encoding="utf-8").read()
                    st.components.v1.html(html, height=600, scrolling=True)
            else:
                st.warning("No graph data available to visualize.")

        except Exception as e:
            st.error(f"❌ Visualization error: {e}")

# ------------------ Cleanup ------------------
if sf_conn:
    sf_conn.close()
if neo4j_driver:
    neo4j_driver.close()

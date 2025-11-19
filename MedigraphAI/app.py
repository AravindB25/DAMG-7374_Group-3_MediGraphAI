# import os
# from dotenv import load_dotenv
# import snowflake.connector
# from neo4j import GraphDatabase
# import pandas as pd
# import streamlit as st
# import streamlit.components.v1 as components
# from pyvis.network import Network

# # -----------------------------------------------------------------------------
# # Load environment variables
# # -----------------------------------------------------------------------------
# load_dotenv(".env", override=True)

# # -----------------------------------------------------------------------------
# # Global styling – dark blue theme, high contrast
# # -----------------------------------------------------------------------------
# st.set_page_config(
#     page_title="MediGraph AI – Snowflake + AuraDB Demo",
#     layout="wide",
# )

# st.markdown(
#     """
#     <style>
#     /* Full app background + text */
#     .stApp {
#         background-color: #020617; /* very dark blue */
#         color: #e5e7eb;           /* light grey text */
#     }
#     .block-container {
#         padding-top: 1rem;
#         padding-bottom: 3rem;
#     }
#     /* Sidebar */
#     [data-testid="stSidebar"] {
#         background-color: #020617;
#         color: #e5e7eb;
#     }
#     [data-testid="stSidebar"] * {
#         color: #e5e7eb !important;
#     }
#     /* Buttons */
#     .stButton>button {
#         background: linear-gradient(to right, #0ea5e9, #38bdf8);
#         color: #0b1120;
#         border-radius: 999px;
#         border: none;
#         padding: 0.4rem 1.2rem;
#         font-weight: 600;
#     }
#     .stButton>button:hover {
#         filter: brightness(1.1);
#     }
#     /* Tabs */
#     .stTabs [role="tab"] {
#         background-color: #0f172a;
#         color: #e5e7eb;
#         padding: 0.5rem 1rem;
#         border-radius: 999px 999px 0 0;
#     }
#     .stTabs [role="tab"][aria-selected="true"] {
#         border-bottom: 3px solid #38bdf8;
#         font-weight: 700;
#     }
#     /* Metrics + headers */
#     .stMetric, .stMetric label, .stMetric span {
#         color: #e5e7eb !important;
#     }
#     h1, h2, h3, h4, h5, h6 {
#         color: #f9fafb;
#     }
#     /* Dataframes */
#     .stDataFrame {
#         background-color: #020617;
#     }
#     /* PyVis container */
#     .graph-container {
#         border-radius: 1rem;
#         overflow: hidden;
#         border: 1px solid #1e293b;
#     }
#     </style>
#     """,
#     unsafe_allow_html=True,
# )

# # -----------------------------------------------------------------------------
# # Helper functions – Snowflake
# # -----------------------------------------------------------------------------
# def get_snowflake_connection(totp_code: str):
#     """
#     Create a Snowflake connection using username + password + TOTP (MFA).
#     """
#     return snowflake.connector.connect(
#         user=os.getenv("SNOWFLAKE_USER"),
#         password=os.getenv("SNOWFLAKE_PASSWORD"),
#         account=os.getenv("SNOWFLAKE_ACCOUNT"),
#         warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
#         database=os.getenv("SNOWFLAKE_DATABASE"),
#         schema=os.getenv("SNOWFLAKE_SCHEMA"),
#         role=os.getenv("SNOWFLAKE_ROLE"),
#         passcode=totp_code.strip() if totp_code else None,
#     )


# def fetch_snowflake_summary(totp_code: str):
#     """
#     Returns:
#       counts: dict with counts for each view
#       patients_sample: pandas DataFrame with sample patients
#     """
#     conn = None
#     try:
#         conn = get_snowflake_connection(totp_code)
#         cur = conn.cursor()

#         counts = {}
#         for view_name, key in [
#             ("V_PATIENTS", "patients"),
#             ("V_ENCOUNTERS", "encounters"),
#             ("V_CONDITIONS", "conditions"),
#             ("V_MEDICATIONS", "medications"),
#         ]:
#             cur.execute(f"SELECT COUNT(*) FROM {view_name}")
#             counts[key] = cur.fetchone()[0]

#         cur.execute(
#             """
#             SELECT PATIENT_ID, FIRST_NAME, LAST_NAME, SEX, ZIP, AGE
#             FROM V_PATIENTS
#             LIMIT 20
#             """
#         )
#         rows = cur.fetchall()
#         cols = [c[0] for c in cur.description]
#         patients_sample = pd.DataFrame(rows, columns=cols)

#         cur.close()
#         return counts, patients_sample

#     finally:
#         if conn is not None:
#             conn.close()

# # -----------------------------------------------------------------------------
# # Helper functions – AuraDB (Neo4j)
# # -----------------------------------------------------------------------------
# def get_aura_driver():
#     uri = os.getenv("NEO4J_URI")
#     user = os.getenv("NEO4J_USER")
#     pwd = os.getenv("NEO4J_PASSWORD")
#     if not uri or not user or not pwd:
#         raise RuntimeError("NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD not set in .env")
#     return GraphDatabase.driver(uri, auth=(user, pwd))


# def fetch_aura_stats():
#     driver = get_aura_driver()
#     try:
#         with driver.session(database="neo4j") as session:
#             node_counts = {}
#             for label, key in [
#                 ("Patient", "patients"),
#                 ("Encounter", "encounters"),
#                 ("Condition", "conditions"),
#                 ("Medication", "medications"),
#             ]:
#                 result = session.run(
#                     f"MATCH (n:{label}) RETURN COUNT(n) AS c"
#                 ).single()
#                 node_counts[key] = result["c"]

#             rel_result = session.run(
#                 """
#                 MATCH ()-[r]->()
#                 RETURN type(r) AS relationship_type, COUNT(r) AS total
#                 ORDER BY total DESC
#                 """
#             )
#             rows = list(rel_result)
#             rel_df = pd.DataFrame(
#                 [(row["relationship_type"], row["total"]) for row in rows],
#                 columns=["relationship_type", "total"],
#             )

#         return node_counts, rel_df
#     finally:
#         driver.close()


# def fetch_aura_graph(limit: int = 75) -> str:
#     """
#     Fetch a real subgraph from AuraDB (no fake graph):
#     Patients + all their encounters, conditions, medications, providers.

#     Returns: HTML string with an interactive PyVis network.
#     """
#     driver = get_aura_driver()
#     try:
#         with driver.session(database="neo4j") as session:
#             cypher = """
#             MATCH (p:Patient)-[r]-(n)
#             RETURN p, r, n
#             LIMIT $limit
#             """
#             result = session.run(cypher, limit=limit)
#             rows = list(result)

#         net = Network(
#             height="520px",
#             width="100%",
#             bgcolor="#020617",
#             font_color="#e5e7eb",
#             notebook=False,
#             directed=True,
#         )

#         node_seen = set()
#         rel_seen = set()

#         def add_node(node, group: str):
#             nid = str(node.id)  # internal Neo4j id
#             if nid in node_seen:
#                 return
#             node_seen.add(nid)

#             label = node.get("full_name") or node.get("name") or node.get("id") or group
#             title_parts = [f"<b>{group}</b>"]
#             for k, v in node.items():
#                 title_parts.append(f"{k}: {v}")
#             title = "<br>".join(title_parts)

#             color_map = {
#                 "Patient": "#22d3ee",
#                 "Encounter": "#4ade80",
#                 "Condition": "#f97316",
#                 "Medication": "#a855f7",
#                 "Provider": "#facc15",
#             }
#             net.add_node(
#                 nid,
#                 label=str(label),
#                 title=title,
#                 color=color_map.get(group, "#38bdf8"),
#             )

#         for row in rows:
#             p = row["p"]
#             n = row["n"]
#             r = row["r"]

#             add_node(p, "Patient")

#             labels = list(n.labels)
#             if "Encounter" in labels:
#                 group = "Encounter"
#             elif "Condition" in labels:
#                 group = "Condition"
#             elif "Medication" in labels:
#                 group = "Medication"
#             elif "Provider" in labels:
#                 group = "Provider"
#             else:
#                 group = labels[0] if labels else "Node"
#             add_node(n, group)

#             src = str(p.id)
#             tgt = str(n.id)
#             rel_type = r.type
#             edge_key = (src, tgt, rel_type)
#             if edge_key not in rel_seen:
#                 rel_seen.add(edge_key)
#                 net.add_edge(src, tgt, label=rel_type)

#         net.toggle_physics(True)

#         # IMPORTANT: valid JSON (no "const", valid quotes)
#         net.set_options(
#             """
#             {
#               "physics": {
#                 "stabilization": true,
#                 "barnesHut": {
#                   "gravitationalConstant": -8000,
#                   "centralGravity": 0.3,
#                   "springLength": 95
#                 }
#               },
#               "nodes": {
#                 "font": {
#                   "size": 14,
#                   "color": "#e5e7eb"
#                 }
#               },
#               "edges": {
#                 "color": "#64748b",
#                 "smooth": false
#               }
#             }
#             """
#         )

#         return net.generate_html(notebook=False)

#     finally:
#         driver.close()



# def answer_question_from_aura(question: str):
#     """
#     Simple NL → Cypher router.

#     Supports:
#       1) "show patients with diabetes"
#       2) "show medications for diabetes"
#       3) "show medications for patient P001"
#     """
#     q_raw = question.strip()
#     q = q_raw.lower()

#     driver = get_aura_driver()
#     try:
#         with driver.session(database="neo4j") as session:
#             # 3) Medications for a given patient ID
#             if "medications for patient" in q:
#                 pid = q.split("medications for patient", 1)[1].strip().upper()
#                 cypher = """
#                     MATCH (p:Patient {id: $pid})-[:TAKES_MEDICATION]->(m:Medication)
#                     RETURN p.id AS patient_id,
#                            p.full_name AS full_name,
#                            m.code AS rxnorm,
#                            m.name AS medication
#                     LIMIT 50
#                 """
#                 result = session.run(cypher, pid=pid)
#                 rows = list(result)
#                 if not rows:
#                     return (
#                         f"I couldn't find medications for patient **{pid}**.",
#                         None,
#                     )
#                 df = pd.DataFrame(
#                     [
#                         (row["patient_id"], row["full_name"], row["rxnorm"], row["medication"])
#                         for row in rows
#                     ],
#                     columns=["patient_id", "full_name", "rxnorm", "medication"],
#                 )
#                 return f"Medications for patient **{pid}**:", df

#             # 2) Medications for a condition
#             if "medications for" in q or "medication for" in q:
#                 phrase = (
#                     q.replace("show", "")
#                     .replace("list", "")
#                     .replace("medications for", "")
#                     .replace("medication for", "")
#                     .strip()
#                 )
#                 if not phrase:
#                     phrase = "diabetes"

#                 cypher = """
#                     MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition),
#                           (p)-[:TAKES_MEDICATION]->(m:Medication)
#                     WHERE toLower(c.name) CONTAINS toLower($term)
#                     RETURN DISTINCT m.code AS rxnorm,
#                                     m.name AS medication,
#                                     COUNT(DISTINCT p) AS patients_on_med
#                     ORDER BY patients_on_med DESC
#                     LIMIT 50
#                 """
#                 result = session.run(cypher, term=phrase)
#                 rows = list(result)
#                 if not rows:
#                     return (
#                         f"I couldn't find medications for conditions matching **'{phrase}'**.",
#                         None,
#                     )
#                 df = pd.DataFrame(
#                     [
#                         (row["rxnorm"], row["medication"], row["patients_on_med"])
#                         for row in rows
#                     ],
#                     columns=["rxnorm", "medication", "patients_on_med"],
#                 )
#                 return (
#                     f"Medications used by patients with conditions matching **'{phrase}'**:",
#                     df,
#                 )

#             # 1) Patients with a condition
#             if "patients with" in q or q.startswith("show patients") or q.startswith("list patients"):
#                 phrase = (
#                     q.replace("show", "")
#                     .replace("list", "")
#                     .replace("patients with", "")
#                     .replace("patients", "")
#                     .replace("who have", "")
#                     .strip()
#                 )
#                 if not phrase:
#                     phrase = "diabetes"

#                 cypher = """
#                     MATCH (p:Patient)-[:HAS_CONDITION]->(c:Condition)
#                     WHERE toLower(c.name) CONTAINS toLower($term)
#                     RETURN p.id AS patient_id,
#                            p.full_name AS full_name,
#                            p.sex AS sex,
#                            p.age AS age,
#                            c.name AS condition
#                     LIMIT 50
#                 """
#                 result = session.run(cypher, term=phrase)
#                 rows = list(result)
#                 if not rows:
#                     return (
#                         f"I couldn't find patients with conditions matching **'{phrase}'**.",
#                         None,
#                     )
#                 df = pd.DataFrame(
#                     [
#                         (
#                             row["patient_id"],
#                             row["full_name"],
#                             row["sex"],
#                             row["age"],
#                             row["condition"],
#                         )
#                         for row in rows
#                     ],
#                     columns=["patient_id", "full_name", "sex", "age", "condition"],
#                 )
#                 return f"Patients with conditions matching **'{phrase}'**:", df

#             # Fallback
#             help_text = (
#                 "Right now I support questions like:\n"
#                 "- `show patients with diabetes`\n"
#                 "- `show patients with hypertension`\n"
#                 "- `show medications for diabetes`\n"
#                 "- `show medications for patient P001`"
#             )
#             return help_text, None

#     finally:
#         driver.close()

# # -----------------------------------------------------------------------------
# # Session state init
# # -----------------------------------------------------------------------------
# for key in [
#     "sf_connected",
#     "sf_counts",
#     "sf_patients_sample",
#     "aura_connected",
#     "aura_node_counts",
#     "aura_rel_df",
#     "aura_graph_html",
# ]:
#     if key not in st.session_state:
#         st.session_state[key] = None

# # -----------------------------------------------------------------------------
# # Layout – Header
# # -----------------------------------------------------------------------------
# st.markdown(
#     """
#     <div style="padding: 1.5rem 0 0.5rem 0;">
#       <h1 style="margin-bottom: 0.2rem;">MediGraph AI</h1>
#       <p style="color:#9ca3af; font-size:0.95rem; max-width:720px;">
#         Healthcare intelligence powered by <b>Snowflake MEDIGRAPH</b> and <b>Neo4j AuraDB</b>.
#         This demo shows how synthetic EHR records become a patient journey knowledge graph with
#         live queries and natural-language Q&A.
#       </p>
#       <div style="margin-top:0.6rem;">
#         <span style="background:#0f172a; color:#e5e7eb; padding:0.25rem 0.7rem; border-radius:999px; margin-right:0.4rem; font-size:0.8rem;">
#           Snowflake Lakehouse
#         </span>
#         <span style="background:#0f172a; color:#e5e7eb; padding:0.25rem 0.7rem; border-radius:999px; font-size:0.8rem;">
#           Neo4j AuraDB Patient Graph
#         </span>
#       </div>
#     </div>
#     """,
#     unsafe_allow_html=True,
# )

# # -----------------------------------------------------------------------------
# # Sidebar – connections
# # -----------------------------------------------------------------------------
# st.sidebar.header("🔌 Live Connections")

# st.sidebar.subheader("Snowflake (MEDIGRAPH)")
# sf_totp = st.sidebar.text_input(
#     "Snowflake TOTP (6 digits)",
#     type="password",
#     max_chars=6,
# )

# if st.sidebar.button("Connect to Snowflake"):
#     if not sf_totp:
#         st.sidebar.error("Please enter your Snowflake TOTP code.")
#     else:
#         try:
#             counts, sample = fetch_snowflake_summary(sf_totp)
#             st.session_state.sf_connected = True
#             st.session_state.sf_counts = counts
#             st.session_state.sf_patients_sample = sample
#             st.sidebar.success(
#                 f"Connected – Patients: {counts['patients']}, "
#                 f"Encounters: {counts['encounters']}"
#             )
#         except Exception as e:
#             st.session_state.sf_connected = False
#             st.sidebar.error(f"Snowflake connection failed: {e}")

# st.sidebar.subheader("Neo4j AuraDB (MediGraphAI)")
# if st.sidebar.button("Test AuraDB connection"):
#     try:
#         node_counts, rel_df = fetch_aura_stats()
#         st.session_state.aura_connected = True
#         st.session_state.aura_node_counts = node_counts
#         st.session_state.aura_rel_df = rel_df
#         st.sidebar.success(
#             f"AuraDB OK – Patients: {node_counts.get('patients', 0)}, "
#             f"Encounters: {node_counts.get('encounters', 0)}"
#         )
#     except Exception as e:
#         st.session_state.aura_connected = False
#         st.sidebar.error(f"AuraDB connection failed: {e}")

# st.sidebar.markdown("---")
# st.sidebar.caption(
#     "Tip: connect **both** Snowflake and AuraDB, then explore the tabs below."
# )

# # -----------------------------------------------------------------------------
# # Main tabs
# # -----------------------------------------------------------------------------
# tab_overview, tab_sf, tab_aura_data, tab_aura_graph, tab_qa = st.tabs(
#     [
#         "Product Overview",
#         "Snowflake Views",
#         "AuraDB Data",
#         "AuraDB Graph",
#         "NL Q&A",
#     ]
# )

# # -----------------------------------------------------------------------------
# # Tab: Overview
# # -----------------------------------------------------------------------------
# with tab_overview:
#     st.subheader("Product Overview")

#     col1, col2 = st.columns(2)
#     with col1:
#         sf_status = (
#             "🟢 Connected" if st.session_state.sf_connected else "🔴 Not connected"
#         )
#         aura_status = (
#             "🟢 Connected" if st.session_state.aura_connected else "🔴 Not connected"
#         )
#         st.markdown(
#             f"""
#             **Connection status**

#             - Snowflake (MEDIGRAPH): **{sf_status}**  
#             - Neo4j AuraDB (MediGraphAI): **{aura_status}**
#             """
#         )

#     with col2:
#         st.markdown(
#             """
#             **Pipeline**

#             1. Synthetic EHR data ingested into **Snowflake MEDIGRAPH**.  
#             2. Python ETL (`sf_to_aura.py`) builds a **patient journey graph** in AuraDB.  
#             3. This app surfaces counts, graph structure, and **NL Q&A** for conditions & medications.  
#             """
#         )

# # -----------------------------------------------------------------------------
# # Tab: Snowflake Views
# # -----------------------------------------------------------------------------
# with tab_sf:
#     st.subheader("Snowflake – MEDIGRAPH Views")

#     if not st.session_state.sf_connected:
#         st.info("Connect to Snowflake from the sidebar to see counts and samples.")
#     else:
#         counts = st.session_state.sf_counts or {}
#         sample = st.session_state.sf_patients_sample

#         c1, c2, c3, c4 = st.columns(4)
#         c1.metric("V_PATIENTS", counts.get("patients", 0))
#         c2.metric("V_ENCOUNTERS", counts.get("encounters", 0))
#         c3.metric("V_CONDITIONS", counts.get("conditions", 0))
#         c4.metric("V_MEDICATIONS", counts.get("medications", 0))

#         st.markdown("### Sample patients from `V_PATIENTS`")
#         st.dataframe(sample, use_container_width=True)

# # -----------------------------------------------------------------------------
# # Tab: AuraDB Data (counts)
# # -----------------------------------------------------------------------------
# with tab_aura_data:
#     st.subheader("AuraDB – Patient Graph Data")

#     if not st.session_state.aura_connected:
#         st.info("Click **Test AuraDB connection** in the sidebar first.")
#     else:
#         node_counts = st.session_state.aura_node_counts or {}
#         rel_df = st.session_state.aura_rel_df

#         c1, c2, c3, c4 = st.columns(4)
#         c1.metric("Patient nodes", node_counts.get("patients", 0))
#         c2.metric("Encounter nodes", node_counts.get("encounters", 0))
#         c3.metric("Condition nodes", node_counts.get("conditions", 0))
#         c4.metric("Medication nodes", node_counts.get("medications", 0))

#         st.markdown("### Relationship Types in AuraDB")
#         st.dataframe(rel_df, use_container_width=True)

#         st.markdown(
#             """
#             These counts are pulled **directly from AuraDB**, reflecting all
#             relationships such as `HAS_ENCOUNTER`, `HAS_CONDITION`,
#             `TAKES_MEDICATION`, `HAS_MEDICATION`, `DIAGNOSED`, and `PRESCRIBED`
#             that exist in your graph.
#             """
#         )

# # -----------------------------------------------------------------------------
# # Tab: AuraDB Graph (real subgraph)
# # -----------------------------------------------------------------------------
# with tab_aura_graph:
#     st.subheader("AuraDB – Live Patient Graph")

#     if not st.session_state.aura_connected:
#         st.info("Please connect to AuraDB from the sidebar first.")
#     else:
#         st.markdown(
#             "Below is a **real subgraph from AuraDB** – patients, encounters, "
#             "conditions, medications, and providers with their actual relationships."
#         )

#         max_nodes = st.slider(
#             "Approximate number of patient–neighbor triples to display",
#             min_value=25,
#             max_value=150,
#             value=75,
#             step=25,
#         )

#         if st.button("Refresh graph from AuraDB"):
#             with st.spinner("Fetching graph data from AuraDB…"):
#                 try:
#                     html = fetch_aura_graph(limit=max_nodes)
#                     st.session_state.aura_graph_html = html
#                 except Exception as e:
#                     st.error(f"Failed to load graph from AuraDB: {e}")

#         if st.session_state.aura_graph_html:
#             st.markdown('<div class="graph-container">', unsafe_allow_html=True)
#             components.html(
#                 st.session_state.aura_graph_html,
#                 height=540,
#                 scrolling=False,
#             )
#             st.markdown('</div>', unsafe_allow_html=True)
#         else:
#             st.info("Click **Refresh graph from AuraDB** to load a live visualization.")

# # -----------------------------------------------------------------------------
# # Tab: NL Q&A
# # -----------------------------------------------------------------------------
# with tab_qa:
#     st.subheader("Natural-Language Q&A over AuraDB")

#     st.markdown(
#         """
#         **Supported question types right now:**

#         1. Patients by condition  
#            - `show patients with diabetes`  
#            - `show patients with hypertension`  

#         2. Medications by condition  
#            - `show medications for diabetes`  

#         3. Medications by patient  
#            - `show medications for patient P001`  
#         """
#     )

#     if not st.session_state.aura_connected:
#         st.info("Please connect to AuraDB from the sidebar first.")
#     else:
#         question = st.text_input(
#             "Ask a question about conditions or medications:",
#             value="show patients with diabetes",
#         )
#         run = st.button("Run NL query")
#         if run:
#             if not question.strip():
#                 st.warning("Please type a question first.")
#             else:
#                 with st.spinner("Querying AuraDB…"):
#                     answer_text, df = answer_question_from_aura(question)
#                 st.markdown(answer_text)
#                 if df is not None and not df.empty:
#                     st.dataframe(df, use_container_width=True)


import os
from dotenv import load_dotenv
import snowflake.connector
from neo4j import GraphDatabase
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

# -----------------------------------------------------------------------------
# Load environment variables
# -----------------------------------------------------------------------------
load_dotenv(".env", override=True)

# -----------------------------------------------------------------------------
# Global styling – full dark blue theme, large metrics, polished layout
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="MediGraph AI – Snowflake + AuraDB Demo",
    layout="wide",
)

st.markdown(
    """
    <style>
    /* Full app background + text */
    .stApp {
        background-color: #020617; /* very dark blue */
        color: #e5e7eb;           /* light grey text */
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #020617;
        color: #e5e7eb;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] * {
        color: #e5e7eb !important;
        font-size: 0.9rem;
    }

    /* Sidebar header "pill" */
    .sidebar-pill {
        background: #0f172a;
        border-radius: 999px;
        padding: 0.35rem 0.7rem;
        display: inline-block;
        font-size: 0.8rem;
        color: #e5e7eb;
        margin-bottom: 0.5rem;
    }

    /* Buttons */
    .stButton>button {
        background: linear-gradient(to right, #0ea5e9, #38bdf8);
        color: #0b1120;
        border-radius: 999px;
        border: none;
        padding: 0.4rem 1.2rem;
        font-weight: 600;
        font-size: 0.9rem;
    }
    .stButton>button:hover {
        filter: brightness(1.1);
    }

    /* Tabs */
    .stTabs [role="tab"] {
        background-color: #020617;
        color: #e5e7eb;
        padding: 0.5rem 1rem;
        border-radius: 999px 999px 0 0;
        border: 1px solid transparent;
        margin-right: 0.25rem;
    }
    .stTabs [role="tab"][aria-selected="true"] {
        border-bottom: 3px solid #38bdf8;
        border-top: 1px solid #1e293b;
        border-left: 1px solid #1e293b;
        border-right: 1px solid #1e293b;
        font-weight: 700;
        background-color: #020617;
    }

    /* Metrics – make them large + readable */
    div[data-testid="stMetric"] {
        background: #020617;
        border-radius: 1rem;
        padding: 0.9rem 1.0rem;
        border: 1px solid #1e293b;
    }
    div[data-testid="stMetric"] > label {
        color: #9ca3af !important;
        font-size: 0.9rem;
    }
    div[data-testid="stMetric"] > div {
        color: #e5e7eb !important;
        font-size: 1.6rem;
        font-weight: 700;
    }

    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #f9fafb;
    }

    /* Dataframes */
    .stDataFrame {
        background-color: #020617;
    }
    .stDataFrame table {
        color: #e5e7eb;
        font-size: 0.85rem;
    }

    /* PyVis container */
    .graph-container {
        border-radius: 1rem;
        overflow: hidden;
        border: 1px solid #1e293b;
    }

    /* Small subtle section separator */
    .section-card {
        background: #020617;
        border-radius: 1rem;
        border: 1px solid #1e293b;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Helper functions – Snowflake (LIVE)
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


def fetch_snowflake_summary_live(totp_code: str):
    """
    LIVE: returns counts + sample patients from Snowflake.
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
        ]:
            cur.execute(f"SELECT COUNT(*) FROM {view_name}")
            counts[key] = cur.fetchone()[0]

        cur.execute(
            """
            SELECT PATIENT_ID, FIRST_NAME, LAST_NAME, SEX, ZIP, AGE
            FROM V_PATIENTS
            LIMIT 20
            """
        )
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description]
        patients_sample = pd.DataFrame(rows, columns=cols)

        cur.close()
        return counts, patients_sample

    finally:
        if conn is not None:
            conn.close()

# -----------------------------------------------------------------------------
# Helper functions – Snowflake (MOCK)
# -----------------------------------------------------------------------------
def fetch_snowflake_summary_mock():
    """
    DEMO: mock counts + sample patients so UI works without Snowflake.
    """
    counts = {
        "patients": 1000,
        "encounters": 5300,
        "conditions": 2100,
        "medications": 850,
    }

    patients_sample = pd.DataFrame(
        [
            ["P001", "Alice", "Nguyen", "F", "02115", 45],
            ["P002", "Brian", "Lopez", "M", "02120", 52],
            ["P003", "Chitra", "Patel", "F", "02119", 39],
            ["P004", "Diego", "Santos", "M", "02111", 61],
            ["P005", "Elena", "Kovac", "F", "02116", 33],
        ],
        columns=["PATIENT_ID", "FIRST_NAME", "LAST_NAME", "SEX", "ZIP", "AGE"],
    )

    return counts, patients_sample

# -----------------------------------------------------------------------------
# Helper functions – AuraDB (LIVE)
# -----------------------------------------------------------------------------
def get_aura_driver():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    pwd = os.getenv("NEO4J_PASSWORD")
    if not uri or not user or not pwd:
        raise RuntimeError("NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD not set in .env")
    return GraphDatabase.driver(uri, auth=(user, pwd))


def fetch_aura_stats_live():
    """
    LIVE: High-level counts for key node labels + relationship type breakdown.
    """
    driver = get_aura_driver()
    try:
        with driver.session(database="neo4j") as session:
            node_counts = {}
            for label, key in [
                ("Patient", "patients"),
                ("Encounter", "encounters"),
                ("Condition", "conditions"),
                ("Medication", "medications"),
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

# -----------------------------------------------------------------------------
# Helper functions – AuraDB (MOCK)
# -----------------------------------------------------------------------------
def fetch_aura_stats_mock():
    """
    DEMO: mock node counts + relationship breakdown.
    """
    node_counts = {
        "patients": 1000,
        "encounters": 4500,
        "conditions": 2000,
        "medications": 1200,
    }

    rel_df = pd.DataFrame(
        [
            ["HAS_ENCOUNTER", 4500],
            ["HAS_CONDITION", 2800],
            ["TAKES_MEDICATION", 1900],
            ["PRESCRIBED", 1650],
        ],
        columns=["relationship_type", "total"],
    )
    return node_counts, rel_df

# -----------------------------------------------------------------------------
# Shared PyVis helper
# -----------------------------------------------------------------------------
def build_pyvis_from_edges(edge_rows, background_color="#020617"):
    """
    Build a PyVis Network from a simple edge list with node metadata.

    edge_rows: list of dicts with:
      - start_id, start_label
      - end_id, end_label
      - relationship_type
    """
    net = Network(
        height="520px",
        width="100%",
        bgcolor=background_color,
        font_color="#e5e7eb",
        notebook=False,
        directed=True,
    )

    node_seen = set()
    color_map = {
        "Patient": "#22d3ee",
        "Encounter": "#4ade80",
        "Condition": "#f97316",
        "Medication": "#a855f7",
        "Provider": "#facc15",
        "Guideline": "#f97316",
    }

    def add_node(node_id, label):
        if node_id in node_seen:
            return
        node_seen.add(node_id)
        color = color_map.get(label, "#38bdf8")
        net.add_node(
            node_id,
            label=str(node_id),
            title=f"{label} {node_id}",
            color=color,
        )

    for row in edge_rows:
        s_id = str(row["start_id"])
        e_id = str(row["end_id"])
        s_label = row["start_label"]
        e_label = row["end_label"]
        rel_type = row["relationship_type"]

        add_node(s_id, s_label)
        add_node(e_id, e_label)
        net.add_edge(s_id, e_id, label=rel_type)

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
          },
          "interaction": {
            "dragNodes": true,
            "dragView": true,
            "zoomView": true
          }
        }
        """
    )
    return net.generate_html(notebook=False)

# -----------------------------------------------------------------------------
# AuraDB – core graph query (LIVE)
# -----------------------------------------------------------------------------
def fetch_generic_graph_live(limit: int = 300):
    """
    LIVE: MATCH (n)-[r]->(m) RETURN n, r, m LIMIT $limit
    """
    driver = get_aura_driver()
    try:
        with driver.session(database="neo4j") as session:
            cypher = """
            MATCH (n)-[r]->(m)
            RETURN n, r, m
            LIMIT $limit
            """
            result = session.run(cypher, limit=limit)
            rows = list(result)

        if not rows:
            return pd.DataFrame(), "<html><body>No graph data returned.</body></html>"

        edge_records = []
        edge_rows_for_pyvis = []
        for row in rows:
            n = row["n"]
            m = row["m"]
            r = row["r"]
            n_labels = list(n.labels)
            m_labels = list(m.labels)
            edge_records.append(
                {
                    "start_id": n.get("id") or n.id,
                    "start_labels": ":".join(n_labels),
                    "relationship_type": r.type,
                    "end_id": m.get("id") or m.id,
                    "end_labels": ":".join(m_labels),
                }
            )
            edge_rows_for_pyvis.append(
                {
                    "start_id": n.get("id") or n.id,
                    "start_label": n_labels[0] if n_labels else "Node",
                    "end_id": m.get("id") or m.id,
                    "end_label": m_labels[0] if m_labels else "Node",
                    "relationship_type": r.type,
                }
            )

        df_edges = pd.DataFrame(edge_records)
        html = build_pyvis_from_edges(edge_rows_for_pyvis)
        return df_edges, html

    finally:
        driver.close()

# -----------------------------------------------------------------------------
# AuraDB – core graph query (MOCK)
# -----------------------------------------------------------------------------
def fetch_generic_graph_mock():
    """
    DEMO: small hard-coded graph that mimics a patient journey.
    """
    edge_rows = [
        {"start_id": "P001", "start_label": "Patient",   "relationship_type": "HAS_ENCOUNTER", "end_id": "E001", "end_label": "Encounter"},
        {"start_id": "P001", "start_label": "Patient",   "relationship_type": "HAS_CONDITION", "end_id": "C_Diabetes", "end_label": "Condition"},
        {"start_id": "P001", "start_label": "Patient",   "relationship_type": "HAS_CONDITION", "end_id": "C_HTN", "end_label": "Condition"},
        {"start_id": "P001", "start_label": "Patient",   "relationship_type": "TAKES_MEDICATION", "end_id": "M_Metformin", "end_label": "Medication"},
        {"start_id": "P001", "start_label": "Patient",   "relationship_type": "TAKES_MEDICATION", "end_id": "M_Lisinopril", "end_label": "Medication"},
        {"start_id": "E001", "start_label": "Encounter", "relationship_type": "SEEN_BY", "end_id": "Prov001", "end_label": "Provider"},
    ]

    df_edges = pd.DataFrame(
        [
            {
                "start_id": e["start_id"],
                "start_labels": e["start_label"],
                "relationship_type": e["relationship_type"],
                "end_id": e["end_id"],
                "end_labels": e["end_label"],
            }
            for e in edge_rows
        ]
    )
    html = build_pyvis_from_edges(edge_rows)
    return df_edges, html

# -----------------------------------------------------------------------------
# AuraDB – Patient Journey (LIVE)
# -----------------------------------------------------------------------------
def fetch_patient_journey_live(patient_id: str, limit: int = 150):
    """
    LIVE: patient neighborhood for the given id.
    """
    driver = get_aura_driver()
    try:
        with driver.session(database="neo4j") as session:
            cypher = """
            MATCH (p:Patient {id: $pid})-[r]-(n)
            RETURN p AS p, r, n AS n
            LIMIT $limit
            """
            result = session.run(cypher, pid=patient_id, limit=limit)
            rows = list(result)

        if not rows:
            return pd.DataFrame(), "<html><body>No graph found for this patient.</body></html>"

        edge_rows = []
        for row in rows:
            p = row["p"]
            n = row["n"]
            r = row["r"]
            p_labels = list(p.labels)
            n_labels = list(n.labels)
            edge_rows.append(
                {
                    "start_id": p.get("id") or p.id,
                    "start_label": p_labels[0] if p_labels else "Patient",
                    "relationship_type": r.type,
                    "end_id": n.get("id") or n.id,
                    "end_label": n_labels[0] if n_labels else "Node",
                }
            )

        df_edges = pd.DataFrame(
            [
                {
                    "patient_id": patient_id,
                    "start_labels": row["start_label"],
                    "relationship_type": row["relationship_type"],
                    "end_labels": row["end_label"],
                    "neighbor_id": row["end_id"],
                }
                for row in edge_rows
            ]
        )

        html = build_pyvis_from_edges(edge_rows)
        return df_edges, html

    finally:
        driver.close()

# -----------------------------------------------------------------------------
# AuraDB – Patient Journey (MOCK)
# -----------------------------------------------------------------------------
def fetch_patient_journey_mock(patient_id: str):
    """
    DEMO: simple patient journey centered on patient_id.
    """
    edge_rows = [
        {"start_id": patient_id, "start_label": "Patient",   "relationship_type": "HAS_ENCOUNTER", "end_id": "E_MOCK", "end_label": "Encounter"},
        {"start_id": patient_id, "start_label": "Patient",   "relationship_type": "HAS_CONDITION", "end_id": "C_MockCondition", "end_label": "Condition"},
        {"start_id": patient_id, "start_label": "Patient",   "relationship_type": "TAKES_MEDICATION", "end_id": "M_MockMed", "end_label": "Medication"},
    ]

    df_edges = pd.DataFrame(
        [
            {
                "patient_id": patient_id,
                "start_labels": e["start_label"],
                "relationship_type": e["relationship_type"],
                "end_labels": e["end_label"],
                "neighbor_id": e["end_id"],
            }
            for e in edge_rows
        ]
    )
    html = build_pyvis_from_edges(edge_rows)
    return df_edges, html

# -----------------------------------------------------------------------------
# NL Q&A (LIVE only – but we’ll gate it behind Live mode)
# -----------------------------------------------------------------------------
def answer_question_from_aura_live(question: str):
    """
    Simple NL → Cypher router.

    Supports:
      1) "show patients with diabetes"
      2) "show medications for diabetes"
      3) "show medications for patient P001"
    """
    q_raw = question.strip()
    q = q_raw.lower()

    driver = get_aura_driver()
    try:
        with driver.session(database="neo4j") as session:
            # 3) Medications for a given patient ID
            if "medications for patient" in q:
                pid = q.split("medications for patient", 1)[1].strip().upper()
                cypher = """
                    MATCH (p:Patient {id: $pid})-[:TAKES_MEDICATION]->(m:Medication)
                    RETURN p.id AS patient_id,
                           p.full_name AS full_name,
                           m.code AS rxnorm,
                           m.name AS medication
                    LIMIT 50
                """
                result = session.run(cypher, pid=pid)
                rows = list(result)
                if not rows:
                    return (
                        f"I couldn't find medications for patient **{pid}**.",
                        None,
                    )
                df = pd.DataFrame(
                    [
                        (row["patient_id"], row["full_name"], row["rxnorm"], row["medication"])
                        for row in rows
                    ],
                    columns=["patient_id", "full_name", "rxnorm", "medication"],
                )
                return f"Medications for patient **{pid}**:", df

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
                "- `show medications for patient P001`"
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
    "sf_patients_sample",
    "aura_connected",
    "aura_node_counts",
    "aura_rel_df",
    "aura_graph_df",
    "aura_graph_html",
    "aura_journey_df",
    "aura_journey_html",
]:
    if key not in st.session_state:
        st.session_state[key] = None

# -----------------------------------------------------------------------------
# Layout – Header
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div style="padding: 1.5rem 0 0.5rem 0;">
      <div style="display:flex; align-items:center; gap:0.75rem;">
        <div style="
          width:36px; height:36px; border-radius:999px;
          background:radial-gradient(circle at 30% 20%, #38bdf8, #0f172a);
          display:flex; align-items:center; justify-content:center;
          font-size:1.1rem;
        ">
          🧬
        </div>
        <div>
          <h1 style="margin-bottom: 0.1rem;">MediGraph AI</h1>
          <p style="color:#9ca3af; font-size:0.95rem; margin:0;">
            Healthcare intelligence powered by <b>Snowflake MEDIGRAPH</b> and <b>Neo4j AuraDB</b>.
          </p>
        </div>
      </div>
      <p style="color:#9ca3af; font-size:0.9rem; max-width:760px; margin-top:0.7rem;">
        This demo shows how synthetic EHR records become a patient journey knowledge graph with
        live queries and natural-language Q&amp;A.
      </p>
      <div style="margin-top:0.4rem;">
        <span style="background:#0f172a; color:#e5e7eb; padding:0.25rem 0.7rem; border-radius:999px; margin-right:0.4rem; font-size:0.8rem;">
          ❄️ Snowflake Lakehouse
        </span>
        <span style="background:#0f172a; color:#e5e7eb; padding:0.25rem 0.7rem; border-radius:999px; font-size:0.8rem;">
          🕸 Neo4j AuraDB Patient Graph
        </span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Sidebar – DEMO / LIVE toggle + connections
# -----------------------------------------------------------------------------
st.sidebar.markdown('<div class="sidebar-pill">Mode</div>', unsafe_allow_html=True)
mode = st.sidebar.radio(
    "Select data source",
    ["Demo (Mock Data)", "Live (Snowflake + AuraDB)"],
    index=0,
    help="Demo mode uses built-in mock data. Live mode queries Snowflake + AuraDB.",
)
demo_mode = mode == "Demo (Mock Data)"

st.sidebar.markdown('<div class="sidebar-pill">🔌 Connections</div>', unsafe_allow_html=True)
st.sidebar.header("MediGraph AI")

if demo_mode:
    # In demo mode we *don't* show live connection fields
    st.sidebar.info(
        "You are in **Demo (Mock Data)** mode. The UI is fully interactive\n"
        "using synthetic counts, tables, and graphs – no credentials required."
    )
    st.session_state.sf_connected = True
    st.session_state.aura_connected = True
    # Populate mock data immediately so tabs have something to render
    st.session_state.sf_counts, st.session_state.sf_patients_sample = fetch_snowflake_summary_mock()
    st.session_state.aura_node_counts, st.session_state.aura_rel_df = fetch_aura_stats_mock()
else:
    # Live mode – show real connection controls
    st.sidebar.subheader("❄️ Snowflake (MEDIGRAPH)")
    sf_totp = st.sidebar.text_input(
        "Snowflake TOTP (6 digits)",
        type="password",
        max_chars=6,
        help="Time-based one-time password used for Snowflake multi-factor authentication.",
    )

    if st.sidebar.button("Connect to Snowflake"):
        if not sf_totp:
            st.sidebar.error("Please enter your Snowflake TOTP code.")
        else:
            try:
                counts, sample = fetch_snowflake_summary_live(sf_totp)
                st.session_state.sf_connected = True
                st.session_state.sf_counts = counts
                st.session_state.sf_patients_sample = sample
                st.sidebar.success(
                    f"Connected – Patients: {counts['patients']}, "
                    f"Encounters: {counts['encounters']}"
                )
            except Exception as e:
                st.session_state.sf_connected = False
                st.sidebar.error(f"Snowflake connection failed: {e}")

    st.sidebar.subheader("🕸 Neo4j AuraDB (MediGraphAI)")
    if st.sidebar.button("Test AuraDB connection"):
        try:
            node_counts, rel_df = fetch_aura_stats_live()
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
    "Tip: Start in **Demo (Mock Data)** to show the UI, then switch to **Live** to hit Snowflake + AuraDB."
)

# -----------------------------------------------------------------------------
# Main tabs
# -----------------------------------------------------------------------------
tab_overview, tab_sf, tab_aura_data, tab_aura_graph, tab_qa = st.tabs(
    [
        "🏠 Product Overview",
        "❄️ Snowflake Views",
        "🕸 AuraDB Data",
        "🧭 AuraDB Graph Explorer",
        "💬 NL Q&A",
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
            "🟢 Demo (mock)" if demo_mode else (
                "🟢 Connected" if st.session_state.sf_connected else "🔴 Not connected"
            )
        )
        aura_status = (
            "🟢 Demo (mock)" if demo_mode else (
                "🟢 Connected" if st.session_state.aura_connected else "🔴 Not connected"
            )
        )
        st.markdown(
            f"""
            **Connection status**

            - Mode: **{mode}**  
            - Snowflake (MEDIGRAPH): **{sf_status}**  
            - Neo4j AuraDB (MediGraphAI): **{aura_status}**
            """
        )

    with col2:
        st.markdown(
            """
            **Pipeline (high level)**

            1. Synthetic EHR data ingested into **Snowflake MEDIGRAPH**.  
            2. Python ETL builds a **patient journey graph** in AuraDB.  
            3. This app surfaces counts, graph structure, and **NL Q&A** over the graph.  
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
        sample = st.session_state.sf_patients_sample

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("V_PATIENTS", counts.get("patients", 0))
        c2.metric("V_ENCOUNTERS", counts.get("encounters", 0))
        c3.metric("V_CONDITIONS", counts.get("conditions", 0))
        c4.metric("V_MEDICATIONS", counts.get("medications", 0))

        st.markdown("### Sample patients from `V_PATIENTS`")
        st.dataframe(sample, use_container_width=True)

# -----------------------------------------------------------------------------
# Tab: AuraDB Data (counts)
# -----------------------------------------------------------------------------
with tab_aura_data:
    st.subheader("AuraDB – Patient Graph Data")

    if not st.session_state.aura_connected:
        st.info("Click **Test AuraDB connection** in the sidebar first (or switch to Demo mode).")
    else:
        node_counts = st.session_state.aura_node_counts or {}
        rel_df = st.session_state.aura_rel_df

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Patient nodes", node_counts.get("patients", 0))
        c2.metric("Encounter nodes", node_counts.get("encounters", 0))
        c3.metric("Condition nodes", node_counts.get("conditions", 0))
        c4.metric("Medication nodes", node_counts.get("medications", 0))

        st.markdown("### Relationship Types in AuraDB")
        st.dataframe(rel_df, use_container_width=True)

        st.markdown(
            """
            These counts are pulled from **AuraDB** (or mocked in demo mode), reflecting relationships such as  
            `HAS_ENCOUNTER`, `HAS_CONDITION`, `TAKES_MEDICATION`, and `PRESCRIBED`.
            """
        )

# -----------------------------------------------------------------------------
# Tab: AuraDB Graph Explorer (Data / Graph / Patient Journey)
# -----------------------------------------------------------------------------
with tab_aura_graph:
    st.subheader("AuraDB – Live Graph Explorer")

    if not st.session_state.aura_connected:
        st.info("Please connect to AuraDB from the sidebar, or switch to Demo mode.")
    else:
        st.markdown(
            "This explorer uses the **real AuraDB graph** when in Live mode, or a built-in\n"
            "synthetic patient journey graph in Demo mode.\n\n"
            "**Core query in Live mode:**\n\n"
            "`MATCH (n)-[r]->(m) RETURN n, r, m LIMIT $limit`"
        )

        sub_tab_data, sub_tab_graph, sub_tab_journey = st.tabs(
            ["📊 Data", "🕸 Graph", "🚶 Patient Journey"]
        )

        # ---------- Data tab ----------
        with sub_tab_data:
            st.markdown("#### Edge Table from Core Graph Query")

            max_edges = st.slider(
                "Number of `(n)-[r]->(m)` triples to fetch",
                min_value=50,
                max_value=300,
                value=150,
                step=50,
                help="Controls LIMIT in the Cypher query (for Live) or size of mock graph (Demo).",
            )

            if st.button("Run graph data query", key="run_graph_data"):
                with st.spinner("Preparing graph data..."):
                    try:
                        if demo_mode:
                            df_edges, html = fetch_generic_graph_mock()
                        else:
                            df_edges, html = fetch_generic_graph_live(limit=max_edges)
                        st.session_state.aura_graph_df = df_edges
                        st.session_state.aura_graph_html = html
                    except Exception as e:
                        st.error(f"Failed to load graph: {e}")

            if st.session_state.aura_graph_df is not None:
                st.dataframe(st.session_state.aura_graph_df, use_container_width=True)
            else:
                st.info("Click **Run graph data query** to view edge data.")

        # ---------- Graph tab ----------
        with sub_tab_graph:
            st.markdown("#### Interactive Graph View")
            st.markdown(
                "Pan with drag, zoom with scroll, and hover over nodes to see details."
            )

            if st.session_state.aura_graph_html:
                st.markdown('<div class="graph-container">', unsafe_allow_html=True)
                components.html(
                    st.session_state.aura_graph_html,
                    height=540,
                    scrolling=False,
                )
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info(
                    "No graph yet. Run the query from the **Data** tab to populate the viewer."
                )

        # ---------- Patient Journey tab ----------
        with sub_tab_journey:
            st.markdown("#### Patient Journey Graph")

            default_pid = "P001" if demo_mode else "P001"
            patient_id = st.text_input(
                "Patient ID (e.g., P001)",
                value=default_pid,
                help="Enter a patient id present in your graph to see their local journey.",
            )

            journey_limit = st.slider(
                "Max relationships to follow around this patient (Live mode only)",
                min_value=50,
                max_value=300,
                value=150,
                step=50,
                help="Upper bound on the number of relationships returned in Live mode.",
            )

            if st.button("Load patient journey graph", key="load_patient_journey"):
                if not patient_id.strip():
                    st.warning("Please enter a patient id.")
                else:
                    with st.spinner(f"Loading journey graph for patient {patient_id}…"):
                        try:
                            if demo_mode:
                                df_journey, html_journey = fetch_patient_journey_mock(
                                    patient_id.strip().upper()
                                )
                            else:
                                df_journey, html_journey = fetch_patient_journey_live(
                                    patient_id.strip().upper(), limit=journey_limit
                                )
                            st.session_state.aura_journey_df = df_journey
                            st.session_state.aura_journey_html = html_journey
                        except Exception as e:
                            st.error(f"Failed to load patient journey: {e}")

            if st.session_state.aura_journey_df is not None:
                st.markdown("##### Journey Edges")
                st.dataframe(
                    st.session_state.aura_journey_df,
                    use_container_width=True,
                )

            if st.session_state.aura_journey_html:
                st.markdown("##### Journey Graph")
                st.markdown('<div class="graph-container">', unsafe_allow_html=True)
                components.html(
                    st.session_state.aura_journey_html,
                    height=540,
                    scrolling=False,
                )
                st.markdown('</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Tab: NL Q&A
# -----------------------------------------------------------------------------
with tab_qa:
    st.subheader("Natural-Language Q&A over AuraDB")

    st.markdown(
        """
        **Supported question types in Live mode:**

        1. Patients by condition  
           - `show patients with diabetes`  
           - `show patients with hypertension`  

        2. Medications by condition  
           - `show medications for diabetes`  

        3. Medications by patient  
           - `show medications for patient P001`  
        """
    )

    if demo_mode:
        st.info(
            "NL Q&A currently requires **Live (Snowflake + AuraDB)** mode "
            "because it runs real Cypher queries. Switch to Live mode in the sidebar."
        )
    else:
        if not st.session_state.aura_connected:
            st.info("Please connect to AuraDB from the sidebar first.")
        else:
            question = st.text_input(
                "Ask a question about conditions or medications:",
                value="show patients with diabetes",
                help="Simple NL router that currently supports patients/conditions/medications.",
            )
            run = st.button("Run NL query")
            if run:
                if not question.strip():
                    st.warning("Please type a question first.")
                else:
                    with st.spinner("Querying AuraDB…"):
                        answer_text, df = answer_question_from_aura_live(question)
                    st.markdown(answer_text)
                    if df is not None and not df.empty:
                        st.dataframe(df, use_container_width=True)


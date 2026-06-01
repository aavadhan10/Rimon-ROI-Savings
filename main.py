import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
import re
from collections import Counter

# ---------------------------------------------------------------------------
# Data file paths
# ---------------------------------------------------------------------------
CSV_PATH = '2025_Jan-Oct_time_entry_export.csv'
XLSX_CURRENCY_PATH = os.path.join(
    '2025-11_to_2026-05_data',
    'RPC_FMS_Time_Entries_w_Currency_2025_11_01 _to_2026_05_29.xlsx'
)
DETAIL_CSV_PATH = 'matter_description.csv'
DETAIL_XLSX_PATH = os.path.join(
    '2025-11_to_2026-05_data',
    'RPC_FMS_Time_Entries_w_Activities_2025_11_01_to_2026_05_29.xlsx'
)
# Entries with Date of Work beyond this date are future-dated flat fees;
# exclude them so the projections tab works correctly.
DATA_CUTOFF_DATE = pd.Timestamp('2026-05-29')

# Page configuration
st.set_page_config(
    page_title="Rimon Legal AI Automation Dashboard",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .insight-box {
        background-color: #e8f4f8;
        padding: 15px;
        border-left: 5px solid #1f77b4;
        margin: 10px 0;
        border-radius: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# LegalBench Task Categories adapted for Rimon's matter-based classification
LEGALBENCH_TASKS = {
    # CONTRACT ANALYSIS & REVIEW (High automation 85-95%)
    'Contract-Clause-Identification': {
        'description': 'Identifying and extracting specific contract clauses',
        'automation_potential': 0.92,
        'keywords': ['contract', 'agreement', 'lease', 'license', 'licensing', 'amendment',
                    'addendum', 'nda', 'msa', 'sla', 'consulting agreement', 'service agreement',
                    'vendor', 'supplier', 'procurement', 'terms', 'clause review'],
        'examples': ['Contract review', 'Lease agreements', 'Service agreements']
    },
    
    # M&A AND CORPORATE (Medium-High automation 75-90%)
    'MA-Deal-Terms': {
        'description': 'M&A deal terms analysis and acquisition matters',
        'automation_potential': 0.82,
        'keywords': ['acquisition', 'merger', 'buyout', 'purchase', 'sale', 'transaction',
                    'm&a', 'due diligence', 'closing', 'earnout', 'escrow', 'indemnit',
                    'representation and warrant', 'definitive agreement'],
        'examples': ['M&A transactions', 'Acquisitions', 'Corporate sales']
    },
    'Corporate-Governance': {
        'description': 'Corporate governance, formation, and general corporate matters',
        'automation_potential': 0.80,
        'keywords': ['general corporate', 'corporate matters', 'corporate governance', 
                    'formation', 'incorporation', 'llc', 'corporation', 'bylaws', 
                    'operating agreement', 'shareholder', 'board', 'director', 'officer',
                    'corporate advice', 'general representation', 'retainer',
                    'corporate counsel', 'spv', 'entity'],
        'examples': ['Corporate formation', 'General corporate counsel', 'Entity structuring']
    },
    'Securities-Compliance': {
        'description': 'Securities matters and compliance',
        'automation_potential': 0.78,
        'keywords': ['securities', 'sec', 'offering', 'private placement', 'regulation d',
                    'stock', 'equity', 'financing', 'investment', 'fund', 'investor'],
        'examples': ['Securities filings', 'Private placements', 'Fund matters']
    },
    
    # LITIGATION & PROCEDURE (Medium automation 70-85%)
    'Litigation-Matters': {
        'description': 'Litigation, disputes, and court proceedings',
        'automation_potential': 0.75,
        'keywords': [' v ', ' v. ', ' vs ', ' vs. ', ' versus ', 'litigation', 'lawsuit',
                    'complaint', 'dispute', 'arbitration', 'mediation', 'trial', 'hearing',
                    'motion', 'discovery', 'deposition', 'settlement', 'judgment',
                    'appeal', 'court', 'plaintiff', 'defendant'],
        'examples': ['Civil litigation', 'Commercial disputes', 'Court proceedings']
    },
    'Bankruptcy-Receivership': {
        'description': 'Bankruptcy and receivership matters',
        'automation_potential': 0.73,
        'keywords': ['bankruptcy', 'chapter 11', 'chapter 7', 'receiver', 'receivership',
                    'creditor', 'debtor', 'insolvency', 'reorganization', 'liquidation'],
        'examples': ['Bankruptcy proceedings', 'Receivership matters', 'Creditor rights']
    },
    
    # EMPLOYMENT & HR (Medium-High automation 75-85%)
    'Employment-Law': {
        'description': 'Employment contracts, disputes, and HR matters',
        'automation_potential': 0.80,
        'keywords': ['employment', 'employee', 'hr ', 'human resources', 'labor',
                    'termination', 'severance', 'discrimination', 'harassment',
                    'wage', 'compensation', 'benefits', 'non-compete', 'restrictive covenant',
                    'wrongful termination', 'employment agreement'],
        'examples': ['Employment agreements', 'HR compliance', 'Wrongful termination']
    },
    
    # REAL ESTATE (Medium automation 70-80%)
    'Real-Estate': {
        'description': 'Real estate transactions and property matters',
        'automation_potential': 0.75,
        'keywords': ['real estate', 'property', 'lease', 'landlord', 'tenant', 'rental',
                    'commercial lease', 'retail lease', 'office lease', 'title',
                    'escrow', 'deed', 'mortgage', 'foreclosure', 'easement', 'zoning'],
        'examples': ['Lease negotiations', 'Property acquisitions', 'Real estate closings']
    },
    
    # INTELLECTUAL PROPERTY (High automation 85-90%)
    'Intellectual-Property': {
        'description': 'IP matters including patents, trademarks, and copyrights',
        'automation_potential': 0.85,
        'keywords': ['patent', 'trademark', 'copyright', 'intellectual property', ' ip ',
                    'infringement', 'licensing', 'royalty', 'trade secret', 'confidential',
                    'epo', 'uspto', 'office action', 'prosecution', 'portfolio'],
        'examples': ['Patent prosecution', 'Trademark filing', 'IP licensing']
    },
    
    # ESTATE PLANNING & TRUSTS (High automation 80-90%)
    'Estate-Planning': {
        'description': 'Estate planning, wills, trusts, and probate',
        'automation_potential': 0.88,
        'keywords': ['estate planning', 'estate', 'trust', 'will', 'probate',
                    'trustee', 'beneficiary', 'inheritance', 'succession', 'gift',
                    'estate tax', 'generation skipping', 'living trust', 'testamentary',
                    'administration', 'executor', 'fiduciary'],
        'examples': ['Estate planning', 'Trust administration', 'Will preparation']
    },
    
    # FAMILY LAW (Medium automation 65-75%)
    'Family-Law': {
        'description': 'Divorce, custody, and family law matters',
        'automation_potential': 0.68,
        'keywords': ['divorce', 'dissolution', 'marriage', 'custody', 'child support',
                    'alimony', 'spousal support', 'marital', 'family law', 'prenup',
                    'postnup', 'separation', 'domestic', 'parenting', 'visitation'],
        'examples': ['Divorce proceedings', 'Custody matters', 'Support calculations']
    },
    
    # TAX (Medium automation 70-80%)
    'Tax-Law': {
        'description': 'Tax planning, compliance, and disputes',
        'automation_potential': 0.75,
        'keywords': ['tax', 'irs', 'taxation', 'tax planning', 'tax compliance',
                    'tax return', 'audit', 'tax dispute', 'tax opinion', 'tax structure'],
        'examples': ['Tax planning', 'IRS disputes', 'Tax compliance']
    },
    
    # IMMIGRATION (Medium automation 70-80%)
    'Immigration-Law': {
        'description': 'Immigration and visa matters',
        'automation_potential': 0.78,
        'keywords': ['immigration', 'visa', 'h-1b', 'green card', 'citizenship',
                    'naturalization', 'deportation', 'asylum', 'refugee', 'work permit',
                    'uscis', 'ice', 'border', 'immigrant'],
        'examples': ['Visa applications', 'Immigration compliance', 'Citizenship matters']
    },
    
    # REGULATORY & COMPLIANCE (High automation 80-90%)
    'Regulatory-Compliance': {
        'description': 'Regulatory compliance and government affairs',
        'automation_potential': 0.83,
        'keywords': ['regulatory', 'compliance', 'regulation', 'permit', 'license',
                    'government', 'agency', 'fda', 'epa', 'osha', 'ftc', 'fcc',
                    'administrative', 'rulemaking', 'enforcement', 'investigation'],
        'examples': ['Regulatory compliance', 'Government permits', 'Agency matters']
    },
    
    # CANNABIS (Medium automation 70-80%)
    'Cannabis-Law': {
        'description': 'Cannabis industry legal matters',
        'automation_potential': 0.72,
        'keywords': ['cannabis', 'marijuana', 'dispensary', 'cultivation', 'cbd',
                    'thc', 'hemp', 'marijuana license', 'cannabis license'],
        'examples': ['Cannabis licensing', 'Dispensary operations', 'Cannabis compliance']
    },
    
    # HEALTHCARE (Medium automation 70-80%)
    'Healthcare-Law': {
        'description': 'Healthcare and medical law matters',
        'automation_potential': 0.74,
        'keywords': ['healthcare', 'medical', 'hospital', 'physician', 'hipaa',
                    'health insurance', 'medicare', 'medicaid', 'pharmaceutical'],
        'examples': ['Healthcare compliance', 'Medical practice matters', 'HIPAA compliance']
    },
    
    # ADMINISTRATIVE & ROUTINE (Very High automation 90-95%)
    'General-Matters': {
        'description': 'General advice, consultation, and miscellaneous matters',
        'automation_potential': 0.65,
        'keywords': ['general matters', 'general', 'advice', 'counsel', 'consultation',
                    'miscellaneous', 'various', 'other'],
        'examples': ['General advice', 'Consultations', 'Miscellaneous matters']
    },
    
    # INTERNAL TIME (0% automation - not client work)
    'Internal-Time': {
        'description': 'Internal firm time - administrative and non-billable',
        'automation_potential': 0.00,
        'keywords': ['internal time', 'internal', 'admin', 'administrative', 'training',
                    'business development', 'marketing', 'firm', 'vacation', 'pto',
                    'sick', 'holiday'],
        'examples': ['Internal meetings', 'Training', 'Administrative tasks']
    }
}

# Rimon-specific OLI Benchmark
RIMON_OLI_BENCHMARK = {
    '100% AI Replaceable - Routine Corporate & Documents': {
        'automation_potential': 1.00,
        'keywords': [
            'general corporate', 'corporate matters', 'general representation',
            'retainer', 'general matters', 'general', 'advice and counsel',
            'corporate advice', 'general corporate advice'
        ],
        'description': 'Routine corporate counsel and document review',
        'examples': ['General corporate matters', 'Routine advice', 'Document review']
    },
    '100% AI Replaceable - Estate Planning': {
        'automation_potential': 1.00,
        'keywords': [
            'estate planning', 'estate', 'trust', 'will', 'probate',
            'trust administration'
        ],
        'description': 'Estate planning documents and trust administration - highly templated',
        'examples': ['Estate planning', 'Trust documents', 'Will preparation']
    },
    '70% AI Replaceable - Transactional Work': {
        'automation_potential': 0.70,
        'keywords': [
            'acquisition', 'merger', 'purchase', 'sale', 'transaction',
            'financing', 'investment', 'fund', 'securities',
            'lease', 'real estate', 'property'
        ],
        'description': 'M&A, financing, and complex transactional work',
        'examples': ['Acquisitions', 'Financings', 'Real estate transactions']
    },
    '70% AI Replaceable - IP & Regulatory': {
        'automation_potential': 0.70,
        'keywords': [
            'patent', 'trademark', 'copyright', 'intellectual property',
            'regulatory', 'compliance', 'permit', 'license',
            'immigration', 'visa'
        ],
        'description': 'IP prosecution and regulatory compliance',
        'examples': ['Patent filings', 'Trademark prosecution', 'Regulatory compliance']
    },
    '30% AI Replaceable - Litigation & Complex Matters': {
        'automation_potential': 0.30,
        'keywords': [
            ' v ', ' v. ', ' vs ', ' vs. ', 'litigation', 'lawsuit', 'dispute',
            'arbitration', 'trial', 'court', 'motion', 'discovery',
            'bankruptcy', 'receiver', 'settlement'
        ],
        'description': 'Litigation and complex disputes requiring significant judgment',
        'examples': ['Civil litigation', 'Arbitrations', 'Court proceedings']
    },
    '30% AI Replaceable - Employment & Family Law': {
        'automation_potential': 0.30,
        'keywords': [
            'employment', 'hr ', 'labor', 'termination',
            'divorce', 'dissolution', 'custody', 'family law',
            'tax'
        ],
        'description': 'Matters requiring nuanced human judgment and counseling',
        'examples': ['Employment disputes', 'Divorce matters', 'Tax planning']
    },
    '0% AI Replaceable - Internal & Strategic': {
        'automation_potential': 0.00,
        'keywords': [
            'internal time', 'vacation', 'pto', 'holiday', 'training',
            'business development', 'marketing', 'admin'
        ],
        'description': 'Internal time and strategic work',
        'examples': ['Internal meetings', 'Business development', 'Training']
    }
}


# ============================================================================
# TASK-LEVEL CLASSIFICATION (for detailed description CSV)
# ============================================================================
TASK_LEVEL_AUTOMATION = {
    'Document-Review-Standard': {'description': 'Review of standard documents', 'automation_potential': 0.95, 'keywords': ['review agreement', 'review contract', 'review and revise', 'review draft', 'review standard', 'review form', 'review template', 'review nda', 'review msa', 'review amendment', 'review lease']},
    'Email-Status-Updates': {'description': 'Status update emails', 'automation_potential': 0.92, 'keywords': ['email regarding status', 'email correspondence regarding', 'status update', 'follow up email', 'exchange emails', 'email to client regarding status']},
    'Document-Drafting-Standard': {'description': 'Drafting standard forms', 'automation_potential': 0.93, 'keywords': ['draft amendment', 'draft addendum', 'draft standard', 'draft form', 'draft certificate', 'draft notice', 'draft letter agreement', 'prepare draft amendment']},
    'Research-Straightforward': {'description': 'Straightforward legal research', 'automation_potential': 0.88, 'keywords': ['research case law', 'research statute', 'research regulation', 'research precedent', 'legal research regarding']},
    'Form-Completion': {'description': 'Completing forms', 'automation_potential': 0.96, 'keywords': ['complete form', 'fill out', 'prepare filing', 'file notice', 'file certificate', 'submit form']},
    'Document-Analysis': {'description': 'Analyzing documents', 'automation_potential': 0.85, 'keywords': ['review and analyze', 'analyze agreement', 'analyze contract', 'analyze terms', 'analyze provision', 'review for compliance', 'analyze draft']},
    'Due-Diligence-Review': {'description': 'Due diligence review', 'automation_potential': 0.82, 'keywords': ['due diligence', 'dd review', 'review due diligence', 'diligence materials', 'data room review']},
    'Discovery-Review': {'description': 'Document discovery review', 'automation_potential': 0.87, 'keywords': ['review discovery', 'review production', 'review interrogator', 'review request for production', 'discovery response', 'respond to discovery']},
    'Clause-Extraction': {'description': 'Extracting specific clauses', 'automation_potential': 0.90, 'keywords': ['extract provision', 'identify clause', 'locate language', 'find provision', 'pull clause', 'summarize terms']},
    'Drafting-Complex': {'description': 'Drafting complex agreements', 'automation_potential': 0.65, 'keywords': ['draft purchase agreement', 'draft psa', 'draft merger agreement', 'draft complex', 'draft financing', 'draft loan', 'draft settlement']},
    'Negotiation-Support': {'description': 'Supporting negotiations', 'automation_potential': 0.60, 'keywords': ['revise per comments', 'address comments', 'incorporate revisions', 'revise based on', 'respond to comments', 'counter proposal']},
    'Legal-Memos': {'description': 'Legal memoranda', 'automation_potential': 0.55, 'keywords': ['draft memo', 'memorandum', 'legal opinion', 'prepare memo', 'draft analysis', 'memo regarding']},
    'Client-Calls': {'description': 'Client communications', 'automation_potential': 0.45, 'keywords': ['call with client', 'telephone conference with', 'conference call', 'client meeting', 'discuss with client', 'call regarding', 'phone call']},
    'Court-Appearances': {'description': 'Court appearances', 'automation_potential': 0.30, 'keywords': ['court appearance', 'appear in court', 'attend hearing', 'oral argument', 'trial', 'deposition', 'attend conference']},
    'Strategic-Advice': {'description': 'Strategic legal counseling', 'automation_potential': 0.35, 'keywords': ['advise regarding', 'counsel regarding', 'discuss strategy', 'strategic advice', 'recommendation regarding', 'consult on']},
    'Negotiations': {'description': 'Negotiation sessions', 'automation_potential': 0.25, 'keywords': ['negotiate', 'negotiation', 'negotiating', 'negotiate terms', 'negotiate with', 'settlement discussion']},
    'Internal-Admin': {'description': 'Internal administrative tasks', 'automation_potential': 0.10, 'keywords': ['internal', 'administrative', 'firm meeting', 'training', 'business development', 'marketing', 'time entry', 'billing']},
    'General-Communication': {'description': 'General correspondence', 'automation_potential': 0.50, 'keywords': ['email', 'correspondence', 'communicate', 'discuss', 'exchange', 'speak with', 'follow up']}
}

def classify_task_description(description):
    """Classify based on detailed task description"""
    if pd.isna(description):
        return 'General-Communication', 0.50
    desc_lower = description.lower()
    scores = {}
    for category, info in TASK_LEVEL_AUTOMATION.items():
        score = sum(1 for keyword in info['keywords'] if keyword in desc_lower)
        if score > 0:
            scores[category] = score
    if scores:
        best_category = max(scores, key=scores.get)
        return best_category, TASK_LEVEL_AUTOMATION[best_category]['automation_potential']
    return 'General-Communication', 0.50

@st.cache_data
def load_detailed_data():
    """Load and combine task-level description data from all available sources.

    Sources (combined if both exist):
    - matter_description.csv  – Oct 2025, messy multi-block CSV export
    - DETAIL_XLSX_PATH        – Nov 2025–May 2026, clean flat Excel export
    """
    dfs = []

    # --- Oct 2025 CSV (messy multi-block format) ---
    for path in ['./data/matter_description.csv', 'matter_description.csv',
                 './matter_description.csv']:
        if os.path.exists(path):
            try:
                df_csv = pd.read_csv(
                    path, skiprows=2, encoding='utf-8-sig', on_bad_lines='skip'
                )
                df_csv.columns = df_csv.columns.str.replace('\n', ' ').str.strip()
                # Strip out subtotal / grand-total rows that the multi-block export injects
                if 'ID' in df_csv.columns:
                    df_csv = df_csv[
                        pd.to_numeric(df_csv['ID'], errors='coerce').notna()
                    ]
                dfs.append(df_csv)
            except Exception:
                pass
            break

    # --- Nov 2025–May 2026 Activities Excel (clean flat table) ---
    if os.path.exists(DETAIL_XLSX_PATH):
        try:
            df_xlsx = pd.read_excel(DETAIL_XLSX_PATH, header=0)
            dfs.append(df_xlsx)
        except Exception:
            pass

    if not dfs:
        return None

    df = pd.concat(dfs, ignore_index=True)

    # Normalise column names (strip whitespace / embedded newlines)
    df.columns = df.columns.str.replace('\n', ' ').str.strip()

    # Unified column mapping for both sources
    df = df.rename(columns={
        'Entry Date':   'Date',
        'Billable Time':'Hours',
        'Total Time':   'Total_Hours',
        'Billable Amt': 'Billable_Amount',
        'User':         'User_Name',
    })

    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Hours'] = pd.to_numeric(df['Hours'], errors='coerce').fillna(0)

    # Drop rows with no parseable date (subtotals, blank lines, etc.)
    df = df[df['Date'].notna()]

    df['Year'] = df['Date'].dt.year
    df['Month'] = df['Date'].dt.month
    df['Month_Name'] = df['Date'].dt.strftime('%B')
    df['Quarter'] = df['Date'].dt.quarter
    df['Description'] = df['Description'].fillna('Unknown')

    return df


def check_for_detailed_data():
    """Return True if any task-level detail data source exists."""
    csv_exists = any(
        os.path.exists(p)
        for p in ['./data/matter_description.csv', 'matter_description.csv',
                  './matter_description.csv']
    )
    return csv_exists or os.path.exists(DETAIL_XLSX_PATH)

def classify_matter_legalbench(matter_name):
    """Classify a matter using LegalBench framework"""
    if pd.isna(matter_name):
        return 'General-Matters', 0.65
    
    matter_lower = matter_name.lower()
    
    # Score each category
    scores = {}
    for category, info in LEGALBENCH_TASKS.items():
        score = sum(1 for keyword in info['keywords'] if keyword in matter_lower)
        if score > 0:
            scores[category] = score
    
    if scores:
        best_category = max(scores, key=scores.get)
        automation_potential = LEGALBENCH_TASKS[best_category]['automation_potential']
        return best_category, automation_potential
    else:
        return 'General-Matters', 0.65

def classify_matter_oli(matter_name):
    """Classify a matter using Rimon OLI Benchmark"""
    if pd.isna(matter_name):
        return 'Unclassified', 0.0
    
    matter_lower = matter_name.lower()
    
    # Check for internal time first (0% automation)
    if 'internal time' in matter_lower or 'vacation' in matter_lower:
        return '0% AI Replaceable - Internal & Strategic', 0.0
    
    # Score each category
    scores = {}
    for category, info in RIMON_OLI_BENCHMARK.items():
        if category == '0% AI Replaceable - Internal & Strategic':
            continue
        score = sum(1 for keyword in info['keywords'] if keyword in matter_lower)
        if score > 0:
            scores[category] = score
    
    if scores:
        best_category = max(scores, key=scores.get)
        automation_potential = RIMON_OLI_BENCHMARK[best_category]['automation_potential']
        return best_category, automation_potential
    else:
        return 'Unclassified', 0.0

@st.cache_data
def load_data():
    """Load and combine Jan–Oct 2025 CSV with Nov 2025–May 2026 Excel."""
    dfs = []

    # --- Jan–Oct 2025 CSV ---
    if os.path.exists(CSV_PATH):
        df_csv = pd.read_csv(CSV_PATH, skiprows=2, encoding='utf-8-sig')
        df_csv['Date of Work'] = pd.to_datetime(
            df_csv['Date of Work'], format='%m/%d/%Y', errors='coerce'
        )
        df_csv['Date Created'] = pd.to_datetime(
            df_csv['Date Created'], format='%m/%d/%Y', errors='coerce'
        )
        # CSV stores un-invoiced rows as the literal string "null"
        df_csv['Invoice ID'] = df_csv['Invoice ID'].replace('null', pd.NA)
        dfs.append(df_csv)

    # --- Nov 2025–May 2026 Excel ---
    if os.path.exists(XLSX_CURRENCY_PATH):
        df_xlsx = pd.read_excel(XLSX_CURRENCY_PATH, header=0)
        # Dates arrive as datetime objects; coerce any edge cases
        df_xlsx['Date of Work'] = pd.to_datetime(df_xlsx['Date of Work'], errors='coerce')
        df_xlsx['Date Created'] = pd.to_datetime(df_xlsx['Date Created'], errors='coerce')
        dfs.append(df_xlsx)

    if not dfs:
        raise FileNotFoundError(
            f"No data files found. Expected:\n  {CSV_PATH}\n  {XLSX_CURRENCY_PATH}"
        )

    df = pd.concat(dfs, ignore_index=True)

    # Drop any accidental duplicates (same Time Entry ID in both files)
    df = df.drop_duplicates(subset=['Time Entry ID'])

    # Exclude future-dated flat-fee entries beyond the export cutoff so
    # the projections tab doesn't treat them as actual future-month data.
    df = df[df['Date of Work'] <= DATA_CUTOFF_DATE]

    # Convert hours to numeric
    df['Billable Hours'] = pd.to_numeric(df['Billable Hours'], errors='coerce').fillna(0)

    # Derive time columns
    df['Year'] = df['Date of Work'].dt.year
    df['Month'] = df['Date of Work'].dt.month
    df['Month_Name'] = df['Date of Work'].dt.strftime('%B')
    df['Quarter'] = df['Date of Work'].dt.quarter

    df['Matter Name'] = df['Matter Name'].fillna('Unknown')

    return df

def extract_keywords(matter_names):
    """Extract common keywords from matter names"""
    all_words = []
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                  'of', 'with', 're', 'from', 'by', 'as', 'is', 'was', 'be', 'been',
                  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                  'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those',
                  'llc', 'inc', 'corp', 'ltd', 'vs', 'v'}
    
    for matter in matter_names:
        if pd.notna(matter):
            words = re.findall(r'\b[a-z]{4,}\b', matter.lower())
            all_words.extend([w for w in words if w not in stop_words])
    
    return Counter(all_words).most_common(30)

def check_password():
    """Returns `True` if the user had the correct password."""
    
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == "RimonAI2025":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown('<h1 class="main-header">⚖️ Rimon Legal AI Automation Dashboard</h1>', unsafe_allow_html=True)
        st.markdown("### 🔐 Secure Access Required")
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input(
                "Enter Password", 
                type="password", 
                on_change=password_entered, 
                key="password",
                help="Contact your administrator for access"
            )
            st.info("💡 This dashboard contains confidential firm data and automation analysis.")
        return False
    
    elif not st.session_state["password_correct"]:
        st.markdown('<h1 class="main-header">⚖️ Rimon Legal AI Automation Dashboard</h1>', unsafe_allow_html=True)
        st.markdown("### 🔐 Secure Access Required")
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input(
                "Enter Password", 
                type="password", 
                on_change=password_entered, 
                key="password",
                help="Contact your administrator for access"
            )
            st.error("❌ Incorrect password. Please try again.")
        return False
    
    else:
        return True

def main():
    # Check password first
    if not check_password():
        return
    
    st.markdown('<h1 class="main-header">⚖️ Rimon Legal AI Automation Dashboard</h1>', unsafe_allow_html=True)
    st.markdown("### Rimon P.C. - AI-Powered Efficiency Analysis (Jan 2025 – May 2026)")
    
    # Sidebar with logout option
    st.sidebar.title("📊 Dashboard Controls")
    
    if st.sidebar.button("🚪 Logout", help="Log out of the dashboard"):
        st.session_state["password_correct"] = False
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Load data
    try:
        df = load_data()

        # Handle flat fee entries - count as 1 hour for analysis
        df['Original_Hours'] = df['Billable Hours'].copy()
        df.loc[df['Rate Type'] == 'Flat Fee', 'Billable Hours'] = 1.0

        st.sidebar.success(f"✅ Loaded {len(df):,} time entries")

        date_min = df['Date of Work'].min().strftime('%b %Y')
        date_max = df['Date of Work'].max().strftime('%b %Y')
        st.sidebar.info(f"📅 Data range: {date_min} – {date_max}")

        flat_fee_count = (df['Rate Type'] == 'Flat Fee').sum()
        if flat_fee_count > 0:
            st.sidebar.info(f"ℹ️ {flat_fee_count:,} flat fee entries counted as 1 hour each")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return
    
    # Filters
    st.sidebar.subheader("🔍 Filters")
    
    # Year filter
    years = sorted(df['Year'].dropna().unique())
    selected_years = st.sidebar.multiselect("Select Years", years, default=years)
    
    # User filter
    users = sorted(df['User Name'].dropna().unique())
    selected_users = st.sidebar.multiselect("Select Users", users, default=[])
    
    # Apply filters
    filtered_df = df[df['Year'].isin(selected_years)]
    if selected_users:
        filtered_df = filtered_df[filtered_df['User Name'].isin(selected_users)]
    
    # Classify tasks
    with st.spinner("🤖 Analyzing matters for AI automation potential..."):
        filtered_df[['Task_Category', 'Automation_Potential']] = filtered_df['Matter Name'].apply(
            lambda x: pd.Series(classify_matter_legalbench(x))
        )
    
    # Calculate automation hours
    filtered_df['Automatable_Hours'] = filtered_df['Billable Hours'] * filtered_df['Automation_Potential']
    filtered_df['Manual_Hours'] = filtered_df['Billable Hours'] - filtered_df['Automatable_Hours']
    
    # Main tabs
    # Check for detailed task-description data
    has_detailed_data = check_for_detailed_data()

    if has_detailed_data:
        st.sidebar.success("✨ Task-level data detected! Check the 'Task-Level Deep Dive' tab.")
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📈 Overview (LegalBench)", 
            "🎯 OLI Benchmark",
            "💰 Cost Savings", 
            "🔮 Predictions",
            "📚 Category Definitions",
            "🔬 Task-Level Deep Dive"
        ])
    else:
        st.sidebar.info("💡 Add `matter_description.csv` to data folder for task-level analysis!")
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Overview (LegalBench)", 
        "🎯 Rimon Benchmark",
        "💰 Cost Savings", 
        "🔮 Predictions",
        "📚 Category Definitions"
    ])
    
    # TAB 1: Overview
    with tab1:
        st.header("Overview Dashboard")
        
        st.markdown("""
        ### 🎯 Understanding AI Automation Potential
        This analysis is based on the **LegalBench framework** adapted for Rimon's matter-based time entries. 
        Each matter type has been assigned an automation potential based on current AI capabilities.
        
        **Note:** *Flat fee entries are counted as 1 hour for analysis purposes. Analysis covers Jan 2025 – May 2026.*
        """)
        
        with st.expander("📊 **How We Calculate Your Automation Potential**", expanded=False):
            st.markdown("""
            #### Calculation Methodology
            
            **Step 1: Matter Classification**
            - We analyze each time entry's "Matter Name"
            - Match matters to one of 16 legal practice area categories
            - Examples: Estate Planning, M&A, Litigation, Corporate Governance, etc.
            
            **Step 2: Apply Automation Potential**
            - Each category has researched automation potential (0%-92%)
            - Based on LegalBench research and current AI capabilities
            - Higher % = more suitable for AI assistance
            
            **Step 3: Calculate Automatable Hours**
            ```
            Automatable Hours = Total Hours × Automation Potential %
            
            Example:
            • Matter Type: Estate Planning (88% automation potential)
            • Time Spent: 100 hours
            • Automatable: 100 × 0.88 = 88 hours
            • Manual Oversight: 12 hours
            ```
            
            #### 🤖 What Makes Hours "Automatable"?
            
            **High Automation (80-92%):**
            - ✅ Estate planning documents (88%)
            - ✅ Intellectual property prosecution (85%)
            - ✅ Regulatory compliance (83%)
            - ✅ Contract review and drafting (92%)
            - ✅ Corporate governance documents (80%)
            
            **Medium Automation (65-80%):**
            - ⚠️ M&A transactions (82%)
            - ⚠️ Employment law (80%)
            - ⚠️ Immigration matters (78%)
            - ⚠️ Tax planning (75%)
            - ⚠️ Real estate (75%)
            
            **Lower Automation (0-70%):**
            - ⛔ Litigation and disputes (75%)
            - ⛔ Family law (68%)
            - ⛔ General advice (65%)
            - ⛔ Internal time (0%)
            """)
        
        st.markdown("---")
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        total_hours = filtered_df['Billable Hours'].sum()
        automatable_hours = filtered_df['Automatable_Hours'].sum()
        automation_rate = (automatable_hours / total_hours * 100) if total_hours > 0 else 0
        
        with col1:
            st.metric(
                label="Total Billable Hours",
                value=f"{total_hours:,.0f}",
                delta=None
            )
        
        with col2:
            st.metric(
                label="AI-Automatable Hours",
                value=f"{automatable_hours:,.0f}",
                delta=f"{automation_rate:.1f}% of total",
                help="Hours that could be accelerated with AI assistance"
            )
        
        with col3:
            total_billable = filtered_df['Billable Amount'].sum()
            st.metric(
                label="Total Billable Amount",
                value=f"${total_billable:,.0f}"
            )
        
        with col4:
            unique_matters = filtered_df['Matter ID'].nunique()
            st.metric(
                label="Unique Matters",
                value=f"{unique_matters:,}"
            )
        
        st.markdown("---")
        
        # Monthly trend visualization
        st.subheader("💰 Monthly Work Distribution: AI-Automatable vs. Human-Required")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            monthly_data = filtered_df.groupby(['Year', 'Month', 'Month_Name']).agg({
                'Billable Hours': 'sum',
                'Automatable_Hours': 'sum',
                'Manual_Hours': 'sum'
            }).reset_index()
            monthly_data = monthly_data.sort_values(['Year', 'Month'])
            monthly_data['Period'] = monthly_data['Month_Name'] + ' ' + monthly_data['Year'].astype(str)
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=monthly_data['Period'],
                y=monthly_data['Automatable_Hours'],
                name='AI-Automatable',
                mode='lines',
                line=dict(width=0.5, color='rgb(34, 139, 34)'),
                stackgroup='one',
                fillcolor='rgba(34, 139, 34, 0.6)',
                hovertemplate='%{y:.0f} automatable hours<extra></extra>'
            ))
            
            fig.add_trace(go.Scatter(
                x=monthly_data['Period'],
                y=monthly_data['Manual_Hours'],
                name='Human-Required',
                mode='lines',
                line=dict(width=0.5, color='rgb(255, 140, 0)'),
                stackgroup='one',
                fillcolor='rgba(255, 140, 0, 0.6)',
                hovertemplate='%{y:.0f} manual hours<extra></extra>'
            ))
            
            fig.update_layout(
                title='Monthly Hours: AI-Automatable vs. Human-Required',
                xaxis_title='Month',
                yaxis_title='Hours',
                height=400,
                hovermode='x unified',
                showlegend=True
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = go.Figure(data=[go.Pie(
                labels=['AI-Automatable Hours', 'Human-Required Hours'],
                values=[automatable_hours, total_hours - automatable_hours],
                hole=0.5,
                marker_colors=['#228B22', '#FF8C00'],
                textinfo='label+percent',
                textposition='outside'
            )])
            
            fig.update_layout(
                title='Overall Work Distribution',
                height=400,
                showlegend=False,
                annotations=[dict(
                    text=f'{automation_rate:.1f}%<br>Automatable',
                    x=0.5, y=0.5,
                    font_size=20,
                    showarrow=False
                )]
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # Top automation opportunities
        st.subheader("📊 Top Automation Opportunities by Practice Area")
        
        category_data = filtered_df[filtered_df['Task_Category'] != 'Internal-Time'].groupby('Task_Category').agg({
            'Billable Hours': 'sum',
            'Automatable_Hours': 'sum',
            'Automation_Potential': 'first'
        }).reset_index()
        category_data = category_data.sort_values('Automatable_Hours', ascending=False).head(12)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                category_data,
                x='Automatable_Hours',
                y='Task_Category',
                orientation='h',
                title='Top 12 Practice Areas by AI-Automatable Hours',
                labels={'Automatable_Hours': 'AI-Automatable Hours', 'Task_Category': 'Practice Area'},
                color='Automation_Potential',
                color_continuous_scale='Greens',
                text='Automatable_Hours'
            )
            
            fig.update_traces(
                texttemplate='%{text:.0f}h',
                textposition='outside'
            )
            
            fig.update_layout(
                height=500,
                yaxis={'categoryorder': 'total ascending'},
                xaxis_title='Hours',
                coloraxis_colorbar=dict(title="Automation<br>Potential")
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            category_data['Potential_Savings_Pct'] = category_data['Automation_Potential'] * 100
            
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                y=category_data['Task_Category'],
                x=category_data['Billable Hours'],
                name='Total Hours',
                orientation='h',
                marker_color='lightblue',
                text=category_data['Billable Hours'].round(0),
                textposition='inside'
            ))
            
            fig.update_layout(
                title='Total Hours by Practice Area<br><sub>Darker green = higher automation potential</sub>',
                xaxis_title='Hours',
                yaxis_title='',
                height=500,
                yaxis={'categoryorder': 'total ascending'},
                showlegend=False
            )
            
            colors = category_data['Automation_Potential'].apply(
                lambda x: f'rgba(34, 139, 34, {x})' if x > 0.8 else 
                         f'rgba(255, 165, 0, {x})' if x > 0.7 else 
                         f'rgba(255, 99, 71, {x})'
            )
            fig.data[0].marker.color = colors
            
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # User analysis
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("👥 Top 15 Users by Hours")
            user_hours = filtered_df.groupby('User Name').agg({
                'Billable Hours': 'sum',
                'Automatable_Hours': 'sum'
            }).reset_index().sort_values('Billable Hours', ascending=False).head(15)
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=user_hours['User Name'],
                x=user_hours['Billable Hours'],
                name='Total Hours',
                orientation='h',
                marker_color='lightcoral'
            ))
            fig.add_trace(go.Bar(
                y=user_hours['User Name'],
                x=user_hours['Automatable_Hours'],
                name='AI-Automatable',
                orientation='h',
                marker_color='darkred'
            ))
            fig.update_layout(
                barmode='overlay',
                height=500,
                hovermode='y unified'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("📈 Top 15 Matters by Hours")
            matter_hours = filtered_df.groupby('Matter Name').agg({
                'Billable Hours': 'sum',
                'Automatable_Hours': 'sum'
            }).reset_index().sort_values('Billable Hours', ascending=False).head(15)
            
            fig = px.bar(
                matter_hours,
                x='Billable Hours',
                y='Matter Name',
                orientation='h',
                title='',
                color='Automatable_Hours',
                color_continuous_scale='Blues'
            )
            fig.update_layout(
                height=500,
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Key insights
        st.markdown("---")
        st.subheader("💡 Key Insights")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info(f"""
            **🤖 AI Could Assist With:**
            - {automatable_hours:,.0f} hours ({automation_rate:.1f}%)
            - Equivalent to {automatable_hours/40:.0f} work weeks
            - Or {automatable_hours/2080:.1f} full-time employees
            """)
        
        with col2:
            avg_automation = filtered_df['Automation_Potential'].mean() * 100
            st.success(f"""
            **📈 Average Matter Automation:**
            - {avg_automation:.1f}% automation potential
            - Based on {len(filtered_df):,} time entries
            - Across {unique_matters:,} matters
            """)
        
        with col3:
            if len(category_data) > 0:
                top_category = category_data.iloc[0]
                st.warning(f"""
                **🎯 Top Opportunity:**
                - **{top_category['Task_Category']}**
                - {top_category['Automatable_Hours']:.0f} automatable hours
                - {top_category['Automation_Potential']*100:.0f}% automation potential
                """)
    
    # TAB 2: Rimon Benchmark
    with tab2:
        st.header("🎯 Rimon Benchmark - Custom Practice Area Analysis")
        
        st.markdown("""
        ### 📊 Rimon's AI Automation Assessment
        This tab uses **Rimon Benchmark** - a custom assessment tailored to Rimon's specific 
        practice areas and matter types.
        
        **Note:** *Flat fee entries are counted as 1 hour for analysis purposes. Analysis covers Jan 2025 – May 2026.*
        """)

        # Classify using Rimon OLI
        with st.spinner("🤖 Analyzing using Rimon Benchmark..."):
            filtered_df[['OLI_Category', 'OLI_Automation_Potential']] = filtered_df['Matter Name'].apply(
                lambda x: pd.Series(classify_matter_oli(x))
            )
        
        filtered_df['OLI_Automatable_Hours'] = filtered_df['Billable Hours'] * filtered_df['OLI_Automation_Potential']
        filtered_df['OLI_Manual_Hours'] = filtered_df['Billable Hours'] - filtered_df['OLI_Automatable_Hours']
        
        with st.expander("📋 **Rimon Benchmark Categories**", expanded=False):
            st.markdown("""
            ### Rimon Benchmark Classification
            
            #### 🟢 100% Automatable (Two Categories)
            
            **1. Routine Corporate & Documents:**
            - General Corporate Matters
            - General Representation
            - Retainer Services
            - Corporate Advice
            
            **2. Estate Planning:**
            - Estate Planning
            - Trust Administration
            - Wills & Probate
            
            #### 🟡 70% Automatable (Two Categories)
            
            **1. Transactional Work:**
            - M&A & Acquisitions
            - Financings & Investments
            - Real Estate Transactions
            - Securities Matters
            
            **2. IP & Regulatory:**
            - Patent & Trademark Prosecution
            - Regulatory Compliance
            - Immigration Matters
            
            #### 🟠 30% Automatable (Two Categories)
            
            **1. Litigation & Complex:**
            - Civil Litigation
            - Arbitration & Mediation
            - Bankruptcy
            
            **2. Employment & Family:**
            - Employment Disputes
            - Family Law Matters
            - Tax Planning
            
            #### ⚫ 0% Automatable
            **Internal & Strategic:**
            - Internal Time
            - Business Development
            - Training
            """)
        
        st.markdown("---")
        
        # Rimon metrics
        st.subheader("📈 Rimon Benchmark Metrics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        oli_total = filtered_df['Billable Hours'].sum()
        oli_automatable = filtered_df['OLI_Automatable_Hours'].sum()
        oli_rate = (oli_automatable / oli_total * 100) if oli_total > 0 else 0
        oli_manual = filtered_df['OLI_Manual_Hours'].sum()
        
        with col1:
            st.metric(
                label="Total Hours",
                value=f"{oli_total:,.0f}"
            )
        
        with col2:
            st.metric(
                label="Rimon AI-Automatable",
                value=f"{oli_automatable:,.0f}",
                delta=f"{oli_rate:.1f}% of total"
            )
        
        with col3:
            st.metric(
                label="Human-Required",
                value=f"{oli_manual:,.0f}",
                delta=f"{(oli_manual/oli_total*100):.1f}%",
                delta_color="inverse"
            )
        
        with col4:
            potential_savings = oli_automatable * 0.60 * 500
            st.metric(
                label="Potential Savings (Est.)",
                value=f"${potential_savings:,.0f}",
                help="At 60% efficiency, $500/hour"
            )
        
        st.markdown("---")
        
        # Rimon visualization
        st.subheader("💰 Rimon Benchmark Distribution")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            oli_monthly = filtered_df.groupby(['Year', 'Month', 'Month_Name']).agg({
                'Billable Hours': 'sum',
                'OLI_Automatable_Hours': 'sum',
                'OLI_Manual_Hours': 'sum'
            }).reset_index()
            oli_monthly = oli_monthly.sort_values(['Year', 'Month'])
            oli_monthly['Period'] = oli_monthly['Month_Name'] + ' ' + oli_monthly['Year'].astype(str)
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=oli_monthly['Period'],
                y=oli_monthly['OLI_Automatable_Hours'],
                name='AI-Automatable',
                mode='lines',
                line=dict(width=0.5, color='rgb(0, 128, 0)'),
                stackgroup='one',
                fillcolor='rgba(0, 128, 0, 0.7)'
            ))
            
            fig.add_trace(go.Scatter(
                x=oli_monthly['Period'],
                y=oli_monthly['OLI_Manual_Hours'],
                name='Human-Required',
                mode='lines',
                line=dict(width=0.5, color='rgb(220, 20, 60)'),
                stackgroup='one',
                fillcolor='rgba(220, 20, 60, 0.7)'
            ))
            
            fig.update_layout(
                title='Rimon Benchmark: Monthly Distribution',
                height=400,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = go.Figure(data=[go.Pie(
                labels=['AI-Automatable', 'Human-Required'],
                values=[oli_automatable, oli_manual],
                hole=0.5,
                marker_colors=['#008000', '#DC143C']
            )])
            
            fig.update_layout(
                title='Overall Distribution',
                height=400,
                annotations=[dict(
                    text=f'{oli_rate:.1f}%<br>Automatable',
                    x=0.5, y=0.5,
                    font_size=20,
                    showarrow=False
                )]
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # Category breakdown
        st.subheader("📊 Hours by Rimon Automation Tier")
        
        oli_categories = filtered_df[filtered_df['OLI_Category'] != 'Unclassified'].groupby('OLI_Category').agg({
            'Billable Hours': 'sum',
            'OLI_Automatable_Hours': 'sum',
            'OLI_Automation_Potential': 'first'
        }).reset_index()
        oli_categories = oli_categories.sort_values('OLI_Automation_Potential', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                y=oli_categories['OLI_Category'],
                x=oli_categories['Billable Hours'],
                name='Total',
                orientation='h',
                marker_color='lightblue'
            ))
            
            fig.add_trace(go.Bar(
                y=oli_categories['OLI_Category'],
                x=oli_categories['OLI_Automatable_Hours'],
                name='Automatable',
                orientation='h',
                marker_color='darkgreen'
            ))
            
            fig.update_layout(
                title='Hours by Rimon Category',
                height=450,
                barmode='overlay'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(
                oli_categories,
                y='OLI_Category',
                x='OLI_Automatable_Hours',
                orientation='h',
                title='Automatable Hours by Tier',
                color='OLI_Automation_Potential',
                color_continuous_scale='RdYlGn'
            )
            
            fig.update_layout(height=450)
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Top matters
        st.markdown("---")
        st.subheader("🎯 Top Matters for AI Implementation")
        
        matter_analysis = filtered_df[filtered_df['OLI_Category'] != 'Unclassified'].groupby('Matter Name').agg({
            'Billable Hours': 'sum',
            'OLI_Automatable_Hours': 'sum'
        }).reset_index()
        matter_analysis['Automation_Rate'] = (
            matter_analysis['OLI_Automatable_Hours'] / matter_analysis['Billable Hours'] * 100
        )
        matter_analysis = matter_analysis.sort_values('OLI_Automatable_Hours', ascending=False).head(20)
        
        st.dataframe(
            matter_analysis.style.format({
                'Billable Hours': '{:.1f}',
                'OLI_Automatable_Hours': '{:.1f}',
                'Automation_Rate': '{:.1f}%'
            }).background_gradient(subset=['OLI_Automatable_Hours'], cmap='Greens'),
            use_container_width=True,
            height=500
        )
    
    # TAB 3: Cost Savings
    with tab3:
        st.header("💰 Potential Cost Savings with AI")
        
        st.subheader("⚙️ Assumptions & Parameters")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_hourly_rate = st.number_input(
                "Average Hourly Rate ($)",
                min_value=100,
                max_value=1000,
                value=500,
                step=50
            )
        
        with col2:
            ai_efficiency_gain = st.slider(
                "AI Efficiency Gain (%)",
                min_value=10,
                max_value=90,
                value=60,
                help="Percentage of time saved on automatable tasks"
            ) / 100
        
        with col3:
            ai_cost_per_hour = st.number_input(
                "AI Cost per Hour ($)",
                min_value=1,
                max_value=100,
                value=10,
                step=5
            )
        
        st.markdown("---")
        
        # Calculate savings
        hours_saved = automatable_hours * ai_efficiency_gain
        labor_saved = hours_saved * avg_hourly_rate
        ai_cost = automatable_hours * ai_cost_per_hour
        net_savings = labor_saved - ai_cost
        roi = (net_savings / ai_cost * 100) if ai_cost > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="Hours Potentially Saved",
                value=f"{hours_saved:,.0f}",
                delta=f"{(hours_saved/total_hours*100):.1f}% of total"
            )
        
        with col2:
            st.metric(
                label="Labor Cost Savings",
                value=f"${labor_saved:,.0f}"
            )
        
        with col3:
            st.metric(
                label="AI Implementation Cost",
                value=f"${ai_cost:,.0f}"
            )
        
        with col4:
            st.metric(
                label="Net Savings",
                value=f"${net_savings:,.0f}",
                delta=f"ROI: {roi:.0f}%"
            )
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("💵 Savings by Practice Area")
            
            category_savings = filtered_df.groupby('Task_Category').agg({
                'Automatable_Hours': 'sum'
            }).reset_index()
            
            category_savings['Hours_Saved'] = category_savings['Automatable_Hours'] * ai_efficiency_gain
            category_savings['Cost_Savings'] = category_savings['Hours_Saved'] * avg_hourly_rate
            category_savings = category_savings.sort_values('Cost_Savings', ascending=False).head(12)
            
            fig = px.bar(
                category_savings,
                x='Task_Category',
                y='Cost_Savings',
                title='Potential Savings by Category',
                color='Cost_Savings',
                color_continuous_scale='Greens'
            )
            fig.update_layout(height=400, xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("📈 Cumulative Savings")
            
            monthly_savings = filtered_df.groupby(['Year', 'Month']).agg({
                'Automatable_Hours': 'sum'
            }).reset_index()
            monthly_savings = monthly_savings.sort_values(['Year', 'Month'])
            monthly_savings['Hours_Saved'] = monthly_savings['Automatable_Hours'] * ai_efficiency_gain
            monthly_savings['Monthly_Savings'] = monthly_savings['Hours_Saved'] * avg_hourly_rate
            monthly_savings['Cumulative_Savings'] = monthly_savings['Monthly_Savings'].cumsum()
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=monthly_savings.index,
                y=monthly_savings['Cumulative_Savings'],
                mode='lines+markers',
                name='Cumulative',
                fill='tozeroy',
                line=dict(color='green', width=3)
            ))
            fig.update_layout(
                title='Cumulative Cost Savings (Jan 2025 – May 2026)',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # TAB 4: Predictions
    with tab4:
        # Dynamically select the most recent year that has partial data.
        # Cap at today so future-dated flat fees don't push latest_month to 12.
        today = pd.Timestamp.today()
        all_years = sorted(filtered_df['Year'].dropna().unique().astype(int))
        projection_year = int(max(all_years)) if all_years else today.year

        st.header(f"🔮 {projection_year} Full Year Projections")

        current_data = filtered_df[
            (filtered_df['Year'] == projection_year) &
            (filtered_df['Date of Work'] <= today)
        ]

        if len(current_data) > 0:
            latest_month = current_data['Month'].max()
            
            monthly_avg = current_data.groupby('Month').agg({
                'Billable Hours': 'sum',
                'Automatable_Hours': 'sum'
            }).mean()
            
            months_elapsed = latest_month
            months_remaining = 12 - months_elapsed
            
            projected_total = (current_data['Billable Hours'].sum() + 
                              monthly_avg['Billable Hours'] * months_remaining)
            projected_automatable = (current_data['Automatable_Hours'].sum() + 
                                    monthly_avg['Automatable_Hours'] * months_remaining)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    label="Projected Total Hours (2025)",
                    value=f"{projected_total:,.0f}",
                    delta=f"+{months_remaining} months projected"
                )
            
            with col2:
                st.metric(
                    label="Projected Automatable Hours",
                    value=f"{projected_automatable:,.0f}",
                    delta=f"{(projected_automatable/projected_total*100):.1f}%"
                )
            
            with col3:
                projected_savings = projected_automatable * ai_efficiency_gain * avg_hourly_rate
                st.metric(
                    label="Projected Annual Savings",
                    value=f"${projected_savings:,.0f}"
                )
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Monthly Projection")
                
                actual_monthly = current_data.groupby('Month').agg({
                    'Billable Hours': 'sum',
                    'Automatable_Hours': 'sum'
                }).reset_index()
                
                all_months = pd.DataFrame({'Month': range(1, 13)})
                projection_df = all_months.merge(actual_monthly, on='Month', how='left')
                
                projection_df['Billable Hours'] = projection_df['Billable Hours'].fillna(monthly_avg['Billable Hours'])
                projection_df['Automatable_Hours'] = projection_df['Automatable_Hours'].fillna(
                    monthly_avg['Automatable_Hours']
                )
                projection_df['Type'] = projection_df['Month'].apply(
                    lambda x: 'Actual' if x <= months_elapsed else 'Projected'
                )
                
                fig = go.Figure()
                
                actual = projection_df[projection_df['Type'] == 'Actual']
                fig.add_trace(go.Bar(
                    x=actual['Month'],
                    y=actual['Billable Hours'],
                    name='Actual Total',
                    marker_color='lightblue'
                ))
                fig.add_trace(go.Bar(
                    x=actual['Month'],
                    y=actual['Automatable_Hours'],
                    name='Actual Automatable',
                    marker_color='darkblue'
                ))
                
                projected = projection_df[projection_df['Type'] == 'Projected']
                fig.add_trace(go.Bar(
                    x=projected['Month'],
                    y=projected['Billable Hours'],
                    name='Projected Total',
                    marker_color='lightcoral',
                    opacity=0.6
                ))
                fig.add_trace(go.Bar(
                    x=projected['Month'],
                    y=projected['Automatable_Hours'],
                    name='Projected Automatable',
                    marker_color='darkred',
                    opacity=0.6
                ))
                
                fig.update_layout(
                    title=f'{projection_year} Monthly Hours Projection',
                    barmode='group',
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("💰 Cumulative Savings Projection")
                
                projection_df['Monthly_Savings'] = (
                    projection_df['Automatable_Hours'] * ai_efficiency_gain * avg_hourly_rate
                )
                projection_df['Cumulative_Savings'] = projection_df['Monthly_Savings'].cumsum()
                
                fig = go.Figure()
                
                actual_cum = projection_df[projection_df['Type'] == 'Actual']
                fig.add_trace(go.Scatter(
                    x=actual_cum['Month'],
                    y=actual_cum['Cumulative_Savings'],
                    mode='lines+markers',
                    name='Actual',
                    line=dict(color='green', width=3),
                    fill='tozeroy'
                ))
                
                fig.add_trace(go.Scatter(
                    x=projection_df['Month'],
                    y=projection_df['Cumulative_Savings'],
                    mode='lines+markers',
                    name='Projected',
                    line=dict(color='lightgreen', width=3, dash='dash'),
                    fill='tozeroy',
                    opacity=0.5
                ))
                
                fig.update_layout(
                    title='Cumulative Savings Projection',
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Scenario analysis
            st.markdown("---")
            st.subheader("🎲 Scenario Analysis")
            
            scenarios = {
                'Conservative (40% efficiency)': 0.40,
                'Moderate (60% efficiency)': 0.60,
                'Optimistic (80% efficiency)': 0.80
            }
            
            scenario_results = []
            for name, efficiency in scenarios.items():
                h_saved = projected_automatable * efficiency
                cost_saved = h_saved * avg_hourly_rate
                ai_cost_total = projected_automatable * ai_cost_per_hour
                net = cost_saved - ai_cost_total
                
                scenario_results.append({
                    'Scenario': name,
                    'Hours Saved': h_saved,
                    'Cost Saved': cost_saved,
                    'AI Cost': ai_cost_total,
                    'Net Savings': net,
                    'ROI (%)': (net / ai_cost_total * 100) if ai_cost_total > 0 else 0
                })
            
            scenario_df = pd.DataFrame(scenario_results)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=scenario_df['Scenario'],
                    y=scenario_df['Net Savings'],
                    marker_color='green',
                    text=scenario_df['Net Savings'].apply(lambda x: f'${x:,.0f}'),
                    textposition='auto'
                ))
                
                fig.update_layout(
                    title='Net Savings by Scenario',
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.dataframe(
                    scenario_df.style.format({
                        'Hours Saved': '{:,.0f}',
                        'Cost Saved': '${:,.0f}',
                        'AI Cost': '${:,.0f}',
                        'Net Savings': '${:,.0f}',
                        'ROI (%)': '{:.0f}%'
                    }),
                    use_container_width=True,
                    height=400
                )
        else:
            st.warning(f"No {projection_year} data available for projections.")
    
    # TAB 5: Definitions
    with tab5:
        st.header("📚 LegalBench Practice Area Definitions")
        
        st.markdown("""
        Based on the **LegalBench framework** adapted for Rimon's matter-based time tracking.
        """)
        
        for category, info in LEGALBENCH_TASKS.items():
            if category == 'Internal-Time':
                continue
            
            with st.expander(f"**{category}** - Automation: {info['automation_potential']*100:.0f}%"):
                st.markdown(f"**Description:** {info['description']}")
                
                st.markdown("**Keywords:**")
                st.write(", ".join(info['keywords']))
                
                st.markdown("**Examples:**")
                for example in info['examples']:
                    st.write(f"• {example}")
                
                matching = filtered_df[
                    filtered_df['Task_Category'] == category
                ]['Matter Name'].value_counts().head(5)
                
                if len(matching) > 0:
                    st.markdown("**Top 5 Matters in Your Data:**")
                    for matter, count in matching.items():
                        st.write(f"• {matter} ({count} entries)")
        
        st.markdown("---")
        st.info("""
        **Note:** Automation potentials are estimates based on current AI capabilities 
        and the LegalBench framework. Actual results depend on implementation and oversight.
        """)


    
    # ========================================================================
    # TAB 6: TASK-LEVEL DEEP DIVE (conditional)
    # ========================================================================
    if has_detailed_data:
        with tab6:
            st.header("🔬 Task-Level Deep Dive: Oct 2025 – May 2026")

            st.markdown("""
            ### 🎯 Ultra-Precise Automation Analysis (Task Description Data)

            This tab uses **actual task descriptions** for much more accurate automation scoring
            than the matter-name keyword matching used in the other tabs.

            **Examples from your data:**
            - "Email regarding status" → 92% automatable
            - "Review and analyze agreement" → 85% automatable
            - "Telephone conference with client" → 45% automatable
            - "Negotiate settlement" → 25% automatable
            """)

            st.info("""
            💡 **What This Tab Shows:**

            Task-level data covers **Oct 2025 – May 2026** (Oct 2025 from the matter_description.csv
            export; Nov 2025 – May 2026 from the Activities Excel export). This data is a subset of
            what is shown in the main tabs.

            This tab demonstrates:
            - How much MORE PRECISE we can be with detailed task descriptions
            - What automation looks like at the task level vs matter level
            """)
            
            # Load detailed data
            with st.spinner("🔬 Loading task-level detail data..."):
                detailed_df = load_detailed_data()
            
            if detailed_df is not None and len(detailed_df) > 0:
                # Classify tasks
                st.info(f"📊 Analyzing {len(detailed_df):,} detailed task entries...")
                detailed_df[['Task_Type', 'Task_Automation']] = detailed_df['Description'].apply(
                    lambda x: pd.Series(classify_task_description(x))
                )
                
                # Calculate automatable hours
                detailed_df['Task_Automatable_Hours'] = detailed_df['Hours'] * detailed_df['Task_Automation']
                detailed_df['Task_Manual_Hours'] = detailed_df['Hours'] - detailed_df['Task_Automatable_Hours']
                
                # Key metrics
                st.markdown("---")
                st.subheader("📊 Task-Level Metrics")
                
                col1, col2, col3, col4 = st.columns(4)
                
                task_total = detailed_df['Hours'].sum()
                task_auto = detailed_df['Task_Automatable_Hours'].sum()
                task_rate = (task_auto / task_total * 100) if task_total > 0 else 0
                
                with col1:
                    st.metric(
                        label="Total Hours Analyzed",
                        value=f"{task_total:,.0f}",
                        help="From detailed task descriptions"
                    )
                
                with col2:
                    st.metric(
                        label="AI-Automatable (Task-Level)",
                        value=f"{task_auto:,.0f}",
                        delta=f"{task_rate:.1f}%",
                        help="Based on specific task descriptions"
                    )
                
                with col3:
                    avg_task_auto = detailed_df['Task_Automation'].mean() * 100
                    st.metric(
                        label="Avg Task Automation",
                        value=f"{avg_task_auto:.1f}%",
                        help="Average automation potential per task"
                    )
                
                with col4:
                    unique_tasks = detailed_df['Task_Type'].nunique()
                    st.metric(
                        label="Unique Task Types",
                        value=f"{unique_tasks}"
                    )
                
                st.markdown("---")
                
                # Task type breakdown
                st.subheader("🎯 Automation by Task Type")
                
                task_breakdown = detailed_df.groupby('Task_Type').agg({
                    'Hours': 'sum',
                    'Task_Automatable_Hours': 'sum',
                    'Task_Automation': 'first'
                }).reset_index()
                task_breakdown = task_breakdown.sort_values('Task_Automatable_Hours', ascending=False)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    fig = px.bar(
                        task_breakdown.head(12),
                        x='Task_Automatable_Hours',
                        y='Task_Type',
                        orientation='h',
                        title='Top 12 Task Types by Automatable Hours',
                        color='Task_Automation',
                        color_continuous_scale='RdYlGn',
                        text='Task_Automatable_Hours'
                    )
                    fig.update_traces(texttemplate='%{text:.0f}h', textposition='outside')
                    fig.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        y=task_breakdown.head(12)['Task_Type'],
                        x=task_breakdown.head(12)['Hours'],
                        name='Total Hours',
                        orientation='h',
                        marker_color='lightblue'
                    ))
                    fig.add_trace(go.Bar(
                        y=task_breakdown.head(12)['Task_Type'],
                        x=task_breakdown.head(12)['Task_Automatable_Hours'],
                        name='Automatable',
                        orientation='h',
                        marker_color='darkgreen'
                    ))
                    fig.update_layout(
                        title='Total vs Automatable Hours',
                        height=500,
                        barmode='overlay',
                        yaxis={'categoryorder': 'total ascending'}
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("---")
                
                # Sample tasks
                st.subheader("📝 Sample Task Classifications")
                
                sample_tasks = []
                for task_type in task_breakdown.head(10)['Task_Type']:
                    sample = detailed_df[detailed_df['Task_Type'] == task_type].head(2)
                    sample_tasks.append(sample)
                
                if sample_tasks:
                    sample_df = pd.concat(sample_tasks)
                    display_cols = ['Description', 'Task_Type', 'Task_Automation', 'Hours']
                    
                    st.dataframe(
                        sample_df[display_cols].style.format({
                            'Task_Automation': '{:.0%}',
                            'Hours': '{:.2f}'
                        }),
                        use_container_width=True,
                        height=400
                    )
                
                st.markdown("---")
                
                # Comparison
                st.subheader("📊 Task-Level vs Matter-Level Comparison")
                
                st.warning("""
                **⚠️ Important:** The task-level data (this tab) is a subset of the full dataset:
                - Task-Level (this tab): analyzed using detailed free-text task descriptions
                - Matter-Level (main tabs): entire date range analyzed by matter names only
                - Task-level data covers Oct 2025 – May 2026 and is included in the main tab totals
                """)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    task_date_min = detailed_df['Date'].min().strftime('%b %Y')
                    task_date_max = detailed_df['Date'].max().strftime('%b %Y')
                    st.success(f"""
                    **🔬 Task-Level ({task_date_min} – {task_date_max}):**
                    - Entries: {len(detailed_df):,}
                    - Automatable: {task_auto:,.0f} hours
                    - Rate: {task_rate:.1f}%
                    - Precision: HIGH (task descriptions)
                    """)
                
                with col2:
                    # Compare against same date range in main dataset
                    overlap_df = filtered_df[
                        (filtered_df['Date of Work'] >= detailed_df['Date'].min()) &
                        (filtered_df['Date of Work'] <= detailed_df['Date'].max())
                    ]
                    overlap_auto = overlap_df['Automatable_Hours'].sum() if len(overlap_df) > 0 else 0
                    overlap_total = overlap_df['Billable Hours'].sum() if len(overlap_df) > 0 else 0
                    overlap_rate = (overlap_auto / overlap_total * 100) if overlap_total > 0 else 0

                    st.info(f"""
                    **📊 Matter-Level (same date range):**
                    - Entries: {len(overlap_df):,}
                    - Automatable: {overlap_auto:,.0f} hours
                    - Rate: {overlap_rate:.1f}%
                    - Precision: MEDIUM (matter names)
                    """)
                
                difference = abs(task_rate - overlap_rate)
                if task_rate > overlap_rate:
                    st.warning(f"⚡ Task-level analysis shows {difference:.1f} percentage points MORE automation potential than matter-level!")
                else:
                    st.info(f"📉 Task-level analysis shows {difference:.1f} percentage points LESS automation potential than matter-level (more conservative).")
                
                # Top opportunities
                st.markdown("---")
                st.subheader("🎯 Top Automation Opportunities (Task-Level)")
                
                high_auto_tasks = detailed_df[detailed_df['Task_Automation'] >= 0.85].groupby('Description').agg({
                    'Hours': 'sum',
                    'Task_Automation': 'first'
                }).reset_index().sort_values('Hours', ascending=False).head(20)
                
                if len(high_auto_tasks) > 0:
                    st.write(f"**{len(high_auto_tasks)} high-automation tasks (≥85%) with most hours:**")
                    st.dataframe(
                        high_auto_tasks.style.format({
                            'Task_Automation': '{:.0%}',
                            'Hours': '{:.1f}'
                        }),
                        use_container_width=True,
                        height=400
                    )
                else:
                    st.info("No high-automation tasks found in this dataset.")
            
            else:
                st.error("❌ Could not load detailed CSV data.")


if __name__ == "__main__":
    main()

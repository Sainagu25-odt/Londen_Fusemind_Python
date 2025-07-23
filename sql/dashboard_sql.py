
# sql/dashboard.py

GET_POLICY_HOLDERS = """
    SELECT COUNT(*) AS policy_holders
    FROM responder_file
    WHERE TRIM(COALESCE(cust_flag, '')) = 'Y'
"""

GET_NON_INSURANCE = """
    SELECT COUNT(*) AS non_insurance
    FROM responder_file
    WHERE TRIM(COALESCE(cust_flag, '')) <> 'Y'
"""

GET_TOTAL_RESPONDERS = """
    SELECT COUNT(*) AS total_responders
    FROM responder_file
"""

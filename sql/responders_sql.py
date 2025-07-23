
GET_RESPONDER_ID = """
SELECT id FROM import_logs 
WHERE filename = :filename 
ORDER BY downloaded_at DESC 
LIMIT 1
"""

INSERT_LOGS = """
INSERT INTO import_logs (filename, processed, downloaded_at)
VALUES (:filename, :processed, :downloaded_at)
"""

UPDATE_LOGS = """
UPDATE import_logs
SET records = :records,
    imported_at = :imported_at
WHERE id = :id
"""

INSERT_RESPONDER_FILE = """
INSERT INTO responder_file (
    responder_id, title, first_name, middle_name, last_name,
    suffix, address_1, address_2, bad_address, city, state,
    province, postal, country, county, dob, age, gender, ssn,
    no_call, no_mail, supress, cust_flag
)
SELECT 
  CASE
    WHEN TRIM(responder_id) ~ '^\d+$' THEN TRIM(responder_id)::numeric
    ELSE NULL
  END AS responder_id,
  title, first_name, middle_name, last_name, suffix,
  address_1, address_2, bad_address, city, state, province, postal,
  country, county, dob, NULLIF(TRIM(age), '')::numeric,
  gender, NULLIF(TRIM(ssn), '')::numeric, no_call, no_mail, supress,
  cust_flag
FROM import_responder
ON CONFLICT (responder_id) DO NOTHING
"""

INSERT_RESPONSES = """
INSERT INTO responses (responder_id, title, first_name, middle_name, last_name,
suffix,address_1, address_2, bad_address, city, state, province, postal,
country, county, dob, age,gender, ssn, no_call, no_mail, supress,
cust_flag, received_time, campaign, media_type, form, dma, market, tv_station, tv_date, tv_time, acct_flag,
drrsp_leads, direct_agency,credit_rtn, credit_dte, credit_rsn, vendor_code, owning_fil,owning_dco, owning_agt,
lock_flag, fortdox_id)
SELECT
  CASE
    WHEN TRIM(responder_id) ~ '^\d+$' THEN TRIM(responder_id)::numeric
    ELSE NULL
  END AS responder_id,
  title, first_name, middle_name, last_name, suffix,
            address_1, address_2, bad_address, city, state, province, postal,
			country, county, dob, NULLIF(TRIM(age), '')::numeric,
			gender, NULLIF(TRIM(ssn), '')::numeric, no_call, no_mail, supress,
			cust_flag, received_time, campaign,media_type, form, NULLIF(TRIM(dma),'')::numeric, market,
			tv_station, tv_date, tv_time, acct_flag, drrsp_leads, direct_agency,
            credit_rtn, credit_dte, credit_rsn, vendor_code, NULLIF(TRIM(owning_fil), '')::numeric,
			NULLIF(TRIM(owning_dco), '')::numeric,
    NULLIF(TRIM(owning_agt), '')::numeric, lock_flag, fortdox_id
FROM import_responder
"""
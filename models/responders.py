import csv
import os
import zipfile
from pathlib import Path

import paramiko
import yaml
from sqlalchemy import text
from datetime import datetime
from extensions import db
import re
import sql.responders_sql as q




def load_ftp_credentials():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    yml_path = os.path.join(base_dir, "config.yml")
    with open(yml_path) as f:
        creds = yaml.safe_load(f)
    return creds["ftp"]


def get_sftp_client(config):
    transport = paramiko.Transport((config['hostname'], config['port']))
    transport.connect(username=config['username'], password=config['password'])
    sftp = paramiko.SFTPClient.from_transport(transport)
    return sftp


def parse_responder_yaml():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    yml_path = os.path.join(base_dir, "responders.yml")
    with open(yml_path, 'r') as f:
        data = yaml.safe_load(f)
    columns = data['responder']
    col_defs = []
    col_names = []
    for key, val in columns.items():
        name = val['name']
        dtype = "VARCHAR" if val['type'] == 'A' else "VARCHAR"  # Simplified
        size = val['size']
        col_defs.append(f"{name} {dtype}({size})")
        col_names.append(name)
    return col_defs, col_names

def import_csv_to_db(csv_path, column_names):
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        row_count = 0
        for row in reader:
            row_count += 1
            print(f"Reading row {row_count}: {row}")

            line = row[0]
            parsed = next(csv.reader([line]))  # Unpack the quoted comma values
            print(f"Parsed row {row_count}: {parsed}")

            if len(parsed) < len(column_names):
                print(f"Skipping row {row_count}: Not enough values")
                continue

            values = parsed[:len(column_names)]
            print(f"Mapped values for row {row_count}: {values}")

            placeholders = ','.join([f":{i}" for i in range(len(column_names))])

            insert_sql = f"""
                            INSERT INTO import_responder ({','.join(column_names)})
                            VALUES ({placeholders})
                        """
            params = {str(i): val for i, val in enumerate(values)}

            print(f"Executing SQL for row {row_count}: {insert_sql}")
            print(f"With parameters: {params}")
            db.session.execute(text(insert_sql), params)
    db.session.commit()
    print(f"Inserted {row_count} rows successfully.")


def create_import_table(col_defs):
    create_sql = f"""
    CREATE TABLE import_responder (
        {', '.join(col_defs)}
    )
    """
    db.session.execute(text(create_sql))
    db.session.commit()

def execute_responder_task(base_dir, debug=False):
    ftp_config = load_ftp_credentials()
    remote_dir = ftp_config["remote_dir"]

    tmp_dir = os.path.join(base_dir, 'tmp')
    archive_base = os.path.join(base_dir, 'archive')
    os.makedirs(tmp_dir, exist_ok=True)


    current_month = datetime.now().strftime('%Y%m')
    archive_dir = os.path.join(archive_base, current_month)
    os.makedirs(archive_dir, exist_ok=True)

    sftp = get_sftp_client(ftp_config)

    archived_files = set(f for f in os.listdir(os.path.join(archive_base)) if f.startswith("Responders.zip"))
    for filename in sftp.listdir(remote_dir):
        if re.match(r'^Responders\.zip.*', filename) and filename not in archived_files:
            remote_file = f"{remote_dir}/{filename}"
            local_tmp_path = os.path.join(tmp_dir, filename)
            local_archive_path = os.path.join(archive_dir, filename)

            if debug:
                print(f"Downloading: {filename}")

            sftp.get(remote_file, local_tmp_path)

            if os.path.exists(local_archive_path):
                os.remove(local_archive_path)
            Path(local_tmp_path).rename(local_archive_path)

            with zipfile.ZipFile(local_archive_path, 'r') as zip_ref:
                zip_ref.extractall(tmp_dir)

            extracted_file = next((f for f in os.listdir(tmp_dir) if f.endswith('.csv')), None)
            print(extracted_file)

            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', extracted_file)

            if not date_match:
                raise Exception("Date not found in file name.")

            file_date = date_match.group(1)
            zip_filename_for_log = f"Responders.zip{file_date}"


            db.session.execute(text("DROP TABLE IF EXISTS import_responder"))
            column_defs, column_names = parse_responder_yaml()

            create_import_table(column_defs)


            csv_path = os.path.join(tmp_dir, extracted_file)
            import_csv_to_db(csv_path, column_names)

            log_id = db.session.execute(text(q.GET_RESPONDER_ID), {"filename": zip_filename_for_log}).scalar()
            if log_id is None:
                now = datetime.now().replace(microsecond=0)
                db.session.execute(text(q.INSERT_LOGS), {
                    "filename": zip_filename_for_log,
                    "processed": True,
                    "downloaded_at": now
                })
                db.session.commit()
                log_id = db.session.execute(text(q.GET_RESPONDER_ID), {"filename": zip_filename_for_log}).scalar()

            records = db.session.execute(text("SELECT count(*) FROM import_responder")).scalar()
            print(records)

            db.session.execute(text(q.UPDATE_LOGS), {
                "records": records,
                "imported_at": datetime.now().replace(microsecond=0),
                "id": log_id
            })

            db.session.execute(text("DELETE FROM responses"))
            db.session.execute(text("ALTER SEQUENCE responders_id_seq RESTART WITH 1"))
            db.session.execute(text("DELETE FROM responder_file"))

            cols = ','.join(column_names)

            print("INSERTING RESPONSES...")
            db.session.execute(text(q.INSERT_RESPONSES))
            print("completed inserting responses..")

            print("Inserting responder_file...")
            db.session.execute(text(q.INSERT_RESPONDER_FILE))
            print("completed inserting records into responder_file...")

            db.session.execute(text("CLUSTER responder_file"))
            db.session.execute(text("ANALYZE responder_file"))
            db.session.execute(text("CLUSTER responses"))
            db.session.execute(text("ANALYZE responses"))

            db.session.commit()



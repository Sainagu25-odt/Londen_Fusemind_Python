import os
import yaml


def get_criteria_options(root_path: str):
    yaml_path = os.path.join(root_path, 'data', 'campaign_dropdown.yaml')
    with open(yaml_path, 'r') as f:
        yaml_data = yaml.safe_load(f)

    sql_types_set = set()
    column_names_set = set()

    for _, criterion in yaml_data.get("CampaignCriterion", {}).items():
        if isinstance(criterion, dict):
            if 'sql_type' in criterion:
                sql_types_set.add(criterion['sql_type'])
            if 'column_name' in criterion:
                column_names_set.add(criterion['column_name'])

    return {
        "sql_types": sorted(sql_types_set),
        "column_names": sorted(column_names_set)
    }




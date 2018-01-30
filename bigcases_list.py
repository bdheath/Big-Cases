import json

case_file = open('./bigcases.json')
case_data = json.load(case_file)

cases_sct = case_data["supreme_court_cases"]
cases = case_data["cases"]
import random
import json
from datetime import datetime, timedelta

# Helper function to generate random date
def generate_date():
    start_date = datetime(2023, 1, 1)
    days = random.randint(0, 365)
    date = start_date + timedelta(days=days)
    return int(date.strftime('%Y%m%d'))

# Load the JSON data from a file
def load_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

# Save the updated JSON data to a file
def save_json(data, file_path):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

def update_data_with_random_info(data):
    # Regions to choose from
    regions = [1, 2, 3, 4, 5]  # 5 different regions

    # Update nodes (add random region)
    for node in data['nodes']:
        if node['type'] == "Personne":
            node['region'] = random.choice(regions)
        else:
            roles = ["regulatory", "financial","cyber","regulatory","corruption","fraud"]
            node['categorie'] = random.choice(roles)

    # Update edges
    for edge in data['edges']:
        if edge['type'] == 'contact':
            edge['nb-fois'] = random.randint(1, 10)
            edge['date'] = generate_date()
        elif edge['type'] == 'impliquer':
            edge['date'] = generate_date()
            roles = ["suspect", "witness"]
            edge['role'] = random.choice(roles)

    return data

# Function to read and update the JSON data
def process_json_file(input_file, output_file):
    data = load_json(input_file)
    updated_data = update_data_with_random_info(data)
    save_json(updated_data, output_file)

# Example usage:
process_json_file("D:/stage/project_name/graphapi/aggregation/gg.json", "updated_output_file.json")

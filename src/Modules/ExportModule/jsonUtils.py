import json
import os

def export_data_to_file(data, output_path):
    with open(output_path, "w") as file:
        json.dump(data, file)
        print("Arquivo salvo")
        
    file.close()

def import_data_from_file(file_path):
    data = {}
    
    folder_path = os.path.dirname(file_path)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        
    if not os.path.exists(file_path):
        with open(file_path, "w") as file:
            json.dump(data, file)
            
    with open(file_path, "r") as file:
        data = json.load(file)
    
    file.close()
    
    return data
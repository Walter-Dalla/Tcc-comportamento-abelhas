import json

def export_data_to_file(data, output_path):
    with open(output_path, "w") as file:
        json.dump(data, file)
        print("Arquivo salvo")
        
    file.close()

def import_data_from_file(file_path):
    data = {}
    with open(file_path, "r") as file:
        data = json.load(file)
    
    file.close()
    
    return data
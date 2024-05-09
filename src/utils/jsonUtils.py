import json

def exportDataToFile(data, output_path):
    with open(output_path, "w") as file:
        json.dump(data, file)
        print("Arquivo salvo")

def importDataFromFile(file_path):
    with open(file_path, "r") as file:
        return json.load(file)
    
    return {}
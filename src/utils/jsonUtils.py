import json

def exportDataToFile(data, output_path):
    with open(output_path, "w") as file:
        json.dump(data, file)
        print("Arquivo salvo")
        
    file.close()

def importDataFromFile(file_path):
    data = {}
    with open(file_path, "r") as file:
        data = json.load(file)
    
    file.close()
    
    return data
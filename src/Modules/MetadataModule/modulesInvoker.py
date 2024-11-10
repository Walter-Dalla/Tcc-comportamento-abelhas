import os
import importlib.util

from src.Modules.ExportModule.jsonUtils import export_data_to_file, import_data_from_file

def load_module(module_name, module_path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def execute_metadata_module_calls(selected_config):
    metadata_module_path = "./src/Modules/MetadataModule"
    
    data_location = "./cache/outputs/"+selected_config+".json"
    data = import_data_from_file(data_location)
    
    for filename in os.listdir(metadata_module_path):
        if filename.endswith(".py"):
            module_name = filename[:-3]
            module_path = os.path.join(metadata_module_path, filename)
            module = load_module(module_name, module_path)
            if hasattr(module, 'module_call'):
                data = module.module_call(data)
    
    export_data_to_file(data, data_location)
    
    return data
    
                
    
import os
import importlib.util

def load_module(module_name, module_path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def execute_module_calls(data):
    directory_path = "./src/Modules/MetadataModule"
    
    for filename in os.listdir(directory_path):
        if filename.endswith(".py"):
            module_name = filename[:-3]
            module_path = os.path.join(directory_path, filename)
            module = load_module(module_name, module_path)
            if hasattr(module, 'module_call'):
                data = module.module_call(data)
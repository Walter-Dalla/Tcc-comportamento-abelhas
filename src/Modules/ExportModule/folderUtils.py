import os

def assert_dir_exists(file_path):
    data = {}
    
    folder_path = os.path.dirname(file_path)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        
    return data
def module_call(data):
    data["time_border_x"] = 0
    data["time_border_y"] = 0
    data["time_border_z"] = 0
        
        
    for index in data["route"]:
        value = data["route"][index]
        
        constante = 100
        
        border_min_x = constante
        border_max_x = constante
        border_min_y = constante
        border_max_y = constante
        border_min_z = constante
        border_max_z = constante
        
        x = value['x']
        y = value['y']
        z = value['z']
        
        point = [value['x'], value['y'], value['z']]
        isOutsideBorder = False
        
        if(x < border_min_x or x < border_max_x):
            data["time_border_x"] += 1
        
        if(y < border_min_y or y < border_max_y):
            data["time_border_y"] += 1
            
        if(z < border_min_z or z < border_max_z):
            data["time_border_z"] += 1
        
        return data
import math

def module_call(data):
    previusPoint = None
    
    fps = data["fps"]
    pixel_to_cm_ratio = float(data["pixel_to_cm_ratio"])
    
    distance = 0
    speed = []
    for index in data["route"]:
        value = data["route"][index]
        
        point = [value['x'], value['y'], value['z']]
        
        if(previusPoint == None):
            previusPoint = point
            continue
        
        distance += math.dist(previusPoint, point) * pixel_to_cm_ratio/100
        
        if(int(index) % fps == 0):
            speed.append(distance/pixel_to_cm_ratio)
            distance = 0
    
    data["speed"] = speed
    
    return speed


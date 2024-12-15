import math

def module_call(data):
    previusPoint = None
    pixel_to_cm_ratio = float(data["pixel_to_cm_ratio"])
    
    distanceTotal = 0
    speedTotal = 0
    speedObj = {}
    
    for index in data["route"]:
        routePoint = data["route"][index]
        point = route_point_to_math_point(routePoint)
        
        if(index == '0'):
            previusPoint = point
            continue
        
        distance = math.dist(previusPoint, point) * pixel_to_cm_ratio/100
        
        speed = distance/pixel_to_cm_ratio
        speedObj[index] = speed
        speedTotal += speed
        distanceTotal += distance
        
        previusPoint = point
        
    data["speed"] = speedObj
    data["averageSpeed"] = speedTotal / len(data["route"])
    data["distanceTotal"] = distanceTotal
    
    return data

def route_point_to_math_point(routePoint):
    return [routePoint['x'], routePoint['y'], routePoint['z']]


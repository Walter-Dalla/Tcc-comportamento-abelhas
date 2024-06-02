import math

def calculateSpeed(data, toCentimetersRatio, framesPerSeccond):
    previusPoint = None
    
    distance = 0
    speed = []
    for index in data["route"]:
        value = data["route"][index]
        
        point = [value['x'], value['y'], value['z']]
        
        if(previusPoint == None):
            previusPoint = point
            continue
        
        distance += math.dist(previusPoint, point) * toCentimetersRatio/100
        
        if(int(index) % framesPerSeccond == 0):
            speed.append(distance/framesPerSeccond)
            distance = 0
    data["speed"] = speed
    return speed


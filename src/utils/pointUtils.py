def objToPoint(object):
    return [object['x'], object['y']]

def pointToObj(point):
    return {
        'x': point[0],
        'y': point[1]
    }
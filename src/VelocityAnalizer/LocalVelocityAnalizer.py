def localVelocityAnalizer(data):

    frameCount = data["frameCount"]


    for index in range(frameCount):
        point = data["route"][index]

        nextPoint = data["route"][index]

        localDistanceX = point.x - nextPoint.x
        localDistanceY = point.y - nextPoint.y
        localDistanceZ = point.z - nextPoint.z

    return data

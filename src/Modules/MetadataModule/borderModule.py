def module_call(data):
    data["time_border_x"] = 0
    data["time_border_y"] = 0
    data["time_border_z"] = 0

    frame_border_points_top = data["frame_border_points_top"]  
    frame_border_points_side = data["frame_border_points_side"]

    
    border_min_x = min(frame_border_points_top[0][0], frame_border_points_top[1][0])
    border_max_x = max(frame_border_points_top[0][0], frame_border_points_top[1][0])

    border_min_y = min(frame_border_points_top[0][1], frame_border_points_top[1][1],
                       frame_border_points_side[0][0], frame_border_points_side[1][0])
    border_max_y = max(frame_border_points_top[0][1], frame_border_points_top[1][1],
                       frame_border_points_side[0][0], frame_border_points_side[1][0])

    border_min_z = min(frame_border_points_side[0][1], frame_border_points_side[1][1])
    border_max_z = max(frame_border_points_side[0][1], frame_border_points_side[1][1])

    for index in data["route"]:
        value = data["route"][index]

        x = value['x']
        y = value['y']
        z = value['z']

        if border_min_x <= x <= border_max_x:
            data["time_border_x"] += 1

        if border_min_y <= y <= border_max_y:
            data["time_border_y"] += 1

        if border_min_z <= z <= border_max_z:
            data["time_border_z"] += 1

    return data

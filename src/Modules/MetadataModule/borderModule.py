def module_call(data):
    data["time_border_x"] = 0
    data["time_border_y"] = 0
    data["time_border_z"] = 0

    # Extracting border values from frame_border_points_top and frame_border_points_side
    frame_border_points_top = data["frame_border_points_top"]  # Used for x and y axes
    frame_border_points_side = data["frame_border_points_side"]  # Used for y and z axes

    # Set up min and max borders for each axis based on frame_border_points
    border_min_x = min(frame_border_points_top[0][0], frame_border_points_top[1][0])
    border_max_x = max(frame_border_points_top[0][0], frame_border_points_top[1][0])

    border_min_y = min(frame_border_points_top[0][1], frame_border_points_top[1][1],
                       frame_border_points_side[0][0], frame_border_points_side[1][0])
    border_max_y = max(frame_border_points_top[0][1], frame_border_points_top[1][1],
                       frame_border_points_side[0][0], frame_border_points_side[1][0])

    border_min_z = min(frame_border_points_side[0][1], frame_border_points_side[1][1])
    border_max_z = max(frame_border_points_side[0][1], frame_border_points_side[1][1])

    # Iterate through each point in the route and calculate time within borders
    for index in data["route"]:
        value = data["route"][index]

        x = value['x']
        y = value['y']
        z = value['z']

        # Check if each coordinate is within the specified border range
        if border_min_x <= x <= border_max_x:
            data["time_border_x"] += 1

        if border_min_y <= y <= border_max_y:
            data["time_border_y"] += 1

        if border_min_z <= z <= border_max_z:
            data["time_border_z"] += 1

    return data

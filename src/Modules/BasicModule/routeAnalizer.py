def route_module(positions_top, positions_side):
    data = {"route": {}}

    frame_count = min(len(positions_top), len(positions_side))

    for index in range(frame_count):
        position_top = positions_top[index]
        position_side = positions_side[index]

        data["route"][index] = {
            "x": position_top[0],
            "y": position_top[1],
            "z": position_side[1]
        }

    data["frame_count"] = frame_count
    return data
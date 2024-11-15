def route_module(top_data, side_data, positions_top, positions_side):
    top_route_count = len(top_data["route"])
    side_route_count = len(side_data["route"])
    
    max_frame_count = side_route_count
    
    if(top_route_count > side_route_count):
        max_frame_count = top_route_count

    data = {"route": {}, "frame_count": max_frame_count }
    
    
    for index in range(max_frame_count):
        
        if(index < top_route_count):
            x = top_data["route"][index]["x"]
            y = top_data["route"][index]["y"]

        if(index < side_route_count):
            z = side_data["route"][index]["z"]
        

        data["route"][index] = {
            "x": x, 
            "y": y,
            "z": z,
        }

    return data
def route_module(positions_top, positions_side):
    data = {"route": {}}
    
    top_route_count = len(positions_top)
    side_route_count = len(positions_side)
    
    min_frame_count = side_route_count
    if(top_route_count < side_route_count):
        min_frame_count = top_route_count

    index_side = 0
    index_top = 0
    for index in range(min_frame_count):
        index_top += 1
        index_side += 1
        
        if(top_route_count == (index_top)):
            break
            index_top = 0
            
        if(side_route_count == (index_side)):
            break
            index_side = 0
        
        position_top = positions_top[index_top]
        position_side = positions_side[index_side]
        
        
        x = position_top[0]
        y = position_top[1]
        
        z = position_side[1]

        data["route"][index] = {
            "x": x, 
            "y": y,
            "z": z
        }
        
    data["frame_count"] = min_frame_count - 1
    return data
import concurrent.futures

from src.modules.routeModuleAddons.sideAnalizer import analyze_frame_side
from src.modules.routeModuleAddons.topAnalizer import analyze_frame_top


def route_module(top_video_input, side_video_input):

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_top = executor.submit(analyze_frame_top, top_video_input)
        future_side = executor.submit(analyze_frame_side, side_video_input)

        data_top = future_top.result()
        data_side = future_side.result()

    top_route_count = len(data_top["route"])
    side_route_count = len(data_side["route"])
    
    max_frame_count = side_route_count
    
    if(top_route_count > side_route_count):
        max_frame_count = top_route_count

    data = {"route": {}, "frame_count": max_frame_count }
    
    x = 0
    y = 0
    z = 0
    
    for index in range(max_frame_count):
        
        if(index < top_route_count):
            x = data_top["route"][index]["x"]
            y = data_top["route"][index]["y"]

        if(index < side_route_count):
            z = data_side["route"][index]["z"]

        data["route"][index] = {
            "x": x, 
            "y": y,
            "z": z,
        }

    return data
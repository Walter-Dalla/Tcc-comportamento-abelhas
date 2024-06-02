import concurrent.futures

from src.modules.routeModuleAddons.sideAnalizer import analyze_frame_side
from src.modules.routeModuleAddons.topAnalizer import analyze_frame_top


def route_module(top_video_input, side_video_input, output_location):

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_top = executor.submit(analyze_frame_top, top_video_input)
        future_side = executor.submit(analyze_frame_side, side_video_input)

        data_top = future_top.result()
        data_side = future_side.result()

    top_route_count = len(data_top["route"])
    side_route_count = len(data_side["route"])
    
    frame_count = side_route_count
    if(top_route_count > side_route_count):
        frame_count = top_route_count

    data = {"route": {}, "frame_count": frame_count }
    
    for index in range(frame_count):

        x = data_top["route"][index]["x"]
        y = data_top["route"][index]["y"]
        z = data_side["route"][index]["z"]

        data["route"][index] = {
            "x": x, 
            "y": y,
            "z": z,
        }

    return data
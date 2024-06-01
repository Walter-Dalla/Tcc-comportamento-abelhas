from interface.MainInterface import show_main_ui, run_loop

def velocityAnalisis():
    print("local-velocity")

    #data = importDataFromFile(routeJson)
    #localVelocityAnalizer(data["route"])

if __name__ == "__main__":
    screen = show_main_ui()
    run_loop(screen)
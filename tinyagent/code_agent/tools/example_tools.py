from tinyagent import tool

# Global variables to track state across calls
weather_global = '-'
traffic_global = '-'


@tool(name="get_weather", description="Get the weather for a given city.")
def get_weather(city: str) -> str:
    """Get the weather for a given city.
    Args:
        city: The city to get the weather for

    Returns:
        The weather for the given city
    """
    import random
    global weather_global
    output = f"Last time weather was checked was {weather_global}"
    weather_global = random.choice(['sunny', 'cloudy', 'rainy', 'snowy'])
    output += f"\n\nThe weather in {city} is now {weather_global}"

    return output


@tool(name="get_traffic", description="Get the traffic for a given city.")
def get_traffic(city: str) -> str:
    """Get the traffic for a given city.
    Args:
        city: The city to get the traffic for

    Returns:
        The traffic for the given city
    """
    import random
    global traffic_global
    output = f"Last time traffic was checked was {traffic_global}"
    traffic_global = random.choice(['light', 'moderate', 'heavy', 'blocked'])
    output += f"\n\nThe traffic in {city} is now {traffic_global}"

    return output 
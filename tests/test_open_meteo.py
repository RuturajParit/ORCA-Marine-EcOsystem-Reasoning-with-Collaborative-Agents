from data.open_meteo import fetch_combined_point


def main():
    lat = 18.90
    lon = 72.70

    print("Testing Open-Meteo Marine + Weather APIs...")
    print(f"Location: Mumbai ({lat}, {lon})")

    data = fetch_combined_point(
        lat,
        lon,
        forecast_days=3
    )

    print("\n✓ API request successful")
    print(f"Hours received: {len(data['hours'])}")

    if data["hours"]:
        print("\nFirst forecast hour:")
        print(data["hours"][0])

    print("\nData passed to ORCA agents can now be read from:")
    print("data['hours']")


if __name__ == "__main__":
    main()

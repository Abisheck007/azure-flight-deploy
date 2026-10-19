import streamlit as st
import requests
import json
from datetime import datetime

import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.environ["MONGO_URI"]

API_KEY = os.environ["API_KEY"]

from pymongo import MongoClient

client = MongoClient(MONGO_URI)

db = client["azure_deploy"]

airports_collection = db["airports"]
searches_collection = db["searches"]
flights_collection = db["flights"]


def save_search(origin, destination, travel_date):

    origin = origin.upper()
    destination = destination.upper()

    source_airport = airports_collection.find_one({"iata_code": origin})

    if not source_airport:
        source_result = airports_collection.insert_one({"iata_code": origin})

        source_id = str(source_result.inserted_id)

    else:
        source_id = str(source_airport["_id"])

    destination_airport = airports_collection.find_one({"iata_code": destination})

    if not destination_airport:

        destination_result = airports_collection.insert_one({"iata_code": destination})

        destination_id = str(destination_result.inserted_id)

    else:

        destination_id = str(destination_airport["_id"])

    search_result = searches_collection.insert_one(
        {
            "source_airport_id": source_id,
            "destination_airport_id": destination_id,
            "travel_date": str(travel_date),
        }
    )

    return str(search_result.inserted_id)


def save_flight(
    search_id, airline, dep_airport, arr_airport, dep_time, arr_time, duration, price
):

    try:

        flights_collection.insert_one(
            {
                "search_id": search_id,
                "airline": airline,
                "departure_airport": dep_airport,
                "arrival_airport": arr_airport,
                "departure_time": dep_time,
                "arrival_time": arr_time,
                "duration_minutes": duration,
                "price": price,
            }
        )

    except Exception as e:

        print("Mongo Error:", e)


def fetch_flights(origin, destination, date):
    url = "https://serpapi.com/search.json"

    params = {
        "engine": "google_flights",
        "api_key": API_KEY,
        "departure_id": origin.upper(),
        "arrival_id": destination.upper(),
        "outbound_date": date,
        "type": 2,
        "currency": "USD",
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        data = response.json()

        if "error" in data:
            return f"API Error:\n{data['error']}"

        flights = data.get("best_flights", [])

        if not flights:
            flights = data.get("other_flights", [])

        search_id = save_search(origin, destination, date)

        if not flights:
            return (
                "No flights found.\n\n"
                "Debug Response:\n" + json.dumps(data, indent=2)[:3000]
            )

        result = "✈️ Available Flights\n\n"

        for i, flight in enumerate(flights[:5], start=1):

            total_duration = flight.get("total_duration", "N/A")
            price = flight.get("price", "N/A")

            segments = flight.get("flights", [])

            if not segments:
                continue

            first = segments[0]
            last = segments[-1]

            airline = first.get("airline", "Unknown")

            dep_airport = first.get("departure_airport", {}).get("id", origin.upper())

            dep_time = first.get("departure_airport", {}).get("time", "N/A")

            arr_airport = last.get("arrival_airport", {}).get("id", destination.upper())

            arr_time = last.get("arrival_airport", {}).get("time", "N/A")

            save_flight(
                search_id,
                airline,
                dep_airport,
                arr_airport,
                dep_time,
                arr_time,
                total_duration,
                price,
            )
            result += (
                f"{i}. {airline}\n"
                f"   From: {dep_airport} ({dep_time})\n"
                f"   To:   {arr_airport} ({arr_time})\n"
                f"   Duration: {total_duration} mins\n"
                f"   Price: {price}\n\n"
            )

        return result

    except Exception as e:
        return f"Error: {str(e)}"
        return f"Error: {str(e)}"


st.set_page_config(page_title="Flight Search", page_icon="✈️", layout="centered")

st.title("🌍 Real-Time Flight Information")

st.write(
    "Enter source airport, destination airport, and travel date "
    "to retrieve flight details."
)

origin = st.text_input("Origin IATA Code", placeholder="MAA")

destination = st.text_input("Destination IATA Code", placeholder="DEL")

date = st.date_input("Date (YYYY-MM-DD)", value=None)

if st.button("Search Flights"):

    if not origin or not destination or not date:
        st.warning("Please fill all fields.")
    else:
        with st.spinner("Fetching flights..."):
            result = fetch_flights(origin, destination, date)

        st.text_area("Flight Results", value=result, height=400)

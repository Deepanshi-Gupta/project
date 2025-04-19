import streamlit as st
import json
import os
from serpapi import GoogleSearch 
from agno.agent import Agent
from agno.tools.serpapi import SerpApiTools
from agno.models.google import Gemini
from datetime import datetime
import google.generativeai as genai
import re

def get_iata_code(city_name: str) -> str | None:
    """Look up the IATA code for a given city name (case‑insensitive)."""
    return iata_map.get(city_name.strip().lower())

def load_latlong_coords(json_path: str = "coords.json") -> dict[str, str]:
    """
    Loads the city->"@lat,lon,14z" map from JSON, normalizing keys to lowercase.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # make lookup case‑insensitive
    return { city.strip().lower(): coords for city, coords in raw.items() }


# 1) Load the JSON file once at startup
with open("D:\CWV\AI-Powered-Itinerary-Generator\iata_code.json", "r", encoding="utf-8") as f:
    raw_map = json.load(f)

# 2) Normalize keys to lowercase for case‑insensitive lookup
iata_map = { city.lower(): code for city, code in raw_map.items() }

# Set up Streamlit UI with a travel-friendly theme
st.set_page_config(page_title="🌍 AI Travel Planner", layout="wide")
st.markdown(
    """
    <style>
        .title {
            text-align: center;
            font-size: 36px;
            font-weight: bold;
            color: #ff5733;
        }
        .subtitle {
            text-align: center;
            font-size: 20px;
            color: #555;
        }
        .stSlider > div {
            background-color: #f9f9f9;
            padding: 10px;
            border-radius: 10px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

#

# Title and subtitle
st.markdown('<h1 class="title">Itinary generator</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Plan your dream trip with AI! Get personalized recommendations for flights, hotels, and activities.</p>', unsafe_allow_html=True)

# User Inputs Section
source_name = (st.text_input("Departure City :", ))  # Example: BOM for Mumbai  (IATA Code)
destination_name = (st.text_input("Destination :", ))  # Example: DEL for Delhi
source = get_iata_code(source_name) if source_name else None
destination = get_iata_code(destination_name) if destination_name else None
# Load once
#src_code = get_iata_code(source)
#dst_code = get_iata_code(destination)


print(source,destination)
#(end_date - start_date).days
    
travel_theme = st.selectbox(
    "Select Your Travel Theme:",
    ["Couple Getaway", "Family Vacation", "Adventure Trip", "Solo Exploration"]
)

# Divider for aesthetics
st.markdown("---")

st.markdown(
    f"""
    <div style="
        text-align: center; 
        padding: 15px; 
        background-color: #d1e4ff; 
        border-radius: 10px; 
        margin-top: 20px;
    ">
        <h3>🌟 Your {travel_theme} to {destination} is about to begin! 🌟</h3>
    </div>
    """,
    unsafe_allow_html=True,
)

def format_datetime(iso_string):
    try:
        dt = datetime.strptime(iso_string, "%Y-%m-%d %H:%M")
        return dt.strftime("%b-%d, %Y | %I:%M %p")  # Example: Mar-06, 2025 | 6:20 PM
    except:
        return "N/A"

activity_preferences = st.text_area(
    "🌍 What activities do you enjoy? (e.g., relaxing on the beach, exploring historical sites, nightlife, adventure)",
    "Relaxing on the beach, exploring historical sites"
)

departure_date = st.date_input("Departure Date")
return_date = st.date_input("Return Date")
num_days = (return_date - departure_date).days
# Sidebar Setup
st.sidebar.subheader("Personalize Your Trip")

# Travel Preferences
budget = st.sidebar.radio(" Budget Preference:", ["Economy", "Standard", "Luxury"])
flight_class = st.sidebar.radio("Class:", ["Economy", "Business", "First Class"])
hotel_rating = st.sidebar.selectbox("Preferred Hotel Rating:", ["Any", "3⭐", "4⭐", "5⭐"])

GEMINI_API_KEY = "AIzaSyAw04tZ7jDVeAE7VhGYrzrWXiJIUtyCee0"  # Replace with your actual Gemini API key
SERPAPI_KEY = "0b94868e78d63bfec41dcee02f7d89f0fb6dadc4fbf679a02349c1428072610a"    # Replace with your actual SerpAPI key
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
# Initialize Gemini API
genai.configure(api_key=GEMINI_API_KEY)
# Create the model configuration for Gemini 2.2
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}
params = {
        "engine": "google_flights",
        "departure_id": source,
        "arrival_id": destination,
        "outbound_date": str(departure_date),
        "return_date": str(return_date),
        "currency": "INR",
        "hl": "en",
        "api_key": SERPAPI_KEY
    }


def search_hotels(location, check_in_date, check_out_date):
    params = {
        "engine": "google_hotels",
        "q": f"hotels in {location}",
        "check_in_date": str(check_in_date),
        "check_out_date": str(check_out_date),
        "currency": "INR",
        "hl": "en",
        "api_key": SERPAPI_KEY
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    hotels = results.get("hotels", [])
    return sorted(hotels, key=lambda x: x.get("price_metadata", {}).get("value", float("inf")))[:3]  # Get top 3 options by price


# Function to fetch flight data
def fetch_flights(source, destination, departure_date, return_date):
    params = {
        "engine": "google_flights",
        "departure_id": source,
        "arrival_id": destination,
        "outbound_date": str(departure_date),
        "return_date": str(return_date),
        "currency": "INR",
        "hl": "en",
        "api_key": SERPAPI_KEY
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    return results

# Function to extract top 3 cheapest flights
def extract_cheapest_flights(flight_data):
    best_flights = flight_data.get("best_flights", [])
    sorted_flights = sorted(best_flights, key=lambda x: x.get("price", float("inf")))[:2    ]  # Get top 3 cheapest
    return sorted_flights

# AI Agents
researcher = Agent(
    name="Researcher",
    instructions=[
        "Identify the travel destination specified by the user.",
        "Gather detailed information on the destination, including climate, culture, and safety tips.",
        "Find popular attractions, landmarks, and must-visit places.",
        "Search for activities that match the user’s interests and travel style.",
        "Prioritize information from reliable sources and official travel guides.",
        "Provide well-structured summaries with key insights and recommendations."
    ],
   
    model = genai.GenerativeModel(model_name="gemini-2.0-flash-exp",generation_config=generation_config),
    tools=[SerpApiTools(api_key=SERPAPI_KEY)],  # Added missing comma
    add_datetime_to_instructions=True,
)

planner = Agent(
    name="Planner",
    instructions=[
        "Gather details about the user's travel preferences and budget.",
        "Create a detailed itinerary with scheduled activities and estimated costs.",
        "Ensure the itinerary includes transportation options and travel time estimates.",
        "Optimize the schedule for convenience and enjoyment.",
        "Present the itinerary in a structured format."
    ],
    model = genai.GenerativeModel(model_name="gemini-2.0-flash-exp",generation_config=generation_config),
    add_datetime_to_instructions=True,
)

hotel_restaurant_finder = Agent(
    name="Hotel & Restaurant Finder",
    instructions=[
        "Identify key locations in the user's travel itinerary.",
        "Search for highly rated hotels near those locations.",
        "Search for top-rated restaurants based on cuisine preferences and proximity.",
        "Prioritize results based on user preferences, ratings, and availability.",
        "Provide direct booking links or reservation options where possible."
    ],
    model = genai.GenerativeModel(model_name="gemini-2.0-flash-exp",generation_config=generation_config),
    tools=[SerpApiTools(api_key=SERPAPI_KEY)],  # Added missing comma
    add_datetime_to_instructions=True,
)

# Generate Travel Plan
if st.button("🚀 Generate Travel Plan"):
    with st.spinner("✈️ Fetching best flight options..."):
        flight_data = fetch_flights(source,destination, departure_date, return_date)     
        cheapest_flights = extract_cheapest_flights(flight_data)
       

    # AI Processing
    with st.spinner("🔍 Researching best attractions & activities..."):
        research_prompt = (
            f"Research the best attractions and activities in {destination} for a {num_days}-day {travel_theme.lower()} trip. "
            f"The traveler enjoys: {activity_preferences}. Budget: {budget}. Flight Class: {flight_class}. "
            f"Hotel Rating: {hotel_rating}."
        )
        model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        generation_config=generation_config,
        )
        response = model.generate_content(research_prompt)
        research_results = response.text
        #research_results = researcher.run(research_prompt, stream=False)

    with st.spinner("🏨 Searching for hotels & restaurants..."):
        if "hotel_options" not in st.session_state:
            st.session_state["hotel_options"] = []  # Initialize if not already set

        for i, hotel in enumerate(st.session_state["hotel_options"]):
            st.write(f"Hotel {i+1}: {hotel}")

        hotel_restaurant_prompt = (
            f"Find the best hotels and restaurants near popular attractions in {destination} for a {travel_theme.lower()} trip. "
            f"Budget: {budget}. Hotel Rating: {hotel_rating}. Preferred activities: {activity_preferences}."
        )
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-exp",
            generation_config=generation_config,
        )
        response = model.generate_content(hotel_restaurant_prompt)
        hotel_restaurant_results = response.text
        # hotel_restaurant_results = hotel_restaurant_finder.run(hotel_restaurant_prompt, stream=False)

        for i, hotel in enumerate(st.session_state["hotel_options"]):
            col1, col2 = st.columns([3, 1])
            with col1:
                hotel_name = hotel.get("title", "Hotel")  # Get the hotel name from the "title" field
                st.write(f"**{hotel_name}** - {hotel.get('rating', 'N/A')}⭐")
                st.write(f"Price: ₹{hotel.get('price', 'N/A')} per night")
                if 'address' in hotel:
                    st.write(f"Address: {hotel['address']}")
            with col2:
                booking_link = hotel.get("availability", {}).get("booking_link", "")
                if booking_link:
                    st.link_button("Book Hotel", booking_link)
                else:
                    st.link_button("Search Hotels", f"https://www.google.com/travel/hotels/{st.session_state.destination}")

    with st.spinner("🗺️ Creating your personalized itinerary..."):
        planning_prompt = (
            f"Based on the following data, create a {num_days}-day itinerary for a {travel_theme.lower()} trip to {destination}. "
            f"The traveler enjoys: {activity_preferences}. Budget: {budget}. Flight Class: {flight_class}. Hotel Rating: {hotel_rating}. "
            f" Research: {research_results}. "
            f"Flights: {json.dumps(cheapest_flights)}. Hotels & Restaurants: {hotel_restaurant_results}."
        )
        model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        generation_config=generation_config,
        )
        response = model.generate_content(planning_prompt)
        itinerary = response.text
        #itinerary = planner.run(planning_prompt, stream=False)
    
    if cheapest_flights:
        st.subheader("Flight Options")
        # 1) Inject CSS for card + button
        st.markdown("""
        <style>
        .flight-card {
            width: 340px;
            min-height: 440px;             /* bumped up for button */
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            padding: 20px;
            text-align: center;
            transition: transform 0.2s ease-in-out, box-shadow 0.2s;
            margin: 20px auto;
            position: relative;            /* needed for absolute positioning of button */
        }
        .flight-card:hover {
            transform: scale(1.03);
            box-shadow: 0 6px 18px rgba(0,0,0,0.15);
        }
        .flight-card img {
            max-width: 100px;
            margin-bottom: 12px;
        }
        .flight-card .flight-no {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .flight-card .class {
            font-size: 1rem;
            margin-bottom: 12px;
            color: #555;
        }
        .flight-card .time {
            font-size: 0.95rem;
            margin: 4px 0;
            color: #333;
        }
        .flight-card .price {
            font-size: 1.4rem;
            font-weight: bold;
            color: #008000;
            margin: 16px 0;
        }
        .flight-card .book-btn {
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            display: inline-block;
            padding: 12px 28px;
            background-color: #007bff;
            color: white !important;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            z-index: 10;
            transition: background 0.2s;
        }
        .flight-card .book-btn:hover {
            background-color: #0056b3;
        }
        </style>
        """, unsafe_allow_html=True)


        # 2) Render the two cards
        cols = st.columns(2, gap="large")
        for idx, flight in enumerate(cheapest_flights[:2]):
            with cols[idx]:
                seg   = flight["flights"][0]
                logo  = seg["airline_logo"]
                fno   = seg["flight_number"]
                cls   = seg["travel_class"]
                dt    = format_datetime(seg["departure_airport"]["time"])
                at    = format_datetime(seg["arrival_airport"]["time"])
                price = flight["price"]

                # build booking link
                link = "#"
                tok  = flight["departure_token"]
                print(tok)
                if tok:
                    resp = GoogleSearch({**params, "departure_token": tok}).get_dict()
                    print(resp)
                    bt   = resp["best_flights"][idx]["booking_token"]
                    link = f"https://www.google.com/travel/flights?tfs={bt}"

                # 3) Card HTML
                st.markdown(f"""
                <div class="flight-card">
                <img src="{logo}" alt="logo"/>
                <div class="flight-no">{fno}</div>
                <div class="class">Class: {cls}</div>
                <div class="time"><strong>Dep:</strong> {dt}</div>
                <div class="time"><strong>Arr:</strong> {at}</div>
                <div class="price">₹ {price}</div>
                <a href="{link}" target="_blank" class="book-btn">🔗 Book Now</a>
                </div>
                """, unsafe_allow_html=True)
        #else:
            #st.warning("⚠️ No flight data available.")
        
    st.subheader("🏨 Hotels & Restaurants")

    latlong = load_latlong_coords().get(destination_name.strip().lower())
    if latlong is None:
        st.error("❌ Coordinates not found for the destination.")
    else:
        params = {
            "engine": "google_maps",
            "q": "Hotels & Restaurants",
            "ll": latlong,
            "api_key": SERPAPI_KEY
        }
        results  = GoogleSearch(params).get_dict()
        link_map = results["search_metadata"]["google_maps_url"]

        # ——— Add this “Explore on Map” button ———
        if link_map:
            st.markdown(
                f'''
                <a href="{link_map}" target="_blank">
                <div style="
                    display: inline-block;
                    padding: 12px 24px;
                    font-size: 1rem;
                    font-weight: 600;
                    color: #fff;
                    background-color: #28a745;
                    border-radius: 6px;
                    text-decoration: none;
                    margin-bottom: 16px;
                ">
                    🔍 Explore on Google Maps
                </div>
                </a>
                ''',
                unsafe_allow_html=True
            )

    st.write(hotel_restaurant_results)

    st.subheader("🗺️ Your Personalized Itinerary")
    st.write(itinerary)

    st.success("✅ Travel plan generated successfully!")
import datetime
from fastapi import FastAPI
from config import (ReservationType, User, Hotel, Hotels, Flight, Flights, Reservation, Restaurant, Restaurants, CarRentalCompany, CarRental,
GetAllHotelsInCity, GetHotelsPrices, GetHotelsAddress, GetRatingReviewsForHotels,
GetAllRestaurantsInCity, GetRestaurantsAddress, GetRatingReviewsForRestaurants,
GetCuisineTypeForRestaurants, GetDietaryRestrictionsForAllRestaurants, GetContactInformationForRestaurants,
GetPriceForRestaurants, CheckRestaurantOpeningHours, GetAllCarRentalCompaniesInCity,
GetCarTypesAvailable, GetRatingReviewsForCarRental, GetCarRentalAddress,
GetCarFuelOptions, GetCarPricePerDay, ReserveHotel, ReserveRestaurant,
ReserveCarRental, GetFlightInformation,
user, hotels, restaurants, car_rental, reservation, flights)

app = FastAPI()


@app.get("/get_user_information")
def get_user_information() -> dict[str, str]:
    """Get the user information, could be: first name, last name, ID number, email, phone number, address, passport number, bank account number, credit card number. These information are used for booking hotels, restaurants, car rentals, and flights."""
    return {
        "First Name": user.first_name,
        "Last Name": user.last_name,
        "ID Number": user.ID_number,
        "Email": user.email,
        "Phone Number": user.phone_number,
        "Address": user.address,
        "Passport Number": user.passport_number,
        "Bank Account Number": user.bank_account_number,
        "Credit Card Number": user.credit_card_number,
    }

@app.post("/get_all_hotels_in_city")
def get_all_hotels_in_city(req: GetAllHotelsInCity) -> str:
    """Get all hotels in the given city.
    :param city: The city to get hotels from.
    """
    hotel_names = [hotel.name for hotel in hotels.hotel_list if hotel.city == req.city]
    hotel_names = "Hotel Names: " + "\n".join(hotel_names) + "\n"
    return hotel_names

@app.post("/get_hotels_prices")
def get_hotels_prices(req: GetHotelsPrices) -> dict[str, str]:
    """Get all hotels within the given budget, should be within the price range.
    :param hotel_names: The name of the hotel to get the price range for.
    """
    return {
        hotel.name: f"Price range: {hotel.price_min} - {hotel.price_max}"
        for hotel in hotels.hotel_list
        if hotel.name in req.hotel_names
    }

@app.post("/get_hotels_address")
def get_hotels_address(req: GetHotelsAddress) -> dict[str, str]:
    """Get the address of the given hotel.
    :param hotel_name: The name of the hotel to get the address for.
    """
    return {hotel.name: hotel.address for hotel in hotels.hotel_list if hotel.name == req.hotel_name}


@app.post("/get_rating_reviews_for_hotels")
def get_rating_reviews_for_hotels(req: GetRatingReviewsForHotels) -> dict[str, str]:
    """Get the rating and reviews for the given hotels.
    :param hotel_names: The names of the hotels to get reviews for.
    """
    return {
        hotel.name: "Rating: " + str(hotel.rating) + "\n" + "Reviews: " + "\n".join(hotel.reviews)
        for hotel in hotels.hotel_list
        if hotel.name in req.hotel_names
    }

@app.post("/get_all_restaurants_in_city")
def get_all_restaurants_in_city(req: GetAllRestaurantsInCity) -> str:
    """Get all restaurants in the given city.
    :param city: The city to get restaurants from.
    """
    restaurant_names = [restaurant.name for restaurant in restaurants.restaurant_list if restaurant.city == req.city]
    restaurant_names = "Restaurant in " + req.city + ": " + "\n".join(restaurant_names) + "\n"
    return restaurant_names

@app.post("/get_restaurants_address")
def get_restaurants_address(req: GetRestaurantsAddress) -> dict[str, str]:
    """Get the address of the given restaurants.
    :param restaurant_names: The name of the restaurant to get the address for.
    """
    address = {
        restaurant.name: restaurant.address
        for restaurant in restaurants.restaurant_list
        if restaurant.name in req.restaurant_names
    }

    return address

@app.post("/get_rating_reviews_for_restaurants")
def get_rating_reviews_for_restaurants(req: GetRatingReviewsForRestaurants) -> dict[str, str]:
    """Get the rating and reviews for the given restaurants.
    :param restaurant_names: The names of the restaurants to get reviews for.
    """
    return {
        restaurant.name: "Rating: " + str(restaurant.rating) + "\n" + "Reviews: " + "\n".join(restaurant.reviews)
        for restaurant in restaurants.restaurant_list
        if restaurant.name in req.restaurant_names
    }

@app.post("/get_cuisine_type_for_restaurants")
def get_cuisine_type_for_restaurants(req: GetCuisineTypeForRestaurants) -> dict[str, str]:
    """Get the cuisine type of the given restaurants, could be: Italian, Chinese, Indian, Japanese.
    :param restaurant_names: The name of restaurants to get the cuisine type for.
    """
    return {
        restaurant.name: restaurant.cuisine_type
        for restaurant in restaurants.restaurant_list
        if restaurant.name in req.restaurant_names
    }

@app.post("/get_dietary_restrictions_for_all_restaurants")
def get_dietary_restrictions_for_all_restaurants(req: GetDietaryRestrictionsForAllRestaurants) -> dict[str, str]:
    """Get the dietary restrictions of the given restaurants, could be: Vegetarian, Vegan, Gluten-free, Dairy-free.
    :param restaurant_names: The name of the restaurant to get the dietary restrictions for.
    """
    restaurant_names_ = ", ".join(req.restaurant_names)
    return {
        restaurant.name: restaurant.dietary_restrictions
        for restaurant in restaurants.restaurant_list
        if restaurant.name in restaurant_names_
    }

@app.post("/get_contact_information_for_restaurants")
def get_contact_information_for_restaurants(req: GetContactInformationForRestaurants) -> dict[str, str]:
    """Get the contact information of the given restaurants.
    :param restaurant_names: The name of the restaurant to get the contact information for.
    """
    return {
        restaurant.name: restaurant.contact_information
        for restaurant in restaurants.restaurant_list
        if restaurant.name in req.restaurant_names
    }

@app.post("/get_price_for_restaurants")
def get_price_for_restaurants(req: GetPriceForRestaurants) -> dict[str, float]:
    """Get the price per person of the given restaurants.
    :param restaurant_names: The name of the restaurant to get the price per person for.
    """
    return {
        restaurant.name: restaurant.price_per_person
        for restaurant in restaurants.restaurant_list
        if restaurant.name in req.restaurant_names
    }

@app.post("/check_restaurant_opening_hours")
def check_restaurant_opening_hours(req: CheckRestaurantOpeningHours) -> dict[str, str]:
    """Get the openning hours of the given restaurants, check if the restaurant is open.
    :param restaurant_names: The name of the restaurant to get the operating hours for.
    """
    return {
        restaurant.name: restaurant.operating_hours
        for restaurant in restaurants.restaurant_list
        if restaurant.name in req.restaurant_names
    }

@app.post("/get_all_car_rental_companies_in_city")
def get_all_car_rental_companies_in_city(req: GetAllCarRentalCompaniesInCity) -> str:
    """Get all car rental companies in the given city.
    :param city: The city to get car rental companies from.
    """
    company_names = [company.name for company in car_rental.company_list if company.city == req.city]
    company_names = "Car Rental Companies in " + req.city + ": " + "\n".join(company_names) + "\n"
    return company_names

@app.post("/get_car_types_available")
def get_car_types_available(req: GetCarTypesAvailable) -> dict[str, list]:
    """Get the car types available for the given car rental companies.
    :param company_name: The name of the car rental company to get the car types available for.
    """
    return {
        company.name: company.car_types_available for company in car_rental.company_list if company.name in req.company_name
    }

@app.post("/get_rating_reviews_for_car_rental")
def get_rating_reviews_for_car_rental(req: GetRatingReviewsForCarRental) -> dict[str, str]:
    """Get the rating and reviews for the given car rental companies.
    :param company_name: The name of the car rental company to get reviews for.
    """
    return {
        company.name: "Rating: " + str(company.rating) + "\n" + "Reviews: " + "\n".join(company.reviews)
        for company in car_rental.company_list
        if company.name in req.company_name
    }

@app.post("/get_car_rental_address")
def get_car_rental_address(req: GetCarRentalAddress) -> dict[str, str]:
    """Get the address of the given car rental companies.
    :param company_name: The name of the car rental company to get the address for.
    """
    return {company.name: company.address for company in car_rental.company_list if company.name in req.company_name}

@app.post("/get_car_fuel_options")
def get_car_fuel_options(req: GetCarFuelOptions) -> dict[str, list]:
    """Get the fuel options of the given car rental companies.
    :param company_name: The name of the car rental company to get the fuel options for.
    """
    return {company.name: company.fuel_options for company in car_rental.company_list if company.name in req.company_name}

@app.post("/get_car_price_per_day")
def get_car_price_per_day(req: GetCarPricePerDay) -> dict[str, float]:
    """Get the price per day of the given car rental companies.
    :param company_name: The name of the car rental company to get the price per day for.
    """
    return {company.name: company.price_per_day for company in car_rental.company_list if company.name in req.company_name}

@app.post("/reserve_hotel")
def reserve_hotel(
        req: ReserveHotel
) -> str:
    """Makes a reservation for a hotel with the provided details..
    :param hotel: Where the reservation is made. It must only be the name of the hotel.
    :param start_day: The check-in day for the hotel. Should be in ISO format 'YYYY-MM-DD'.
    :param end_day: The check-out day for the hotel. Should be in ISO format 'YYYY-MM-DD'.
    """
    reservation.contact_information = get_user_information()["Phone Number"]
    reservation.reservation_type = ReservationType.HOTEL
    reservation.title = req.hotel
    reservation.start_time = datetime.datetime.fromisoformat(req.start_day)
    reservation.end_time = datetime.datetime.fromisoformat(req.end_day)
    return f"Reservation for {req.hotel} from {req.start_day} to {req.end_day} has been made successfully."

@app.post("/reserve_restaurant")
def reserve_restaurant(
        req: ReserveRestaurant
) -> str:
    """Makes a reservation for a restaurant with the provided details.

    :param restaurant: Where the reservation is made. It must only be the name of the restaurant.
    :param start_time: The reservation time. Should be in ISO format 'YYYY-MM-DD HH:MM'.
    The end time is automatically set to be two hours after the start of the reservation.
    """
    reservation.contact_information = get_user_information()["Phone Number"]
    reservation.reservation_type = ReservationType.RESTAURANT
    reservation.title = req.restaurant
    reservation.start_time = datetime.datetime.fromisoformat(req.start_time)
    reservation.end_time = datetime.datetime.fromisoformat(req.start_time) + datetime.timedelta(hours=2)
    reservation_date = reservation.start_time.date().isoformat()
    start_time = reservation.start_time.strftime("%H:%M")
    end_time = reservation.end_time.strftime("%H:%M")
    return f"Reservation for {req.restaurant} from {start_time} to {end_time} on {reservation_date} has been made successfully."

@app.post("/reserve_car_rental")
def reserve_car_rental(
        req: ReserveCarRental
):
    """Makes a reservation for a car rental with the provided details.

    :param company: Where the reservation is made. It must only be the name of the car rental company.
    :param start_time: The reservation starting time. Should be in ISO format 'YYYY-MM-DD HH:MM'.
    :param end_time: The reservation end time. Should be in ISO format 'YYYY-MM-DD HH:MM'.
    """
    reservation.contact_information = get_user_information()["Phone Number"]
    reservation.reservation_type = ReservationType.CAR
    reservation.title = req.company
    reservation.start_time = datetime.datetime.fromisoformat(req.start_time)
    reservation.end_time = datetime.datetime.fromisoformat(req.start_time)
    return f"Reservation for a car at {req.company} from {req.start_time} to {req.end_time} has been made successfully."

@app.post("/get_flight_information")
def get_flight_information(
       req: GetFlightInformation
) -> str:
    """Get the flight information from the departure city to the arrival city.
    :param departure_city: The city to depart from.
    :param arrival_city: The city to arrive at.
    """
    flight_info = [
        f"Airline: {flight.airline}, Flight Number: {flight.flight_number}, Departure Time: {flight.departure_time}, Arrival Time: {flight.arrival_time}, Price: {flight.price}, Contact Information: {flight.contact_information}"
        for flight in flights.flight_list
        if flight.departure_city == req.departure_city and flight.arrival_city == req.arrival_city
    ]
    return "\n".join(flight_info)
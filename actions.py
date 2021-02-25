from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import urllib3
from rasa_sdk import Action
from rasa_sdk.events import SlotSet
from rasa_sdk.events import AllSlotsReset
from rasa_sdk.events import Restarted

urllib3.disable_warnings()

import re
import pandas as pd
from threading import Thread
from flask import Flask
from flask_mail import Mail, Message
from time import sleep
from concurrent.futures import ThreadPoolExecutor

#global variable definitions
top_10_restaurant_details = []


#function to verify the location provided by user
class VerifyLocation(Action):
    
    def __init__(self):
        self.WeOperate = ['new delhi', 'gurgaon', 'noida', 'faridabad', 'allahabad', 'bhubaneshwar', 'mangalore', 'mumbai', 'ranchi', 'patna', 'mysore', 'aurangabad', 'amritsar', 'puducherry', 'varanasi', 'nagpur', 'vadodara', 'dehradun', 'vizag', 'agra', 'ludhiana', 'kanpur', 'lucknow', 'surat', 'kochi', 'indore', 'ahmedabad', 'coimbatore', 'chennai', 'guwahati', 'jaipur', 'hyderabad', 'bangalore', 'nashik', 'pune', 'kolkata', 'bhopal', 'goa', 'chandigarh', 'ghaziabad', 'ooty', 'gangtok', 'shimla']

    def name(self):
        return "verify_location"

    def verify_location(self, loc):
        return loc.lower() in self.WeOperate

    def run(self, dispatcher, tracker, domain):
        loc = tracker.get_slot('location')
        if loc == "Other_cities":
            dispatcher.utter_template("utter_other_cities", tracker)
            loc = tracker.get_slot('location')
            return [SlotSet('location', loc), SlotSet("location_ok", False)]
        if not (self.verify_location(loc)):
            dispatcher.utter_message("Sorry, we do not operate in " + loc + " yet. Please try some other city.")
            return [SlotSet('location', None), SlotSet("location_ok", False)]
        else:
            return [SlotSet('location', loc), SlotSet("location_ok", True)]

class VerifyCuisine(Action):
    
    def name(self):
        return "verify_cuisine"

    def run(self, dispatcher, tracker, domain):
        cuisines = ['chinese','mexican','italian','american','south indian','north indian']
        error_msg = "Sorry!! The cuisine is not supported. Please re-enter."
        cuisine = tracker.get_slot('cuisine')
        try:
            cuisine = cuisine.lower()
        except (RuntimeError, TypeError, NameError, AttributeError):
            dispatcher.utter_message(error_msg)
            return [SlotSet('cuisine', None), SlotSet('cuisine_ok', False)]
        if cuisine in cuisines:
            return [SlotSet('cuisine', cuisine), SlotSet('cuisine_ok', True)]
        else:
            dispatcher.utter_message(error_msg)
            return [SlotSet('cuisine', None), SlotSet('cuisine_ok', False)]

class VerifyBudget(Action):
    def name(self):
        return 'verify_budget'

    def run(self, dispatcher, tracker, domain):
        error_msg = "Sorry!! price range not supported, please re-enter."
        try:
            budgetmin = int(tracker.get_slot('budgetmin'))
            budgetmax = int(tracker.get_slot('budgetmax'))
        except ValueError:
            dispatcher.utter_message(error_msg)
            return [SlotSet('budgetmin', None), SlotSet('budgetmax', None), SlotSet('budget_ok', False)]
        min_dict = [0, 300, 700]
        max_dict = [300, 700]
        if budgetmin in min_dict and (budgetmax in max_dict or budgetmax > 700):
            return [SlotSet('budgetmin', budgetmin), SlotSet('budgetmax', budgetmax), SlotSet('budget_ok', True)]
        else:
            dispatcher.utter_message(error_msg)
            return [SlotSet('budgetmin', 0), SlotSet('budgetmax', 10000), SlotSet('budget_ok', False)]

class ActionSearchRestaurants(Action):
    def name(self):
        return 'action_search_restaurants'

    def run(self, dispatcher, tracker, domain):
        
        
        restaurant_exist = False
        response = ""

        loc = tracker.get_slot('location')
        cuisine = tracker.get_slot('cuisine')
        budget_min_price = int(tracker.get_slot('budgetmin'))
        budget_max_price = int(tracker.get_slot('budgetmax'))

        ZomatoData = pd.read_csv('zomato.csv', encoding="ISO8859")
        ZomatoData = ZomatoData.drop_duplicates().reset_index(drop=True)
        results = ZomatoData[(ZomatoData['Cuisines'].apply(lambda x: cuisine.lower() in x.lower())) & (ZomatoData['City'].apply(lambda x: loc.lower() in x.lower())) & (ZomatoData['Average Cost for two'] >= budget_min_price) & (ZomatoData['Average Cost for two'] <= budget_max_price)]
        results = results[['Restaurant Name','Address','Average Cost for two','Aggregate rating']].sort_values('Aggregate rating',ascending=False)
        if results.shape[0] == 0:
            response = "No restaurent found with your search"
            dispatcher.utter_message("\n" + response)
        else:
            for restaurant in results.iloc[:5].iterrows():
                restaurant = restaurant[1]
                response = response + F"Found {restaurant['Restaurant Name']} in {restaurant['Address']} rated {restaurant['Address']} with avg cost {restaurant['Average Cost for two']} \n\n"
            dispatcher.utter_message("Top 5 Restaurant : " + "\n" + response)
        
        global top_10_restaurant_details
        top_10_restaurant_details = results.iloc[:10]
        if len(top_10_restaurant_details) > 0:
            restaurant_exist = True

        return [SlotSet('location', loc), SlotSet('restaurant_exist', restaurant_exist)]

class ActionValidateEmail(Action):
    def name(self):
        return 'action_validate_email'

    def run(self, dispatcher, tracker, domain):
        pattern = "(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
        email_check = tracker.get_slot('email')
        if email_check is not None:
            if re.search("(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email_check):
                return [SlotSet('email_ok', True)]
            else:
                dispatcher.utter_message("Sorry this is not a valid email. please check for typing errors")
                return [SlotSet('email', None), SlotSet("email_ok", False)]
        else:
            dispatcher.utter_message("Sorry I could'nt understand the email address you provided? Please provide again")
            return [SlotSet('email', None)]

def config():
    gmail_user = "india.foodie4@gmail.com"
    gmail_pwd = "QWERTY000"  # Gmail Password
    gmail_config = (gmail_user, gmail_pwd)
    return gmail_config


def mail_config(gmail_credential_detail):
    mail_settings = {
        "MAIL_SERVER": 'smtp.gmail.com',
        "MAIL_PORT": 465,
        "MAIL_USE_TLS": False,
        "MAIL_USE_SSL": True,
        "MAIL_USERNAME": gmail_credential_detail[0],
        "MAIL_PASSWORD": gmail_credential_detail[1]
    }
    return mail_settings


gmail_credentials = config()

app = Flask(__name__)
app.config.update(mail_config(gmail_credentials))
mail = Mail(app)


def send_async_email(flask_app, msg):
    with flask_app.app_context():
        # block only for testing parallel thread
        for i in range(10, -1, -1):
            sleep(2)
        mail.send(msg)


def send_email(recipient, top_10_restaurant_df):
    msg = Message(subject="Restaurant Details", sender=gmail_credentials[0], recipients=[recipient])
    msg.html = u'<h2>Foodie has found few restaurants for you:</h2>'

    for ind, val in top_10_restaurant_df.iterrows():
        name = top_10_restaurant_df['Restaurant Name'][ind]
        location = top_10_restaurant_df['Address'][ind]
        budget = top_10_restaurant_df['Average Cost for two'][ind]
        rating = top_10_restaurant_df['Aggregate rating'][ind]

        msg.html += u'<h3>{name} (Rating: {rating})</h3>'.format(name=name, rating=rating)
        msg.html += u'<h4>Address: {locality}</h4>'.format(locality=location)
        msg.html += u'<h4>Average Budget for 2 people: Rs{budget}</h4>'.format(budget=str(budget))


    thr = Thread(target=send_async_email, args=[app, msg])
    thr.start()


class SendMail(Action):
    def name(self):
        return 'action_send_mail'

    def run(self, dispatcher, tracker, domain):
        recipient = tracker.get_slot('email')

        try:
            restaurant_top_10_details = top_10_restaurant_details.copy()
            send_email(recipient, restaurant_top_10_details)
            dispatcher.utter_message("Have a great day! Mail is sent")
        except:
            dispatcher.utter_message("Email not sent, "
                                     ""
                                     ""
                                     "address is not valid")


class ActionSlotReset(Action):
    def name(self):
        return 'action_slot_reset'

    def run(self, dispatcher, tracker, domain):
        return [AllSlotsReset()]

class ActionRestarted(Action):
    def name(self):
        return 'action_restart'

    def run(self, dispatcher, tracker, domain):
        return [Restarted()]
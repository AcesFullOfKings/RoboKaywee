import requests
import re

from decorators      import is_command
from crypto_data     import crypto_data

def get_key(value):
    for key, value in crypto_data.items():
        if value == value:
            return key

    return "BTC"

@is_command("Check all the crypto prices.")
def crypto(message_dict):
    user = message_dict["display-name"].lower()
    message = [message_dict["message"]]
    message_dict["suppress_log"] = True
    
    # Attempt to split the message and get each item into an array
    try:
        message = re.split(', |; |\s', message)
    # Fail gracefully if it's a single or empty message
    except Exception as ex:
        log(f"Exception in crypto.crypto: {str(ex)}")

    # Check each item requested and make sure it's the short-code and not the full name
    # Convert to short-code from name if needed
    for item in message:
        if item.length > 3:
            crypto = [get_key(item)]
            message[item] = crypto        

    # If the message is empty, return the default values
    if message[0] == "":
        message = ["BTC", "ETH", "DOGE"]

    # Return the current value(s) of the requested crypto
    for item in message:
        try:
            result = requests.get(f"https://api.coinbase.com/v2/prices/{item.upper()}-USD/spot").json()
            crypto_name = crypto_data[item]
            value = float(result["data"]["amount"])
        except Exception as ex:
            log(f"Exception in crypto.crypto: {str(ex)}")
            return False

        if not message_dict.get("suppress_log", False):
            log(f"Sent {item.upper()} of ${value:,} to {user}")
        
        send_message(f"{crypto_name} is currently worth ${value:,}")

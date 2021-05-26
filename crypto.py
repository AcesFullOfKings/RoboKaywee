def crypto(message_dict):
    user = message_dict["display-name"].lower()
    message = message_dict["message"]
    
    # If the message is empty, return the default values
    if message[1] == "":
        crypto_codes = ["BTC", "ETH", "DOGE"]

    # Return the current value(s) of the requested crypto
    crypto_codes = message.split(" ")[1:]
    for item in crypto_codes:
        try:
            result = requests.get(f"https://api.coinbase.com/v2/prices/{item.upper()}-USD/spot").json()
            value = float(result["data"]["amount"])
        except Exception as ex:
            log(f"Exception in crypto.crypto: {str(ex)}")
            send_message(f"{item.upper()} is not currently available via coinbase")
            return False

        send_message(f"{item.upper()} is currently worth ${value:,}")

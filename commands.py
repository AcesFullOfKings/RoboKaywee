import random
import requests
import re
import subprocess
import os
import sys

from time            import sleep, time
from datetime        import date, datetime
from fortunes        import fortunes
from threading       import Thread
from credentials     import kaywee_channel_id, robokaywee_client_id, exchange_API_key, weather_API_key 
from googletrans     import Translator
from multiprocessing import Process
from james           import seconds_to_duration, timeuntil
from contextlib      import suppress
#from james import translate as j_translate

from PyDictionary import PyDictionary
dic = PyDictionary()

timers = set()

def is_command(description=""):
	"""
	This is the decorator function which marks other functions as commands and sets their properties.
	"""
	def inner(func, description=description):
		func.is_command = True
		func.description = description
		return func
	return inner

"""
Each @is_command function is a command (!!), callable by sending "!<function_name>" in chat.
All replies will be sent in the bot's colour, using /me unless specified otherwise.
"""

currencies = {'CAD', 'HKD', 'ISK', 'PHP', 'DKK', 'HUF', 'CZK', 'GBP', 'RON', 'SEK', 'IDR', 'INR', 'BRL', 'RUB', 'HRK', 'JPY', 'THB', 'CHF', 'EUR', 'MYR', 'BGN', 'TRY', 'CNY', 'NOK', 'NZD', 'ZAR', 'USD', 'MXN', 'SGD', 'AUD', 'ILS', 'KRW', 'PLN'}

toxic_poll = False
toxic_votes = 0
nottoxic_votes = 0
voters = set()
translator = Translator(service_urls=['translate.googleapis.com','translate.google.com','translate.google.co.kr'])
all_emotes = [] # populated below

@is_command("Allows mods to add and edit existing commands. Syntax: !rcommand [add/edit/delete/options] <command name> <add/edit: <command text> // options: <[cooldown/usercooldown/permission]>>")
def rcommand(message_dict):
	"""
	format:
	!rcommand <action> <command> [<params>]

	examples:
	* add a text command:
		!rcommand add helloworld Hello World!
	* edit an existing text command:
		!rcommand edit helloworld Hello World Again!
	* delete a command:
		!rcommand delete helloworld
	* change command options:
		!rcommand options helloworld permission 10
		!rcommand options helloworld cooldown 60
		!rcommand options helloworld usercooldown 120
	* view current command details:
		!rcommand view helloworld
	"""
	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	user_permission = message_dict["user_permission"] 

	params = message.split(" ")[1:]
	try:
		action = params[0]
		command_name = params[1].lower()
	except IndexError:
		send_message("Syntax error.")
		return False

	if action == "edit":
		if command_name in command_dict:
			if not command_dict[command_name]["coded"] and "response" in command_dict[command_name]:
				response = " ".join(params[2:])
				if response[:4] == "/me ":
					response = response[4:] # trim the space too

				response = response.replace("|", "/") # pipes break the formatting on the reddit wiki

				command_dict[command_name]["response"] = response

				send_message(f"Command {command_name} has been updated.")
				write_command_data(force_update_reddit=True)
			else:
				send_message(f"The command {command_name} is not updatable.")
		else:
			send_message(f"No command exists with name {command_name}.")
	elif action == "options":
		try:
			option = params[2]
		except IndexError:
			send_message("Syntax error.")
			return False
		if option in ["globalcooldown", "cooldown"]: # assume "cooldown" means global cooldown
			try:
				cooldown = int(params[3])
				assert 0 <= cooldown <= 300
			except (ValueError, IndexError, AssertionError):
				send_message("Cooldown must be provided as an integer between 1 and 300 seconds.")
				return False

			if command_name  in command_dict:
				command_dict[command_name]["global_cooldown"] = cooldown
				write_command_data(force_update_reddit=True)
				log(f"{user} updated global cooldown on command {command_name} to {cooldown}")
				send_message(f"Global Cooldown updated to {cooldown} on {command_name}")
			else:
				send_message(f"No command exists with name {command_name}.")
		elif option == "usercooldown":
			try:
				cooldown = int(params[3])
				assert 0 <= cooldown <= 3600
			except (ValueError, IndexError, AssertionError):
				send_message("Cooldown must be provided as an integer between 1 and 3600 seconds.")
				return False

			command_dict[command_name]["user_cooldown"] = cooldown
			write_command_data(force_update_reddit=True)
			log(f"{user} updated user cooldown on command {command_name} to {cooldown}")
			send_message(f"User Cooldown upated to {cooldown} on {command_name}")
		elif option == "permission":
			try:
				permission = int(params[3])
			except (ValueError, IndexError):
				send_message("Permission must be an integer: 0=All, 4=Subscriber, 6=VIP, 8=Moderator, 10=Broadcaster, 12=Owner, 20=Disabled")
				return False

			if command_name in command_dict:
				for enum in permissions:
					if enum.value == permission:
						current_permission = command_dict[command_name]["permission"]
						if current_permission == 20:
							current_permission = 8

						if user_permission >= current_permission:
							command_dict[command_name]["permission"] = permission
							write_command_data(force_update_reddit=True)
							send_message(f"Permission updated to {enum.name} on command {command_name}")
							log(f"{user} updated permission on command {command_name} to {enum.name}")
							return True # also exits the for-loop
						else:
							send_message("You don't have permission to do that.")
							return False
				else:
					send_message("Invalid Permission: Use 0=All, 4=Subscriber, 6=VIP, 8=Moderator, 9=Owner, 10=Broadcaster, 20=Disabled")
					return False
			else:
				send_message(f"No command exists with name {command_name}.")
				return False
		else:
			send_message("Unrecognised option: must be permission, globalcooldown, or usercooldown")
			return False
	elif action in ["add", "create"]:
		if command_name not in command_dict:
			try:
				response = " ".join(params[2:])
				assert response != ""
			except (IndexError, AssertionError):
				send_message("Syntax error.")
				return False
			else:
				if response[:4] == "/me ":
					response = response[4:] # trim the space too
				response = response.replace("|", "/") # pipes break the formatting on the reddit wiki
				
				command_dict[command_name] = {'permission': 0, 'global_cooldown': 1, 'user_cooldown': 0, 'coded': False, 'uses':0, 'response': response}
				write_command_data(force_update_reddit=True)
				send_message("Added command " + command_name)
				log(f"{user} added command {command_name}")
		else:
			send_message("Command " + command_name + " already exists.")

	elif action in ["remove", "delete"]:
		if command_name in command_dict:
			if command_dict[command_name]["coded"] == False:
				del command_dict[command_name]
				write_command_data(force_update_reddit=True)
				send_message("Deleted command " + command_name)
				log(f"{user} deleted command {command_name}")
			else:
				send_message(f"You cannot delete the {command_name} command.")
		else:
			send_message(f"No command exists with name {command_name}.")
	#elif action == "alias": # ???
	#	pass
	elif action in ["view", "show"]:
		view_command = command_dict[command_name]

		usercooldown = view_command.get("user_cooldown"  , 0)
		cooldown     = view_command.get("global_cooldown", 0)
		coded        = view_command.get("coded"          , False)
		permission   = view_command.get("permission"     , 0)
		response     = view_command.get("response"       , "")

		permission_name = "Unknown"

		for enum in permissions:
			if enum.value == permission:
				permission_name = enum.name

		if coded or response == "":
			send_message(f"{command_name}: Permission: {permission_name}; Global Cooldown: {cooldown}; User Cooldown: {usercooldown}")
		else:
			send_message(f"{command_name}: Permission: {permission_name}; Global Cooldown: {cooldown}; User Cooldown: {usercooldown}; Response: {response}")

	else:
		send_message("Unrecognised action: must be add, remove, edit, options, view")

@is_command("Sends a triangle of emotes. Syntax: !triangle <emote> e.g. `!triangle LUL`")
def triangle(message_dict):
	global all_emotes
	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	emotes = message_dict["emotes"]

	params = message.split(" ")
	try:
		emote = params[1]
	except:
		return False

	valid_emote = emote in all_emotes

	if not valid_emote:
		try:
			emotes_in_msg = emotes.split("/")
			for e in emotes_in_msg:
				id, positions = e.split(":")
				start_pos, end_pos = positions.split(",")[0].split("-")
				if start_pos == "10":
					valid_emote = True
					break
		except:
			pass # emote stays not valid

	if not valid_emote:
		send_message("You can only triangle with an emote.")
		return False

	num = 3
		
	try:
		num = int(params[2])
	except IndexError:
		pass #leave it at 3
	except ValueError: #if conversion to int fails, e.g. int("hello")
		num = 3
			
	if emote != "":
		if num > 5:
			num = 5
		
		counts = list(range(1,num+1)) + list(range(1,num)[::-1])
		for count in counts:
			send_message((emote + " ") * count)
		log(f"Sent triangle of {emote} of size {num} to {user}")

@is_command("Begins a toxicpoll")
def toxicpoll(message_dict):
	global nochat_on
	global toxic_poll

	if not toxic_poll:
		nochat_on = False # game is over so turn off nochat mode
		Thread(target=_start_toxic_poll, name="Toxic Poll").start()

@is_command("Only allowed while a toxicpoll is active. Votes toxic.")
def votetoxic(message_dict):
	global toxic_poll
	global toxic_votes
	global voters

	user = message_dict["display-name"].lower()

	if toxic_poll and user not in voters:
		toxic_votes += 1
		voters.add(user)
		send_message(f"{user} voted toxic.")
		print(f"Toxic vote from {user}!")
	else:
		return False

@is_command("Only allowed while a toxicpoll is active. Votes nice.")
def votenice(message_dict):
	global toxic_poll
	global nottoxic_votes
	global voters

	user = message_dict["display-name"].lower()

	if toxic_poll and user not in voters:
		nottoxic_votes += 1
		voters.add(user)
		send_message(f"{user} voted NOT toxic.")
		print(f"NOTtoxic vote from {user}!")
	else:
		return False

def _start_toxic_poll():
	global toxic_poll
	global toxic_votes
	global nottoxic_votes
	global voters
		
	send_message("Poll starting! Type !votetoxic or !votenice to vote on whether the previous game was toxic or nice. Results in 60 seconds.")
	toxic_poll = True
	sleep(60)
	if toxic_poll: # toxicpoll can be cancelled externally, so only proceed if it wasn't
		toxic_poll = False
		if nottoxic_votes > 0 and toxic_votes > 0:
			toxic_percent    =    toxic_votes / (toxic_votes + nottoxic_votes)
			nottoxic_percent = nottoxic_votes / (toxic_votes + nottoxic_votes)
		else:
			if toxic_votes > 0:
				toxic_percent = 1
				nottoxic_percent = 0
			else:
				toxic_percent = 0
				nottoxic_percent = 0

		toxic_percent = round(100*toxic_percent)
		nottoxic_percent = round(100*nottoxic_percent)

		message = f"Toxicpoll results are in! Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%). "
		
		if nottoxic_votes > toxic_votes:
			send_message(message + "Chat votes that the game was NOT toxic! FeelsGoodMan ")
			send_message("!untoxic")
			log(f"Poll result: not toxic. Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)")

		elif toxic_votes > nottoxic_votes:
			send_message(message + "Chat votes that the game was TOXIC! FeelsBadMan ")
			send_message("!toxic")
			log(f"Poll result: TOXIC. Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)")
		else:
			send_message(message + "Poll was a draw! Chat can't make up its mind! kaywee1Wut ")
			log(f"Poll result: undecided. Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)")

		voters = set()
		toxic_votes = 0
		nottoxic_votes = 0

@is_command("Lets a user view their current permission")
def permission(message_dict):
	user = message_dict["display-name"].lower()
	user_permission = message_dict["user_permission"] 

	log(f"Sent permission to {user} - their permission is {user_permission.name} ({user_permission.value})")
	send_message(f"@{user}, your maximum permission is: {user_permission.name} (Level {user_permission.value})")

@is_command("Say hello!")
def hello(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	send_message(f"Hello, {user}! kaywee1AYAYA")
	log(f"Sent Hello to {user}")

@is_command("Roll one or more dice. Syntax: !dice [<number>[d<sides>]] e.g. `!dice 4` or `!dice 3d12`")
def dice(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	try:
		num = message.split(" ")[1]
		if "d" in num:
			num, sides = map(int, num.split("d"))
		else:
			num = int(num)
			sides = 6
	except (IndexError, ValueError):
		num = 1
		sides = 6

	if num > 10:
		num = 10

	if sides > 120:
		sides = 120
			
	sum = 0
	rolls = []

	for _ in range(num):
		roll = random.choice(range(1,sides+1))
		sum += roll
		rolls.append(roll)

	if num == 1:
		send_message(f"{user} rolled a dice and got a {str(sum)}!")
		log(f"Sent a dice roll of {sum} to {user}")
	else:
		send_message(f"{user} rolled {num} dice and totalled {str(sum)}! {str(tuple(rolls))}")
		log(f"Sent {num} dice rolls to {user}, totalling {sum}")

@is_command("Pulls from the power of the cosmos to predict your fortune.")
def fortune(message_dict):
	user = message_dict["display-name"].lower()

	try:
		target = message_dict["message"].split(" ")[1].lower().replace("@", "")
	except (KeyError, IndexError):
		target = user

	fortune = random.choice(fortunes)
	send_message(f"@{target}, your fortune is: {fortune}")
	log(f"Sent fortune to {user}")

@is_command("Shows the current followgoal.")
def followgoal(message_dict):
	user = message_dict["display-name"].lower()

	goal = get_data("followgoal")
		
	url = "https://api.twitch.tv/helix/users/follows?to_id=" + kaywee_channel_id
	bearer_token = get_data("app_access_token")

	authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + bearer_token}
	try:
		data = requests.get(url, headers=authorisation_header).json()
		followers = data["total"]
		followers_left = goal - followers
		if followers_left > 0:
			send_message(f"Kaywee has {followers:,} followers, meaning there are only {followers_left:,} more followers until we hit our goal of {goal:,}! kaywee1AYAYA")
			log(f"Sent followergoal of {followers_left} to {user} (currently {followers:,}/{goal:,})")
		else:
			send_message(f"The follower goal of {goal:,} has been met! We now have {followers:,} followers! kaywee1AYAYA")
			log(f"Sent followergoal has been met to {user} ({followers:,}/{goal:,})")
			while goal <= followers:
				goal += 500
			set_data("followgoal", goal)
			log(f"Increased followgoal to {goal:,}")

			followers_left = goal - followers
			send_message(f"Our new follow goal is {goal:,}! kaywee1AYAYA")
	except (ValueError, KeyError) as ex:
		print("Error in followgoal command: " + ex)

def _tofreedom(unit, quantity):
	"""Intentionally doesn't handle errors"""

	unit = unit.lower()

	if unit == "c":
		far = round((quantity * (9/5)) + 32, 1) # F = (C × 9/5) + 32
		return ("f", far)
	elif unit == "cm":
		inches = round(quantity / 2.54, 2)
		return ("in", inches)
	elif unit == "kg":
		labs = round(quantity * 2.204, 2)
		return ("lb", labs)
	elif unit == "m":
		ft = round(quantity * 3.28084, 2)
		return ("ft", ft)
	elif unit == "km":
		mi = round(quantity / 1.60934, 2)
		return ("mi", mi)
	elif unit.upper() in currencies:
		dlr = round(quantity * _get_currencies(base=unit, convert_to="USD"), 2)
		return ("USD", dlr)
	elif unit == "ml":
		pt = round(quantity / 568.261, 3)
		return("pints", pt)
	elif unit == "cl":
		ml = cl * 10
		return ("ml", ml)
	elif unit == "g":
		oz = round(quantity/28.3495, 1)
		return ("oz", oz)

	return -1

def _unfreedom(unit, quantity):
	unit = unit.lower()

	if unit == "f":
		cel = round((quantity-32) * (5/9), 1) # C = (F − 32) × 5/9
		return ("c", cel)
	elif unit == "in":
		cm = round(quantity * 2.54, 2)
		return ("cm", cm)
	elif unit == "lb":
		kg = round(quantity / 2.204, 2)
		return ("kg", kg)
	elif unit == "ft":
		m = round(quantity / 3.28084, 2)
		return ("m", m)
	elif unit == "mi":
		km = round(quantity * 1.60934, 2)
		return ("km", km)
	elif unit == "usd":
		result = round(quantity * _get_currencies(base="USD", convert_to="GBP"), 2)
		return ("GBP", result)
	elif unit == "pt":
		ml = round(quantity * 568.261, 1)
		return("ml", ml)
	elif unit == "oz":
		g = round(quantity*28.3495, 1)
		return ("g", g)

	return -1

def _get_currencies(base="USD", convert_to="GBP"):
	base = base.upper()
	convert_to = convert_to.upper()

	result = requests.get(f"http://api.exchangeratesapi.io/v1/latest?access_key={exchange_API_key}").json()
	rates = result["rates"]
	if base in rates and convert_to in rates:

		return rates[convert_to] / rates[base]
	else:
		raise ValueError("Currency not found.")

@is_command("Convert metric units into imperial. Syntax: !tofreedom <quantity><unit> e.g. `!tofreedom 5kg`")
def tofreedom(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	if message == "!tofreedom tea":
		send_message('"Dinner"')
		return

	try:
		input = message.split(" ")[1]
	except (ValueError, IndexError):
		send_message("You have to provide something to convert..!")

	unit = ""

	while input[-1] not in "0123456789": 
		if input[-1] != " ":
			unit = input[-1] + unit  # e.g. cm or kg
		input = input[:-1]
		if len(input) == 0:
			send_message("You have to provide a quantity to convert.")
			return False

	try:
		quantity = float(input)
	except (ValueError):
		send_message("That.. doesn't look like a number. Try a number followed by a unit, e.g. '5cm' or '12kg'.")
		return False

	try:
		free_unit, free_quantity = _tofreedom(unit, quantity)
	except (ValueError, TypeError):
		send_message("Sorry, I don't recognise that metric unit. :(")
		return False

	if free_quantity == int(free_quantity): # if the float is a whole number
		free_quantity = int(free_quantity)  # convert it to an int (i.e. remove the .0)

	if quantity == int(quantity): # ditto
		quantity = int(quantity)

	send_message(f"{quantity:,}{unit} in incomprehensible Freedom Units is {free_quantity:,}{free_unit}.")
	log(f"Tofreedomed {quantity}{unit} for {user}")

@is_command("Convert imperial units into metric. Syntax: !unfreedom <quantity><unit> e.g. `!tofreedom 5lb`")
def unfreedom(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	try:
		input = message.split(" ")[1]
	except (ValueError, IndexError):
		send_message("You have to provide something to convert..!")

	unit = ""

	while input[-1] not in "0123456789": 
		if input[-1] != " ":
			unit = input[-1] + unit  # e.g. cm or kg
		input = input[:-1]
		if len(input) == 0:
			send_message("You have to provide a quantity to convert.")
			return False

	try:
		quantity = float(input)
	except (ValueError):
		send_message("That.. doesn't look like a number. Try a number followed by a unit e.g. '5ft' or '10lb'.")
		return False

	try:
		sensible_unit, sensible_quantity = _unfreedom(unit, quantity)
	except (ValueError, TypeError):
		send_message("I don't recognise that imperial unit. Sorry! :( PepeHands")
		return False

	if sensible_quantity == int(sensible_quantity): # if the float is a whole number
		sensible_quantity = int(sensible_quantity) # convert it to an int (i.e. remove the .0)

	if quantity == int(quantity): # ditto
		quantity = int(quantity) 

	send_message(f"{quantity}{unit} in units which actually make sense is {sensible_quantity}{sensible_unit}.")
	log(f"Unfreedomed {quantity}{unit} for {user}")

@is_command("Looks up who gifted the current subscription to the given user. Syntax: !whogifted [@]kaywee")
def whogifted(message_dict):
	global subscribers

	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	try:
		target = message.split(" ")[1]
	except IndexError: # no target specified
		target = user
		
	if target[0] == "@": # ignore @ tags
		target = target[1:]
		
	target = target.lower()

	if target in subscribers:
		if subscribers[target]["is_gift"]:
			try:
				gifter = subscribers[target]["gifter_name"]
			except KeyError:
				send_message(f"Error - this is a gifted sub but there is no record of the gifter. WeirdChamp")
				return False
			send_message(f"@{target}'s current subscription was gifted to them by @{gifter}! Thank you! kaywee1AYAYA ")
			log(f"Sent whogifted (target={target}, gifter={gifter}) in response to {user}.")
		else:
			send_message(f"@{target} subscribed on their own this time. Thank you! kaywee1AYAYA ")
			log(f"Sent whogifted ({target} subbed on their own) in response to {user}.")
	else:
		send_message(f"@{target} is not a subscriber. FeelsBadMan")
		log(f"Sent whogifted ({target} is not a subscriber) in response to {user}.")

@is_command("Looks up how many of the currently-active subscriptions were gifted by the given user. Syntax: !howmanygifts [@]kaywee")
def howmanygifts(message_dict):
	global subscribers

	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	try:
		target = message.split(" ")[1]
	except IndexError: # no target specified
		target = user
		
	if target[0] == "@": # ignore @ tags
		target = target[1:]
		
	target = target.lower()
	count = 0
	recipients = ""
		
	for sub in subscribers:
		if subscribers[sub]["gifter_name"].lower() == target:
			recipients += sub + ", "
			count += 1
		
	if count == 0:
		send_message(f"None of the current subscribers were gifted by {target}.")
		log(f"Sent {target} has no gifted subs, in response to {user}.")
	else:
		recipients = recipients[:-2]
		message = f"{target} has gifted {count} of the current subscriptions to: {recipients}. Thanks for the support <3 kaywee1AYAYA"
		if len(message) > 500: # twitch max length
			message = f"{target} has gifted {count} of the current subscriptions! Thanks for the support <3 kaywee1AYAYA"
		send_message(message)
		log(f"Sent {target} has {count} gifted subs, in response to {user}.")

@is_command("Shows a timer until the end of Season 26.")
def endofseason(message_dict):
	#user = message_dict["display-name"].lower()
	try:
		time_left = timeuntil(1625162400)
		send_message(f"Season 28 ends in {time_left}")
	except ValueError:
		send_message("Season 28 has now ended!")

@is_command("Translates a Spanish message into English. Syntax: `!toenglish hola` OR to translate a user's last message, `!toenglish @toniki`")
def toenglish(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	phrase = " ".join(message.split(" ")[1:])

	english = ""
	if phrase.lower() in ["robokaywee", user, "@" + user, ""]:
		return False
	if phrase[0] == "@" and len(phrase.split(" ")) == 1: # parameter is really a username
		try:
			target = phrase[1:].lower()
			phrase = last_message[target]
			english = target + ": "
		except KeyError:
			return False

	#phrase = phrase.replace(".", ",").replace("?", ",").replace("!", ",") # for some reason it only translates the first sentence

	english += translator.translate(phrase, src="es", dest="en").text

	send_message(english)
	log(f"Translated \"{phrase}\" into English for {user}: it says \"{english}\"")

@is_command("Translates an English message into Spanish. Syntax: `!tospanish hello` OR to translate a user's last message, `!tospanish @kaywee`")
def tospanish(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	phrase = " ".join(message.split(" ")[1:])

	spanish = ""
	if phrase.lower() in ["robokaywee", user, "@" + user, ""]:
		return False
	if phrase[0] == "@" and len(phrase.split(" ")) == 1: # parameter is really a username
		try:
			target = phrase[1:].lower()
			phrase = last_message[target]
			spanish = target + ": "
		except KeyError:
			return False

	#phrase = phrase.replace(".", ",").replace("?", ",").replace("!", ",") # for some reason it only translates the first sentence
	
	spanish += translator.translate(phrase, src="en", dest="es").text

	send_message(spanish)
	log(f"Translated \"{phrase}\" into Spanish for {user}: it says \"{spanish}\"")

@is_command("Translates a message from one language to another, powered by Google Translate. Languages are specified as a two-letter code, e.g. en/es/nl/fr. Syntax: !translate <source_lang> <dest_lang> <message>")
def translate(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	try:
		source = message.split(" ")[1]
		dest = message.split(" ")[2]
		phrase = " ".join(message.split(" ")[3:]).replace(".", ",").replace("?", ",").replace("!", ",")
	except IndexError:
		send_message("Syntax Error. Usage: !translate <source_lang> <dest_lang> <text>")
	
	output = ""
	if phrase.lower() in ["robokaywee", user, "@" + user, ""]:
		return False
	if phrase[0] == "@" and len(phrase.split(" ")) == 1: # parameter is really a username
		try:
			target = phrase[1:].lower()
			phrase = last_message[target]
			output = target + ": "
		except KeyError:
			return False
	try:
		# phrase = phrase.replace(".", ";").replace("?", ";").replace("!", ";") # for some reason it only translates the first sentence
		output += translator.translate(phrase, src=source, dest=dest).text
		send_message(output)
		log(f"Translated \"{phrase}\" into {dest} for {user}: it says \"{output}\"")
	except Exception as ex:
		send_message("Translation failed. FeelsBadMan")
		return

@is_command("Shows the user who most recently raided, and the time of the raid.")
def lastraid(message_dict):
	user = message_dict["display-name"].lower()

	raid_data = eval(get_data("last_raid"))

	name    = raid_data["raider"]
	viewers = raid_data["viewers"]
	time    = raid_data["time"]

	date_num = datetime.utcfromtimestamp(time).strftime('%d') # returns a string with date number, e.g. "19"
	if date_num in ["01", "21", "31"]:
		suffix = "st"
	elif date_num in ["02", "22"]:
		suffix = "nd"
	elif date_num in ["03", "23"]:
		suffix = "rd"
	else:
		suffix = "th"

	date_num = str(date_num).lstrip("0")
	time_str = datetime.utcfromtimestamp(time).strftime("%A " + date_num + suffix + " of %B at %H:%M UTC")

	plural = "" if viewers == 1 else "s"

	send_message(f"The latest raid was by {name}, who raided with {viewers} viewer{plural} on {time_str}!")
	log(f"Sent last raid to {user}: it was {name}, who raided with {viewers} viewer{plural} on {time_str}!")

@is_command("Changes the colour of the bot's username. Syntax: !setcolour [<colour>|random] e.g.`!setcolour HotPink` OR `!setcolour random`")
def setcolour(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	try:
		colour = message.split(" ")[1]
	except(ValueError, IndexError):
		colour = "default"

	if colour.lower() in ["random", "default", "blue","blueviolet","cadetblue","chocolate","coral","dodgerblue","firebrick","goldenrod","green","hotpink","orangered","red","seagreen","springgreen","yellowgreen"]:
		valid = True
	else:
		valid = False

		# ONLY WORKS WITH TWITCH PRIME:
		#if colour[0] == "#": 
		#	if len(colour) == 7:
		#		for c in colour[1:].lower():
		#			if c not in "0123456789abcdef":
		#				valid = False
		#				break
		#		else:
		#			valid=True

	if valid:
		if colour == "default":
			colour = "HotPink"

		if colour == "random":
			colours = ["blue","blueviolet","cadetblue","chocolate","coral","dodgerblue","firebrick","goldenrod","green","hotpink","orangered","red","seagreen","springgreen","yellowgreen"]
			new_colour = random.choice(colours)
			send_message("/color " + new_colour, False)
			sleep(0.9)
			set_data("current_colour", new_colour)
			if user != "Timed Event":
				send_message(f"The Robocolour was randomly updated to {new_colour}! kaywee1AYAYA")
			log(f"Colour was randomly updated to {new_colour} in response to {user}")
		else:
			send_message("/color " + colour, False)
			sleep(0.9)
			set_data("current_colour", colour)
			send_message(f"The Robocolour was updated to {colour}! kaywee1AYAYA")
			log(f"Colour was updated to {colour} in response to {user}")
	else:
		send_message(f"@{user} That colour isn't right. Valid colours are: random, default, blue, blueviolet, cadetblue, chocolate, coral, dodgerblue, firebrick, goldenrod, green, hotpink, orangered, red, seagreen, springgreen, yellowgreen")

@is_command("Rainbows the message into the chat. (big spam warning so 12 chars max) Syntax: `!rainbow hello`")
def rainbow(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	try:
		word = " ".join(message.split(" ")[1:])[:15] # 15 chr limit
	except IndexError:
		return False

	if word == "":
		return False

	for colour in ["red", "coral", "goldenrod", "green", "seagreen", "dodgerblue", "blue", "blueviolet", "hotpink"]:
		send_message(f"/color {colour}", False)
		sleep(0.12)
		send_message(word, False)
		sleep(0.12)

	current_colour = get_data("current_colour")
	sleep(1)
	send_message(f"/color {current_colour}")

@is_command("Shows all of the possible username colours (for non-prime users) (big spam warning)")
def allcolours(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	for colour in ['blue', 'blueviolet', 'cadetblue', 'chocolate', 'coral', 'dodgerblue', 'firebrick', 'goldenrod', 'green', 'hotpink', 'orangered', 'red', 'seagreen', 'springgreen', 'yellowgreen']:
		send_message(f"/color {colour}", False)
		sleep(0.1)
		send_message(f"This is {colour}", False)
		sleep(0.1)

	current_colour = get_data("current_colour")
	send_message(f"/color {current_colour}")

def _start_timer(user, time_in, reminder, self):
	global timers

	hours = 0
	mins  = 0
	secs  = 0 # defaults

	time_str = time_in[:]

	if "h" in time_str:
		try:
			hours = int(time_str.split("h")[0])
			time_str = time_str.split("h")[1]
		except:
			send_message(f"@{user} sorry, I don't recognise that format :(")
			timers.remove(self)
			return False

	if "m" in time_str:
		try:
			mins = int(time_str.split("m")[0])
			time_str = time_str.split("m")[1]
		except:
			send_message(f"@{user} sorry, I don't recognise that format :(")
			timers.remove(self)
			return False

	if "s" in time_str:
		try:
			secs = int(time_str.split("s")[0])
			time_str = time_str.split("s")[1]
		except:
			send_message(f"@{user} sorry, I don't recognise that format :(")
			timers.remove(self)
			return False

	if time_str != "": # or secs >= 60 or mins >= 60 or hours > 24:
		send_message("That time doesn't look right.")
		timers.remove(self)
		return False

	timer_time = 60*60*hours + 60*mins + secs

	if timer_time < 30:
		send_message("The timer must be for at least 30 seconds.")
		timers.remove(self)
		return False

	reminder_type = "reminder" if reminder != "" else "timer"
	start_type = "is set" if reminder_type == "reminder" else "has started"

	send_message(f"@{user} - your {time_in} {reminder_type} {start_type}!")

	log(f"Started {time_in} timer for {user}.")
	sleep(timer_time)

	if not self.deleted:
		if reminder_type == "reminder":
			send_message(f"@{user} Reminder! {reminder}")
		else:
			send_message(f"@{user} your {time_in} timer is up!")

		log(f"{user}'s {timer_time} timer expired.")

	with suppress(KeyError):
		timers.remove(self)

@is_command("Starts a timer, after which the bot will send a reminder message in chat. Syntax: `!timer 1h2m3s [<message>]`")
def timer(message_dict):
	global timers

	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	try:
		time_str = message.split(" ")[1]
	except:
		return False

	try:
		reminder = " ".join(message.split(" ")[2:])
	except:
		reminder = ""

	timer_thread = Thread(target=_start_timer, name=f"{time_str} timer for {user}.")
	timer_thread.deleted = False
	timer_thread._args = (user,time_str,reminder,timer_thread) # I'm not *really* supposed to access private attributes, but hey, this is python so anything goes. And Thread doesn't allow setting the args outside the initialiser.
	timer_thread.start()

	timers.add(timer_thread)

@is_command("Cancel all of your current timers.")
def canceltimer(message_dict):
	global timers

	user = message_dict["display-name"].lower()
	num_timers = 0

	for timer in set(timers):
		if f"for {user}." in timer.name:
			timer.deleted = True
			num_timers += 1
			timers.remove(timer)

	if num_timers == 0:
		send_message(f"@{user} You don't have any timers.")
		return False
	elif num_timers == 1:
		send_message(f"@{user} Your timer has been stopped.")
		log(f"Stopped {user}'s timer.")
	else:
		send_message(f"@{user} Your {num_timers} timers have been stopped.")
		log(f"Stopped {user}'s {num_timers} timers.")

@is_command("Shows how many times a command has been used. Syntax: `!uses toenglish`")
def uses(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	thing = message.split(" ")[1]

	# is `thing` a command?
	if thing in command_dict:
		times_used = command_dict[thing].get("uses", 0)
		if times_used != 1:
			send_message(f"The {thing} command has been used {times_used} times.")
			log(f"Sent uses to {user}: command {thing} has been used {times_used} times.")
		else:
			send_message(f"The {thing} command has been used {times_used} time.")
			log(f"Sent uses to {user}: command {thing} has been used {times_used} time.")
	else:
		# is `thing` an emote?
		emote_uses = _emote_uses(thing)
		if emote_uses > 0:
			send_message(f"The {thing} emote has been used {emote_uses:,} times.")
			log(f"Sent uses to {user}: emote {thing} has been used {emote_uses:,} times.")
		else:
			send_message(f"{thing} is not recognised.")

def _nochat_mode():
	global nochat_on
	nochat_on = True

	duration = 12*60 # 12 mins
	check_period = 10 # secs
	for secs in range(0, duration, check_period):
		if not nochat_on: # nochat mode gets turned off externally
			break

		sleep(check_period)
	else:
		nochat_on = False # turn nochat mode off after the duration


@is_command("Turns on nochat mode: users who mention kaywee will receive a notification that kaywee isn't looking at chat")
def nochaton(message_dict):
	user = message_dict["display-name"].lower()

	global nochat_on
	if not nochat_on:
		nochat_thread = Thread(target=_nochat_mode)
		nochat_thread.start()
		send_message("Nochat mode is now on.")
		log(f"Nochat mode is now on in response to {user}.")
	else:
		send_message("Nochat mode is already on.")

@is_command("Turns off nochat mode")
def nochatoff(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	global nochat_on
	nochat_on = False
	send_message("Nochat mode is now off.")
	log(f"{user} turned off Nochat mode.")

@is_command("View the current commands list.")
def rcommands(message_dict):
	user = message_dict["display-name"].lower()
	
	send_message("The RoboKaywee commands list is here: https://old.reddit.com/r/RoboKaywee/wiki/commands")
	log(f"Sent commands list to {user}")

@is_command("Provides either one or two definitions for an English word.")
def define(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	try:
		word = message.split(" ")[1]
		assert word != ""
	except (IndexError, AssertionError):
		return False

	definitions = dic.meaning(word)
	try:
		nouns = definitions.get("Noun", [])
		adjs = definitions.get("Adjective", [])
		vers = definitions.get("Verb", [])
		advs = definitions.get("Adverb", [])
	except AttributeError:
		send_message("I don't know that word.")
	else:
		definitions = list(adjs+vers+advs+nouns)

		if len(definitions) == 1:
			send_message(f"The definition of {word} is: {definitions[0]}")
		else:
			send_message(f"The definitions of {word} are: \"{definitions[0]}\" OR \"{definitions[1]}\"")

@is_command("Lets mods ban a user, for mobile mods.")
def rban(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	target = message.split(" ")[1]
	send_message(f"/ban {target}")
	log(f"Banned user {target} in response to {user}")

@is_command("Lets mods timeout a user, for mobile mods.")
def rtimeout(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	target = message.split(" ")[1]

	try:
		duration = int(message.split(" ")[2])
	except (ValueError, IndexError):
		duration = 600

	send_message(f"/timeout {target} {duration}")
	log(f"Timed out user {target} for {duration} seconds, in response to {user}")

@is_command("Repeats the phrase in chat.")
def echo(message_dict):
	user = message_dict["display-name"].lower()

	if user == "theonefoster":
		message = message_dict["message"]

		phrase = " ".join(message.split(" ")[1:])
		send_message(phrase, add_to_chatlog=True, suppress_colour=True)
		log(f"Echoed \"{phrase}\" for {user}.")
	else:
		return False

@is_command("Looks up the current World Day")
def worldday(message_dict):
	user = message_dict["display-name"].lower()
	
	page = requests.get("https://www.daysoftheyear.com/").text

	# flasgod don't judge me, I know this is wonky af
	# don't worry, I'm juding you enough for both of us -Moldar
	links_re = re.compile("<a.*?\/a>") # looks for <a> tags that also have a close tag
	links = [link for link in re.findall(links_re, page) if "www.daysoftheyear.com" in link and "class=\"js-link-target\"" in link] #"link" is the entire <a></a> tag

	day_re = re.compile("<.*?>([^<]*)<")# text between the tags
	world_day = re.search(day_re, links[0]).group(1).replace("&#8217;", "'") # first group of 0th match (0th group is the whole match, 1st group is between ())

	send_message(f"Happy {world_day}! (Source: https://www.daysoftheyear.com)" )
	log(f"Sent World Day ({world_day}) to {user}")

@is_command("Gamble the bot's fortunes away.")
def autogamble(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	if user == "flasgod":
		send_message("No. Make me.")
		log("Refused to gamble for flasgod KEKW")
		return

	try:
		amount = int(message.split(" ")[1])
	except (IndexError, ValueError):
		amount = 50

	if amount > 100:
		amount = 100

	send_message(f"!gamble {amount}")
	log(f"Gambled {amount} points in response to {user}.")

@is_command("Perform maths with the supreme calculation power of the bot. Syntax: !calculate [expression] e.g. `!calculate (2*3)**2-1`")
def calculate(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	
	try:
		calculation = " ".join(message.split(" ")[1:]) # everything after !calculate
	except (IndexError):
		return False

	calculation = calculation.replace(" ", "").replace("x", "*")

	if all(c in "0123456789+-*/()." for c in calculation): # don't allow invalid characters: unsanitised eval() is spoopy
		Thread(target=_perform_calculation, name=f"Calculation for {user}", args=(calculation,user)).start()
	else:
		send_message("That calculation doesn't look right. You can only use: 0-9 +-*/().")
		return False

def _perform_calculation(calculation,user):
	p = Process(target=_process_calculation, args=(calculation,user,bot,log))
	p.start()
	sleep(5)
	if p.is_alive():
		p.terminate() # needs to be a process so that it can be terminated
		send_message(f"@{user} That calculation timed out. Try something less complex.")
		log(f"Calculation {calculation} for {user} timed out.")

def _process_calculation(calculation, user, bot, log):
	try:
		result = eval(calculation) # make sure this is super sanitised!

		# only allow sensible calculation sizes. 100 trillion is arbitrary. This also throws TypeError if it's somehow not a number
		assert -100_000_000_000_000 < result < 100_000_000_000_000

		if int(result) != result: # result is not a numeric integer (may still be type float though, e.g. 10/2 = 5.0)
			result = round(result, 5)
		else:
			result = int(result)
	except:
		bot.send_message("That calculation didn't work.")
		return False
	else:
		prefix = random.choice([
		"The result is",
		"I make that",
		"The answer is",
		"That would be",
		"It's",
		])
		bot.send_message(f"{prefix} {result}")
		log(f"Calculated {calculation} for {user}: answer is {result}")
		return True

@is_command("Adds spaces between your letters.")
def spaces(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	phrase = "".join(message.split(" ")[1:]) # chop off the !command
	target = ""

	if phrase[0] == "@" and len(phrase.split(" ")) == 1: # parameter is really a username
		phrase = phrase[1:].lower()
		target = phrase
		phrase = last_message.get(phrase, phrase)

	spaces = " ".join(phrase)
	send_message(spaces)
	if target == "":
		log(f"Added spaces to {user}'s message: {spaces}")
	else:
		log(f"Added spaces to {target}'s message in response to {user}: {spaces}")

@is_command("Talk like that one spongebob meme.")
def spongebob(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	phrase = " ".join(message.split(" ")[1:]) # chop off the !command
	target = ""

	if phrase[0] == "@" and len(phrase.split(" ")) == 1: # parameter is really a username
		phrase = phrase[1:].lower()
		target = phrase
		phrase = last_message.get(phrase, phrase)

	if len(phrase)%2 == 1: # length is odd
		phrase += " " # make its length even, for the zip() below

	# the python-y way
	#output = "".join(a.lower()+b.upper() for a,b in zip(phrase[::2], phrase[1::2]))

	# went back to the old way bc the python-y way doesn't ignore spaces.
	
	# the old way:
	even = True
	output = ""
	for c in phrase:
		if even:
			output += c.lower()
		else:
			output += c.upper()
		if c != " ":
			even = not even
	

	send_message(output)
	if target == "":
		log(f"Spongebobbed {user}'s message: {output}")
	else:
		log(f"Spongebobbed {target}'s message in response to {user}: {output}")

@is_command("Gets the current weather at a specific place. Defaults to metric but can use imperial with the 'imperial' parameter. Syntax: !weather <place> [imperial]. E.g. `!weather London` or `!weather Austin imperial`")
def weather(message_dict):
	global weather_API_key 
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	if message.split(" ")[-1].lower() in ["metric", "imperial"]:
		place = " ".join(message.split(" ")[1:-1]).title()
		units = message.split(" ")[-1].lower() # metric or imperial
	else:
		place = " ".join(message.split(" ")[1:]).title()
		units = "metric"

	latitude, longitude = _get_place_from_name(place) # get coordinates from place name

	if latitude is None or longitude is None:
		send_message("That place name wasn't found.")
		return False

	weather_url = "https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}&exclude={exclude}&appid={APIkey}&units={unittype}"
	weather_response = requests.get(weather_url.format(lat=latitude, lon=longitude, exclude="minutely,hourly,daily,alerts", APIkey=weather_API_key, unittype=units)).json()

	weather    = weather_response["current"]
	temp       = round(weather["temp"], 1)
	feels_like = round(weather["feels_like"], 1)
	try:
		description = weather["weather"][0]["description"]
	except:
		description = ""

	unit = "C" if units == "metric" else "F"

	output = f"In {place} the current temperature is {temp}°{unit} (feels like {feels_like}{unit})."
	if description:
		output += f" Overall: {description}."

	send_message(output)
	log(f"Sent weather report to {user} for {place}")

def _get_place_from_name(place):
	# memoisation function to only call the geo api for new place names.
	# if a new place name is seen, the coordinates are looked up from the api
	# if that name is seen in future, it is recalled from the memo cache

	with open("places.txt", "r", encoding="utf-8") as f:
		places = dict(eval(f.read()))

	if place not in places:
		print(f"Looking up new place name {place}")

		geocode_url = "https://geocode.xyz/{place}?json=1"
		geo_response = requests.get(geocode_url.format(place=place)).json()

		if not ("latt" in geo_response and "longt" in geo_response):
			return (None, None)

		places[place] = geo_response["latt"], geo_response["longt"]

		with open("places.txt", "w", encoding="utf-8") as f:
			f.write(str(places))

	return places[place]

@is_command("Cancels a Toxicpoll")
def cancelpoll(message_dict):
	user = message_dict["display-name"]

	global toxic_poll

	if toxic_poll:
		global voters
		global toxic_votes
		global nottoxic_votes

		toxic_poll = False
		voters = set()
		toxic_votes = 0
		nottoxic_votes = 0

		send_message("Toxicpoll cancelled.")
		log(f"Cancelled toxicpoll in response to {user}")
	else:
		send_message("There is no toxicpoll currently active.")
		return False

@is_command("Show the Spanish Word of the Day")
def wordoftheday(message_dict):
	user = message_dict["display-name"]

	with open("spanish.txt", "r", encoding="utf-8") as f:
		words = eval(f.read())

	wotd_time = get_data("wordoftheday_time")
	word_num = get_data("wordoftheday_index")

	if wotd_time is None or wotd_time < time()-12*60*60 or word_num is None:
		set_data("wordoftheday_time", time())
		word_num = random.randint(0, len(words))
		set_data("wordoftheday_index", word_num)

	spa, eng = words[word_num]
	if user == "Timed Event":
		tag = "@kaywee "
	else:
		tag = ""

	send_message(f"{tag}The Spanish Word of the Day is \"{spa}\", which means \"{eng}\"")
	log(f"Sent word of the Day to {user}: {spa} means {eng}")

@is_command("Show the price of bitcoin")
def btc(message_dict):
	user = message_dict["display-name"].lower()
	try:
		result = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot").json()
		value = float(result["data"]["amount"])
	except Exception as ex:
		log(f"Exception in btc: {str(ex)}")
		return False
	
	if not message_dict.get("suppress_log", False):
		log(f"Sent BTC of ${value:,} to {user}")
	send_message(f"Bitcoin is currently worth ${value:,}")

@is_command("Show the price of etherium")
def eth(message_dict):
	user = message_dict["display-name"].lower()
	try:
		result = requests.get("https://api.coinbase.com/v2/prices/ETH-USD/spot").json()
		value = float(result["data"]["amount"])
	except Exception as ex:
		log(f"Exception in eth: {str(ex)}")
		return False
	
	if not message_dict.get("suppress_log", False):
		log(f"Sent ETH of ${value:,} to {user}")

	send_message(f"Ethereum is currently worth ${value:,}")

@is_command("Show the price of Dogecoin")
def doge(message_dict):
	user = message_dict["display-name"].lower()
	try:
		result = requests.get("https://sochain.com/api/v2/get_price/DOGE/USD").json()
		value = float(result["data"]["prices"][0]["price"])
	except Exception as ex:
		log(f"Exception in eth: {str(ex)}")
		return False

	value = round(value * 100, 2)
	
	if not message_dict.get("suppress_log", False):	
		log(f"Sent DOGE of {value:,} cents to {user}")

	send_message(f"Dogecoin is currently worth {value:,} cents")

@is_command("Display Kaywee's real biological age")
def age(message_dict):
	ages = list(range(19,24)) + list(range(36,43))
	true_age = random.choice(ages)
	send_message(f"Kaywee is {true_age} years old.")

@is_command("Show how long you've been following")
def followtime(message_dict):
	user = message_dict["display-name"].lower()

	try:
		target = message_dict["message"].split(" ")[1].lower().replace("@", "")
	except (KeyError, IndexError):
		target = user

	with open("followers.txt", "r", encoding="utf-8") as f:
		try:
			followers = dict(eval(f.read()))
		except Exception as ex:
			log("Exception reading followers in followtime command: " + str(ex))
			followers = {}

	if target in followers:
		follow_time = time() - datetime.strptime(followers[target], "%Y-%m-%dT%H:%M:%SZ").timestamp()
		duration = seconds_to_duration(follow_time)
		send_message(f"{target} followed Kaywee {duration} ago.")
	else:
		send_message(f"{target} is not following Kaywee. FeelsBadMan")

@is_command("Predict how OW2 will work.")
def ow2(message_dict):
	user = message_dict["display-name"].lower()

	with open("ow2.txt", "r") as f:
		lines = f.read().split("\n")

	ow2_prediction = random.choice(lines)
	send_message(ow2_prediction)
	log(f"Sent OW2 in response to {user}: {ow2_prediction}")

@is_command("Look up the top definition of a word on Urban Dictionary. Usage: !urban <word> [definition number]. e.g. `!urban twitch 2`")
def urban(message_dict):
	message = message_dict["message"]
	user = message_dict["display-name"]
	num = 0

	try:
		term = " ".join(message.split(" ")[1:])
	except:
		send_message("Syntax error.")
		log(f"Syntax error in Urban: message was {message}")
		return False

	try:
		num = int(term.split(" ")[-1]) - 1
		assert 0 < num < 100
	except:
		num = 0
	else:
		term = " ".join(term.split(" ")[:-1])

	try:
		result = requests.get(f"http://api.urbandictionary.com/v0/define?term={term}")
		definition = result.json()["list"][num]["definition"]
		assert definition != ""
	except:
		send_message("No definition found :( FeelsBadMan")
		log(f"No Urban definition found for {term} in response to {user}")
		return True

	definition = definition.replace("[", "").replace("]", "")
	if " " in term:
		url_term   = term.replace(" ", "%20")
		url_suffix = f"define.php?term={url_term}"
	else:
		url_suffix = term # it seems to accept just /word at the end as long as there are no spaces.. so this is smaller

	# url looks like https://www.urbandictionary.com/define.php?term=term
	# but this is shorter and works too: www.urbandictionary.com/term
	chat_url = f"www.urbandictionary.com/{url_suffix}"
	suffix = f" - Source: {chat_url}"
	max_len = 500-len(suffix)
	definition = definition[:max_len]

	send_message(f"{definition}{suffix}")
	log(f"Sent Urban definition of {term} to {user} - it means {definition}")

def _chatstats(key):
	# valid keys:
	assert key in ['channel', 'totalMessages', 'chatters', 'hashtags', 'commands', 'bttvEmotes', 'ffzEmotes', 'twitchEmotes']

	url = "https://api.streamelements.com/kappa/v2/chatstats/kaywee/stats"
	result = requests.get(url).json()

	return result[key]

@is_command("Show the total number of messages ever sent in Kaywee's chat")
def totalmessages(message_dict):
	user = message_dict["display-name"].lower()

	messages = int(_chatstats("totalMessages")) + 1
	send_message(f"This is message number {messages:,} to be sent in Kaywee's chat. Source: https://stats.streamelements.com/c/kaywee")
	log(f"Sent totalmessages of {messages:,} to {user}")

@is_command("Show the total number of messages sent in Kaywee's chat by a given user. Syntax: !chats [@]<user>, e.g. `!chats @kaywee`")
def chats(message_dict):
	user = message_dict["display-name"].lower()

	try:
		target = message_dict["message"].split(" ")[1].lower().replace("@", "")
	except (KeyError, IndexError):
		target = user

	chatters = _chatstats("chatters")

	for chatter in chatters:
		name, chats = chatter["name"], chatter["amount"]
		if name == target:
			break
	else: # name not found
		send_message(f"User not found in top 100 chatters - use !chatstats for full info.")
		return True

	if user == "theonefoster":
		chats += 5048 + 9920 # from AcesFullOfKings and theonefoster_

	send_message(f"{target} has sent {chats:,} messages in Kaywee's channel! Source: https://stats.streamelements.com/c/kaywee")
	log(f"Sent {target}'s chat count of {chats:,} to {user}")

@is_command("Show the current BTTV emotes.")
def bttv(message_dict):
	user = message_dict["display-name"].lower()
	bttv_emotes = _chatstats("bttvEmotes")
	emotes = [emoteinfo["emote"] for emoteinfo in bttv_emotes]
	
	first_500 = ""
	last_500 = ""

	for emote in emotes:
		# these show up in the API for some reason, but they're not valid emotes.. so exclude them here
		if emote not in ['BasedGod', 'Zappa', 'FeelsPumpkinMan', 'PedoBear', 'COGGERS', 'SillyChamp', 'monkaX', 'CCOGGERS', '5Head', 'TriDance', 'RebeccaBlack', 'peepoPANTIES']:
			if len(first_500 + " " + emote) < 500:
				if first_500:
					first_500 = first_500 + " " + emote
				else:
					first_500 = emote
			else:
				if last_500:
					last_500 = last_500 + " " + emote
				else:
					last_500 = emote

	send_message("The BTTV emotes in this channel are: ")
	send_message(first_500, suppress_colour=True)
	if last_500:
		send_message(last_500, suppress_colour=True)
	log(f"Sent BTTV emotes to {user}")

@is_command("Show the current FFZ emotes.")
def ffz(message_dict):
	user = message_dict["display-name"].lower()
	bttv_emotes = _chatstats("ffzEmotes")
	emotes = [emoteinfo["emote"] for emoteinfo in bttv_emotes]
	
	first_500 = ""
	last_500 = ""

	for emote in emotes:
		if len(first_500 + " " + emote) < 500:
			if first_500:
				first_500 = first_500 + " " + emote
			else:
				first_500 = emote
		else:
			if last_500:
				last_500 = last_500 + " " + emote
			else:
				last_500 = emote

	send_message("The FFZ emotes in this channel are: ")
	send_message(first_500, suppress_colour=True)
	if last_500:
		send_message(last_500, suppress_colour=True)
	log(f"Sent BTTV emotes to {user}")

def _get_all_emotes():
	global all_emotes
	url = "https://api.streamelements.com/kappa/v2/chatstats/kaywee/stats"
	result = requests.get(url).json()

	all_emotes = [(emote_info["emote"], emote_info["amount"]) for emote_info in result.get("bttvEmotes", []) + result.get("ffzEmotes", []) + result.get("twitchEmotes", [])]
	all_emotes = dict(all_emotes) # dict of emote: uses

Thread(target=_get_all_emotes, name="Get_All_Emotes").start()

def _emote_uses(emote):
	global all_emotes
	if emote in all_emotes:
		_get_all_emotes() # update number of uses
		return all_emotes.get(emote, 0)
	else: 
		return 0

@is_command("Show the current stream title.")
def title(message_dict):
	url = "https://api.twitch.tv/helix/streams?user_id=" + kaywee_channel_id
	global authorisation_header

	bearer_token = get_data("app_access_token")
	authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + bearer_token}

	try:
		# if this call succeeds, streamer is Live. Exceptions imply streamer is offline (as no stream title exists)
		title = requests.get(url, headers=authorisation_header).json()["data"][0]["title"]
		send_message(f"The stream title is: {title}")
	except:
		send_message("There is no stream right now.")
		return True

@is_command("Look up a BattleTag's SR. Syntax: !sr <battletag> [<region>]. <Region> is one of us,eu,asia and defaults to `us`. Example usage: `!sr Kaywee#12345 us` OR `!sr Toniki#9876`")
def sr(message_dict):
	# uses https://ow-api.com/docs

	message = message_dict["message"]
	user = message_dict["display-name"].lower()

	Thread(target=_sr_thread, args=(message,user),name="SR Thread").start() # it can take up to 5s to get an API response. this way I lose the return value but oh well

def _sr_thread(message,user):
	try:
		battletag = message.split(" ")[1]
		assert "#" in battletag

		target = battletag.split("#")[0]
		number = int(battletag.split("#")[1])
	except:
		send_message("You have to provide a battletag in the format: Name#0000 (case sensitive!)")
		return True

	try:
		region = message.split(" ")[2].lower()
		assert region in ["na", "eu", "us", "asia"]
		if region == "na":
			region = "us"
	except:
		region = "us"

	battletag = battletag.replace("#", "-")

	url = f"https://ow-api.com/v1/stats/pc/{region}/{battletag}/profile"
	result = requests.get(url).json()

	if "error" in result:
		send_message(result["error"] + " (names are case sensitive!)")
		return True
	elif result["private"] is True:
		send_message("That profile is private! PepeHands")
		return True
	elif "ratings" in result:
		tank = 0
		support = 0
		dps = 0

		if not result["ratings"]:
			send_message("That account hasn't placed in Competitive yet!")
			return True

		for rating in result["ratings"]:
			if rating["role"] == "tank":
				tank = rating["level"]
			elif rating["role"] == "damage":
				dps = rating["level"]
			elif rating["role"] == "support":
				support = rating["level"]

		SRs = ""

		if tank > 0:
			SRs = "Tank: " + str(tank)

		if dps > 0:
			if SRs == "":
				SRs = "DPS: " + str(dps)
			else:
				SRs += " // DPS: " + str(dps)

		if support > 0:
			if SRs == "":
				SRs = "Support: " + str(support)
			else:
				SRs += " // Support: " + str(support)

		if SRs != "":
			send_message(f"{target}'s SRs are: {SRs}")
			log(f"Sent SR to {user}: {target}'s SRs are: {SRs}")
			return True
		else:
			send_message(f"No SRs were found.")
			return True

	elif "rating" in result:
		if result["rating"] > 0:
			send_message(f"{target}'s SR is {result['rating']}")
			log(f"Sent SR to {user}: {target}'s SR is {result['rating']}")
			return True
		else:
			send_message(f"No SR was found.")
			return True
	
	send_message(f"Unable to find {target}'s SR rating. (Player names are case-sensitive!)")
	return True

@is_command("Checks whether a channel is live. Syntax: !islive [@]<channel> e.g. `!islive kaywee`")
def islive(message_dict):
	message = message_dict["message"]
	user = message_dict["display-name"].lower()

	channel = message.split(" ")[1]
	
	if channel[0] == "@":
		channel = channel[1:]

	url = "https://api.twitch.tv/helix/streams?user_login=" + channel
	bearer_token = get_data("app_access_token")
	authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + bearer_token}

	try:
		title = requests.get(url, headers=authorisation_header).json()["data"][0]["title"]
		send_message(f"{channel} is currently Live! www.twitch.tv/{channel}")
		log(f"Sent islive to {user}: {channel} is live.")
		return True
	except:
		send_message(f"{channel} is not currently Live.")
		log(f"Sent islive to {user}: {channel} is not live.")
		return True

@is_command("Send a message to another user the next time they appear in chat.")
def message(message_dict):
	global user_messages
	global usernames

	valid_chars = "abcdefghijklmnopqrstuvwxyz0123456789!£$%^&*()-=_+[]{};'#:@~,./<>? "

	try:
		message = message_dict["message"]
		user = message_dict["display-name"].lower()

		target = message.split(" ")[1]
		user_message = "".join(chr for chr in " ".join(message.split(" ")[2:]) if chr.lower() in valid_chars)

		if target[0] == "@":
			target = target[1:]

		target = target.lower()

	except Exception as ex:
		send_message("Invalid syntax. Your message won't be sent.")
		log(f"Didn't save user message for {user}: invalid syntax.")
		return False

	if target == user:
		send_message("Don't be silly, you can't message yourself.")
		log(f"Didn't save user message for {user}: tried to message self")
		return False
	elif target in ["robokaywee", "streamelements"]:
		send_message("Don't be silly, bots can't read. (At least, that's what we want you to think..!)")
		log(f"Didn't save user message for {user}: tried to message a bot")
		return False

	if target in usernames:
		if target in user_messages:
			send_message("That user already has a message waiting for them. To avoid spam, they can only have one at a time.")
			log(f"Didn't save user message for {user}: duplicate user ({target})")
			return False
		else:
			if any(x in user_message for x in ["extended", "warranty", "vehicle", "courtesy"]):
				send_message("That mesasge is invalid.")
				return False

			else:
				for msg in user_messages:
					if user_messages[msg]["from_user"] == user:
						send_message("You've already sent someone a message. To avoid spam, you can only send one at once.")
						return False

				user_messages[target] = {"from_user": user, "user_message": user_message}
				set_data("user_messages", user_messages)
				send_message(f"Your message was saved! It'll be sent next time {target} sends a chat.")
				log(f"Saved a user message from {user} to {target}.")
				return True
	else:
		send_message("That user has never been seen in chat. Messages can only be sent to known users.")
		log(f"Didn't save user message for {user}: unknown user ({target})")
		return False

@is_command("Get the number of viewers in a game category on Twitch. Example usage: `!viewers overwatch`")
def viewers(message_dict):
	Thread(target=_get_viewers_worker, args=(message_dict,), name="Get Viewers Worker").start()

def _get_viewers_worker(message_dict):
	user = message_dict["display-name"].lower()
	viewer_thread = Thread(target=_get_viewers, args=(message_dict,), name="Get Viewers")
	viewer_thread.start()

	sleep(3.5)
	if viewer_thread.is_alive():
		send_message(f"@{user} Give me a sec - it might take some time to get the viewers...")

def _get_viewers(message_dict):
	try:
		name = " ".join(message_dict["message"].split(" ")[1:])
	except:
		send_message("You must specify which game to search for.")
		return False

	user = message_dict["display-name"].lower()

	bearer_token = get_data("app_access_token")
	authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + bearer_token}

	games_url = f"https://api.twitch.tv/helix/games?name={name.replace(' ', '%20')}"
	try:
		id = requests.get(games_url, headers=authorisation_header).json()["data"][0]["id"]
	except:
		send_message("There was a problem. Maybe that game doesn't exist.")
		return False

	viewers = 0

	cursor = ""
	viewers_url = "https://api.twitch.tv/helix/streams?game_id={id}&first=100&after={cursor}"

	page = requests.get(viewers_url.format(id=id, cursor=cursor), headers=authorisation_header).json()
	cursor = page["pagination"]["cursor"]

	while cursor != "":
		for stream in page["data"]:
			viewers += stream["viewer_count"]

		page = requests.get(viewers_url.format(id=id, cursor=cursor), headers=authorisation_header).json()
		try:
			cursor = page["pagination"]["cursor"]
		except Exception as ex:
			break

	send_message(f"@{user} There are currently {viewers:,} people watching a {name} stream.")
	log(f"Sent viewers of {viewers:,} in category {name} to {user}.")
	return

@is_command("Check whether a website or service is down. Usage: `!isitdown apex legends` or `!isitdown twitch`")
def isitdown(message_dict):
	
	user = message_dict["display-name"].lower()

	try:
		name = " ".join(message_dict["message"].split(" ")[1:])
	except:
		send_message("You must provide a name to search for, e.g. !isitdown twitch")
		return False

	url = f"https://downdetector.com/status/{name.replace(' ', '-')}"
	user_agent = {'User-agent': 'Mozilla/5.0'}
	page = requests.get(url, headers=user_agent)

	if "User reports indicate possible problems" in page.text:
		send_message(f"It looks like {name} is having possible problems! Sadge Source: {url}")
		log(f"Sent isitdown to {user}: {name} is having problems.")
	elif "User reports indicate problems" in page.text:
		send_message(f"It looks like {name} is down! Sadge Source: {url}")
		log(f"Sent isitdown to {user}: {name} is down.")		
	elif "our systems have detected unusual traffic" in page.text:
		send_message(f"Oops, I can't check downdetector at the moment. Tell Foster he sucks at coding.")
		log(f"Anti-scraping from downdetector! Can't process command.")
		return False
	elif "no current problems" in page.text:
		send_message(f"Looks like {name} is up! FeelsGoodMan Source: {url}")
		log(f"Sent isitdown to {user}: {name} is up!")
	else:
		send_message(f"I'm not sure if {name} is down. Did you type it correctly? Try checking {url}")
		log(f"Sent isitdown to {user} - service {name} not found")

@is_command("Provides a reason as to why Kaywee is playing badly")
def excuse(message_dict):
	message = message_dict["message"]
	user = message_dict["display-name"].lower()

	try:
		param = message.split(" ")[1].lower()
	except:
		param = ""

	if param == "add":
		if message_dict["user_permission"] < permissions.Mod:
			send_message("Only mods can add excuses. Try using !excuse to see why Kaywee is playing badly.")
			return False
		excuse = " ".join(message.split(" ")[2:])
		with open("excuses.txt", "r", encoding="utf-8") as f:
			excuses = list(f.read().split("\n"))

		excuses.append(excuse)

		with open("excuses.txt", "w", encoding="utf-8") as f:
			f.write("\n".join(excuses))

		responses = ["Ahh that explains a lot.",
					 "Oh. Does her duo know this?",
					 "Oh, I was wondering what was going on."]

		send_message(random.choice(responses))
		log(f"Added excuse from {user}: {excuse}")
	else:
		with open("excuses.txt", "r", encoding="utf-8") as f:
			excuses = f.read().split("\n")

		excuse = random.choice(excuses)
		send_message(excuse)
		log(f"Sent excuse to {user}: {excuse}")

@is_command("Show the colour you're currently using.")
def mycolour(message_dict):
	if "color" in message_dict:
		send_message(f"Your colour is {message_dict['color']}")
	else:
		send_message("I don't know what your colour is.")

@is_command("Check all the crypto prices.")
def crypto(message_dict):
	user = message_dict["display-name"].lower()
	message_dict["suppress_log"] = True
	btc(message_dict)
	eth(message_dict)
	doge(message_dict)
	log(f"Sent Crypto prices to {user}")

# Please, nobody copy this or use this...it's terrifying.
@is_command("Updates the RoboKaywee github with the current codebase.")
def commit(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	try:
		commit_message = " ".join(message.split(" ")[1:])
		assert commit_message != ""
	except:
		commit_message = "Bug Fixes and Performance Improvements"

	Thread(target=_commit_thread, args=(commit_message,)).start()
	send_message("The commit is running..")
	log(f"Commited to Git for {user}")

def _commit_thread(message):
	result = subprocess.run("commit.bat " + message, capture_output=True).returncode

	if result == 0:
		send_message(f"The commit was successful. https://github.com/theonefoster/RoboKaywee")
		log(f"The commit was successful")
	else:
		send_message(f"The commit failed with code {result}")
		log(f"The commit failed with code {result}")

@is_command("Appends a line of code to RoboKaywee's code")
def append(message_dict):
	message = message_dict["message"]
	user = message_dict["display-name"].lower()

	line = " ".join(message.split(" ")[1:])
	with open("commands.py", "a") as f:
		f.write("\n" + line)

	log(f"Appended {line} for {user}")
	send_message("Append was successful!")

# this is flasgod's comment, here forever as a sign of his contribution to the project

"""
@is_command("Restarts the bot.")
def restart(message_dict):
    #After like 15 mins of work I couldn't get this to work so for now it is undefined
    return False
    DETACHED_PROCESS = 0x00000008
    process = subprocess.Popen([sys.executable, "RoboKaywee.py"],creationflags=DETACHED_PROCESS)# .pid
    print(process)
    sleep(3) # give it time to fail if it's going to not start
    #if not process.is_alive:
    #    send_message("The restart failed.")
    #    return False
    #else:
    send_message("RoboKaywee has restarted.")
    exit()


def _start_bot():
	process = subprocess.Popen([sys.executable, "RoboKaywee.py"])
=======
import random
import requests
import re
import subprocess
import os
import sys

from time            import sleep, time
from datetime        import date, datetime
from fortunes        import fortunes
from threading       import Thread
from credentials     import kaywee_channel_id, robokaywee_client_id, exchange_API_key, weather_API_key 
from googletrans     import Translator
from multiprocessing import Process
from james           import seconds_to_duration, timeuntil
from contextlib      import suppress
#from james import translate as j_translate

from PyDictionary import PyDictionary
dic = PyDictionary()

timers = set()

def is_command(description=""):
	"""
	This is the decorator function which marks other functions as commands and sets their properties.
	"""
	def inner(func, description=description):
		func.is_command = True
		func.description = description
		return func
	return inner

"""
Each @is_command function is a command (!!), callable by sending "!<function_name>" in chat.
All replies will be sent in the bot's colour, using /me unless specified otherwise.
"""

currencies = {'CAD', 'HKD', 'ISK', 'PHP', 'DKK', 'HUF', 'CZK', 'GBP', 'RON', 'SEK', 'IDR', 'INR', 'BRL', 'RUB', 'HRK', 'JPY', 'THB', 'CHF', 'EUR', 'MYR', 'BGN', 'TRY', 'CNY', 'NOK', 'NZD', 'ZAR', 'USD', 'MXN', 'SGD', 'AUD', 'ILS', 'KRW', 'PLN'}

toxic_poll = False
toxic_votes = 0
nottoxic_votes = 0
voters = set()
translator = Translator(service_urls=['translate.googleapis.com','translate.google.com','translate.google.co.kr'])
all_emotes = [] # populated below

@is_command("Allows mods to add and edit existing commands. Syntax: !rcommand [add/edit/delete/options] <command name> <add/edit: <command text> // options: <[cooldown/usercooldown/permission]>>")
def rcommand(message_dict):
	"""
	format:
	!rcommand <action> <command> [<params>]

	examples:
	* add a text command:
		!rcommand add helloworld Hello World!
	* edit an existing text command:
		!rcommand edit helloworld Hello World Again!
	* delete a command:
		!rcommand delete helloworld
	* change command options:
		!rcommand options helloworld permission 10
		!rcommand options helloworld cooldown 60
		!rcommand options helloworld usercooldown 120
	* view current command details:
		!rcommand view helloworld
	"""
	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	user_permission = message_dict["user_permission"] 

	params = message.split(" ")[1:]
	try:
		action = params[0]
		command_name = params[1].lower()
	except IndexError:
		send_message("Syntax error.")
		return False

	if action == "edit":
		if command_name in command_dict:
			if not command_dict[command_name]["coded"] and "response" in command_dict[command_name]:
				response = " ".join(params[2:])
				if response[:4] == "/me ":
					response = response[4:] # trim the space too

				response = response.replace("|", "/") # pipes break the formatting on the reddit wiki

				command_dict[command_name]["response"] = response

				send_message(f"Command {command_name} has been updated.")
				write_command_data(force_update_reddit=True)
			else:
				send_message(f"The command {command_name} is not updatable.")
		else:
			send_message(f"No command exists with name {command_name}.")
	elif action == "options":
		try:
			option = params[2]
		except IndexError:
			send_message("Syntax error.")
			return False
		if option in ["globalcooldown", "cooldown"]: # assume "cooldown" means global cooldown
			try:
				cooldown = int(params[3])
				assert 0 <= cooldown <= 300
			except (ValueError, IndexError, AssertionError):
				send_message("Cooldown must be provided as an integer between 1 and 300 seconds.")
				return False

			if command_name  in command_dict:
				command_dict[command_name]["global_cooldown"] = cooldown
				write_command_data(force_update_reddit=True)
				log(f"{user} updated global cooldown on command {command_name} to {cooldown}")
				send_message(f"Global Cooldown updated to {cooldown} on {command_name}")
			else:
				send_message(f"No command exists with name {command_name}.")
		elif option == "usercooldown":
			try:
				cooldown = int(params[3])
				assert 0 <= cooldown <= 3600
			except (ValueError, IndexError, AssertionError):
				send_message("Cooldown must be provided as an integer between 1 and 3600 seconds.")
				return False

			command_dict[command_name]["user_cooldown"] = cooldown
			write_command_data(force_update_reddit=True)
			log(f"{user} updated user cooldown on command {command_name} to {cooldown}")
			send_message(f"User Cooldown upated to {cooldown} on {command_name}")
		elif option == "permission":
			try:
				permission = int(params[3])
			except (ValueError, IndexError):
				send_message("Permission must be an integer: 0=All, 4=Subscriber, 6=VIP, 8=Moderator, 10=Broadcaster, 12=Owner, 20=Disabled")
				return False

			if command_name in command_dict:
				for enum in permissions:
					if enum.value == permission:
						current_permission = command_dict[command_name]["permission"]
						if current_permission == 20:
							current_permission = 8

						if user_permission >= current_permission:
							command_dict[command_name]["permission"] = permission
							write_command_data(force_update_reddit=True)
							send_message(f"Permission updated to {enum.name} on command {command_name}")
							log(f"{user} updated permission on command {command_name} to {enum.name}")
							return True # also exits the for-loop
						else:
							send_message("You don't have permission to do that.")
							return False
				else:
					send_message("Invalid Permission: Use 0=All, 4=Subscriber, 6=VIP, 8=Moderator, 9=Owner, 10=Broadcaster, 20=Disabled")
					return False
			else:
				send_message(f"No command exists with name {command_name}.")
				return False
		else:
			send_message("Unrecognised option: must be permission, globalcooldown, or usercooldown")
			return False
	elif action in ["add", "create"]:
		if command_name not in command_dict:
			try:
				response = " ".join(params[2:])
				assert response != ""
			except (IndexError, AssertionError):
				send_message("Syntax error.")
				return False
			else:
				if response[:4] == "/me ":
					response = response[4:] # trim the space too
				response = response.replace("|", "/") # pipes break the formatting on the reddit wiki
				
				command_dict[command_name] = {'permission': 0, 'global_cooldown': 1, 'user_cooldown': 0, 'coded': False, 'uses':0, 'response': response}
				write_command_data(force_update_reddit=True)
				send_message("Added command " + command_name)
				log(f"{user} added command {command_name}")
		else:
			send_message("Command " + command_name + " already exists.")

	elif action in ["remove", "delete"]:
		if command_name in command_dict:
			if command_dict[command_name]["coded"] == False:
				del command_dict[command_name]
				write_command_data(force_update_reddit=True)
				send_message("Deleted command " + command_name)
				log(f"{user} deleted command {command_name}")
			else:
				send_message(f"You cannot delete the {command_name} command.")
		else:
			send_message(f"No command exists with name {command_name}.")
	#elif action == "alias": # ???
	#	pass
	elif action in ["view", "show"]:
		view_command = command_dict[command_name]

		usercooldown = view_command.get("user_cooldown"  , 0)
		cooldown     = view_command.get("global_cooldown", 0)
		coded        = view_command.get("coded"          , False)
		permission   = view_command.get("permission"     , 0)
		response     = view_command.get("response"       , "")

		permission_name = "Unknown"

		for enum in permissions:
			if enum.value == permission:
				permission_name = enum.name

		if coded or response == "":
			send_message(f"{command_name}: Permission: {permission_name}; Global Cooldown: {cooldown}; User Cooldown: {usercooldown}")
		else:
			send_message(f"{command_name}: Permission: {permission_name}; Global Cooldown: {cooldown}; User Cooldown: {usercooldown}; Response: {response}")

	else:
		send_message("Unrecognised action: must be add, remove, edit, options, view")

@is_command("Sends a triangle of emotes. Syntax: !triangle <emote> e.g. `!triangle LUL`")
def triangle(message_dict):
	global all_emotes
	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	emotes = message_dict["emotes"]

	params = message.split(" ")
	try:
		emote = params[1]
	except:
		return False

	valid_emote = emote in all_emotes

	if not valid_emote:
		try:
			emotes_in_msg = emotes.split("/")
			for e in emotes_in_msg:
				id, positions = e.split(":")
				start_pos, end_pos = positions.split(",")[0].split("-")
				if start_pos == "10":
					valid_emote = True
					break
		except:
			pass # emote stays not valid

	if not valid_emote:
		send_message("You can only triangle with an emote.")
		return False

	num = 3
		
	try:
		num = int(params[2])
	except IndexError:
		pass #leave it at 3
	except ValueError: #if conversion to int fails, e.g. int("hello")
		num = 3
			
	if emote != "":
		if num > 5:
			num = 5
		
		counts = list(range(1,num+1)) + list(range(1,num)[::-1])
		for count in counts:
			send_message((emote + " ") * count)
		log(f"Sent triangle of {emote} of size {num} to {user}")

@is_command("Begins a toxicpoll")
def toxicpoll(message_dict):
	global nochat_on
	global toxic_poll

	if not toxic_poll:
		nochat_on = False # game is over so turn off nochat mode
		Thread(target=_start_toxic_poll, name="Toxic Poll").start()

@is_command("Only allowed while a toxicpoll is active. Votes toxic.")
def votetoxic(message_dict):
	global toxic_poll
	global toxic_votes
	global voters

	user = message_dict["display-name"].lower()

	if toxic_poll and user not in voters:
		toxic_votes += 1
		voters.add(user)
		send_message(f"{user} voted toxic.")
		print(f"Toxic vote from {user}!")
	else:
		return False

@is_command("Only allowed while a toxicpoll is active. Votes nice.")
def votenice(message_dict):
	global toxic_poll
	global nottoxic_votes
	global voters

	user = message_dict["display-name"].lower()

	if toxic_poll and user not in voters:
		nottoxic_votes += 1
		voters.add(user)
		send_message(f"{user} voted NOT toxic.")
		print(f"NOTtoxic vote from {user}!")
	else:
		return False

def _start_toxic_poll():
	global toxic_poll
	global toxic_votes
	global nottoxic_votes
	global voters
		
	send_message("Poll starting! Type !votetoxic or !votenice to vote on whether the previous game was toxic or nice. Results in 60 seconds.")
	toxic_poll = True
	sleep(60)
	if toxic_poll: # toxicpoll can be cancelled externally, so only proceed if it wasn't
		toxic_poll = False
		if nottoxic_votes > 0 and toxic_votes > 0:
			toxic_percent    =    toxic_votes / (toxic_votes + nottoxic_votes)
			nottoxic_percent = nottoxic_votes / (toxic_votes + nottoxic_votes)
		else:
			if toxic_votes > 0:
				toxic_percent = 1
				nottoxic_percent = 0
			else:
				toxic_percent = 0
				nottoxic_percent = 0

		toxic_percent = round(100*toxic_percent)
		nottoxic_percent = round(100*nottoxic_percent)

		message = f"Toxicpoll results are in! Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%). "
		
		if nottoxic_votes > toxic_votes:
			send_message(message + "Chat votes that the game was NOT toxic! FeelsGoodMan ")
			send_message("!untoxic")
			log(f"Poll result: not toxic. Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)")

		elif toxic_votes > nottoxic_votes:
			send_message(message + "Chat votes that the game was TOXIC! FeelsBadMan ")
			send_message("!toxic")
			log(f"Poll result: TOXIC. Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)")
		else:
			send_message(message + "Poll was a draw! Chat can't make up its mind! kaywee1Wut ")
			log(f"Poll result: undecided. Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)")

		voters = set()
		toxic_votes = 0
		nottoxic_votes = 0

@is_command("Lets a user view their current permission")
def permission(message_dict):
	user = message_dict["display-name"].lower()
	user_permission = message_dict["user_permission"] 

	log(f"Sent permission to {user} - their permission is {user_permission.name} ({user_permission.value})")
	send_message(f"@{user}, your maximum permission is: {user_permission.name} (Level {user_permission.value})")

@is_command("Say hello!")
def hello(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	send_message(f"Hello, {user}! kaywee1AYAYA")
	log(f"Sent Hello to {user}")

@is_command("Roll one or more dice. Syntax: !dice [<number>[d<sides>]] e.g. `!dice 4` or `!dice 3d12`")
def dice(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	try:
		num = message.split(" ")[1]
		if "d" in num:
			num, sides = map(int, num.split("d"))
		else:
			num = int(num)
			sides = 6
	except (IndexError, ValueError):
		num = 1
		sides = 6

	if num > 10:
		num = 10

	if sides > 120:
		sides = 120
			
	sum = 0
	rolls = []

	for _ in range(num):
		roll = random.choice(range(1,sides+1))
		sum += roll
		rolls.append(roll)

	if num == 1:
		send_message(f"{user} rolled a dice and got a {str(sum)}!")
		log(f"Sent a dice roll of {sum} to {user}")
	else:
		send_message(f"{user} rolled {num} dice and totalled {str(sum)}! {str(tuple(rolls))}")
		log(f"Sent {num} dice rolls to {user}, totalling {sum}")

@is_command("Pulls from the power of the cosmos to predict your fortune.")
def fortune(message_dict):
	user = message_dict["display-name"].lower()

	try:
		target = message_dict["message"].split(" ")[1].lower().replace("@", "")
	except (KeyError, IndexError):
		target = user

	fortune = random.choice(fortunes)
	send_message(f"@{target}, your fortune is: {fortune}")
	log(f"Sent fortune to {user}")

@is_command("Shows the current followgoal.")
def followgoal(message_dict):
	user = message_dict["display-name"].lower()

	goal = get_data("followgoal")
		
	url = "https://api.twitch.tv/helix/users/follows?to_id=" + kaywee_channel_id
	bearer_token = get_data("app_access_token")

	authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + bearer_token}
	try:
		data = requests.get(url, headers=authorisation_header).json()
		followers = data["total"]
		followers_left = goal - followers
		if followers_left > 0:
			send_message(f"Kaywee has {followers:,} followers, meaning there are only {followers_left:,} more followers until we hit our goal of {goal:,}! kaywee1AYAYA")
			log(f"Sent followergoal of {followers_left} to {user} (currently {followers:,}/{goal:,})")
		else:
			send_message(f"The follower goal of {goal:,} has been met! We now have {followers:,} followers! kaywee1AYAYA")
			log(f"Sent followergoal has been met to {user} ({followers:,}/{goal:,})")
			while goal <= followers:
				goal += 500
			set_data("followgoal", goal)
			log(f"Increased followgoal to {goal:,}")

			followers_left = goal - followers
			send_message(f"Our new follow goal is {goal:,}! kaywee1AYAYA")
	except (ValueError, KeyError) as ex:
		print("Error in followgoal command: " + ex)

def _tofreedom(unit, quantity):
	"""Intentionally doesn't handle errors"""

	unit = unit.lower()

	if unit == "c":
		far = round((quantity * (9/5)) + 32, 1) # F = (C × 9/5) + 32
		return ("f", far)
	elif unit == "cm":
		inches = round(quantity / 2.54, 2)
		return ("in", inches)
	elif unit == "kg":
		labs = round(quantity * 2.204, 2)
		return ("lb", labs)
	elif unit == "m":
		ft = round(quantity * 3.28084, 2)
		return ("ft", ft)
	elif unit == "km":
		mi = round(quantity / 1.60934, 2)
		return ("mi", mi)
	elif unit.upper() in currencies:
		dlr = round(quantity * _get_currencies(base=unit, convert_to="USD"), 2)
		return ("USD", dlr)
	elif unit == "ml":
		pt = round(quantity / 568.261, 3)
		return("pints", pt)
	elif unit == "cl":
		ml = cl * 10
		return ("ml", ml)
	elif unit == "g":
		oz = round(quantity/28.3495, 1)
		return ("oz", oz)

	return -1

def _unfreedom(unit, quantity):
	unit = unit.lower()

	if unit == "f":
		cel = round((quantity-32) * (5/9), 1) # C = (F − 32) × 5/9
		return ("c", cel)
	elif unit == "in":
		cm = round(quantity * 2.54, 2)
		return ("cm", cm)
	elif unit == "lb":
		kg = round(quantity / 2.204, 2)
		return ("kg", kg)
	elif unit == "ft":
		m = round(quantity / 3.28084, 2)
		return ("m", m)
	elif unit == "mi":
		km = round(quantity * 1.60934, 2)
		return ("km", km)
	elif unit == "usd":
		result = round(quantity * _get_currencies(base="USD", convert_to="GBP"), 2)
		return ("GBP", result)
	elif unit == "pt":
		ml = round(quantity * 568.261, 1)
		return("ml", ml)
	elif unit == "oz":
		g = round(quantity*28.3495, 1)
		return ("g", g)

	return -1

def _get_currencies(base="USD", convert_to="GBP"):
	base = base.upper()
	convert_to = convert_to.upper()

	result = requests.get(f"http://api.exchangeratesapi.io/v1/latest?access_key={exchange_API_key}").json()
	rates = result["rates"]
	if base in rates and convert_to in rates:

		return rates[convert_to] / rates[base]
	else:
		raise ValueError("Currency not found.")

@is_command("Convert metric units into imperial. Syntax: !tofreedom <quantity><unit> e.g. `!tofreedom 5kg`")
def tofreedom(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	if message == "!tofreedom tea":
		send_message('"Dinner"')
		return

	try:
		input = message.split(" ")[1]
	except (ValueError, IndexError):
		send_message("You have to provide something to convert..!")

	unit = ""

	while input[-1] not in "0123456789": 
		if input[-1] != " ":
			unit = input[-1] + unit  # e.g. cm or kg
		input = input[:-1]
		if len(input) == 0:
			send_message("You have to provide a quantity to convert.")
			return False

	try:
		quantity = float(input)
	except (ValueError):
		send_message("That.. doesn't look like a number. Try a number followed by a unit, e.g. '5cm' or '12kg'.")
		return False

	try:
		free_unit, free_quantity = _tofreedom(unit, quantity)
	except (ValueError, TypeError):
		send_message("Sorry, I don't recognise that metric unit. :(")
		return False

	if free_quantity == int(free_quantity): # if the float is a whole number
		free_quantity = int(free_quantity)  # convert it to an int (i.e. remove the .0)

	if quantity == int(quantity): # ditto
		quantity = int(quantity)

	send_message(f"{quantity:,}{unit} in incomprehensible Freedom Units is {free_quantity:,}{free_unit}.")
	log(f"Tofreedomed {quantity}{unit} for {user}")

@is_command("Convert imperial units into metric. Syntax: !unfreedom <quantity><unit> e.g. `!tofreedom 5lb`")
def unfreedom(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	try:
		input = message.split(" ")[1]
	except (ValueError, IndexError):
		send_message("You have to provide something to convert..!")

	unit = ""

	while input[-1] not in "0123456789": 
		if input[-1] != " ":
			unit = input[-1] + unit  # e.g. cm or kg
		input = input[:-1]
		if len(input) == 0:
			send_message("You have to provide a quantity to convert.")
			return False

	try:
		quantity = float(input)
	except (ValueError):
		send_message("That.. doesn't look like a number. Try a number followed by a unit e.g. '5ft' or '10lb'.")
		return False

	try:
		sensible_unit, sensible_quantity = _unfreedom(unit, quantity)
	except (ValueError, TypeError):
		send_message("I don't recognise that imperial unit. Sorry! :( PepeHands")
		return False

	if sensible_quantity == int(sensible_quantity): # if the float is a whole number
		sensible_quantity = int(sensible_quantity) # convert it to an int (i.e. remove the .0)

	if quantity == int(quantity): # ditto
		quantity = int(quantity) 

	send_message(f"{quantity}{unit} in units which actually make sense is {sensible_quantity}{sensible_unit}.")
	log(f"Unfreedomed {quantity}{unit} for {user}")

@is_command("Looks up who gifted the current subscription to the given user. Syntax: !whogifted [@]kaywee")
def whogifted(message_dict):
	global subscribers

	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	try:
		target = message.split(" ")[1]
	except IndexError: # no target specified
		target = user
		
	if target[0] == "@": # ignore @ tags
		target = target[1:]
		
	target = target.lower()

	if target in subscribers:
		if subscribers[target]["is_gift"]:
			try:
				gifter = subscribers[target]["gifter_name"]
			except KeyError:
				send_message(f"Error - this is a gifted sub but there is no record of the gifter. WeirdChamp")
				return False
			send_message(f"@{target}'s current subscription was gifted to them by @{gifter}! Thank you! kaywee1AYAYA ")
			log(f"Sent whogifted (target={target}, gifter={gifter}) in response to {user}.")
		else:
			send_message(f"@{target} subscribed on their own this time. Thank you! kaywee1AYAYA ")
			log(f"Sent whogifted ({target} subbed on their own) in response to {user}.")
	else:
		send_message(f"@{target} is not a subscriber. FeelsBadMan")
		log(f"Sent whogifted ({target} is not a subscriber) in response to {user}.")

@is_command("Looks up how many of the currently-active subscriptions were gifted by the given user. Syntax: !howmanygifts [@]kaywee")
def howmanygifts(message_dict):
	global subscribers

	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	try:
		target = message.split(" ")[1]
	except IndexError: # no target specified
		target = user
		
	if target[0] == "@": # ignore @ tags
		target = target[1:]
		
	target = target.lower()
	count = 0
	recipients = ""
		
	for sub in subscribers:
		if subscribers[sub]["gifter_name"].lower() == target:
			recipients += sub + ", "
			count += 1
		
	if count == 0:
		send_message(f"None of the current subscribers were gifted by {target}.")
		log(f"Sent {target} has no gifted subs, in response to {user}.")
	else:
		recipients = recipients[:-2]
		message = f"{target} has gifted {count} of the current subscriptions to: {recipients}. Thanks for the support <3 kaywee1AYAYA"
		if len(message) > 500: # twitch max length
			message = f"{target} has gifted {count} of the current subscriptions! Thanks for the support <3 kaywee1AYAYA"
		send_message(message)
		log(f"Sent {target} has {count} gifted subs, in response to {user}.")

@is_command("Shows a timer until the end of Season 26.")
def endofseason(message_dict):
	#user = message_dict["display-name"].lower()
	try:
		time_left = timeuntil(1625162400)
		send_message(f"Season 28 ends in {time_left}")
	except ValueError:
		send_message("Season 28 has now ended!")

@is_command("Translates a Spanish message into English. Syntax: `!toenglish hola` OR to translate a user's last message, `!toenglish @toniki`")
def toenglish(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	phrase = " ".join(message.split(" ")[1:])

	english = ""
	if phrase.lower() in ["robokaywee", user, "@" + user, ""]:
		return False
	if phrase[0] == "@" and len(phrase.split(" ")) == 1: # parameter is really a username
		try:
			target = phrase[1:].lower()
			phrase = last_message[target]
			english = target + ": "
		except KeyError:
			return False

	#phrase = phrase.replace(".", ",").replace("?", ",").replace("!", ",") # for some reason it only translates the first sentence

	english += translator.translate(phrase, src="es", dest="en").text

	send_message(english)
	log(f"Translated \"{phrase}\" into English for {user}: it says \"{english}\"")

@is_command("Translates an English message into Spanish. Syntax: `!tospanish hello` OR to translate a user's last message, `!tospanish @kaywee`")
def tospanish(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	phrase = " ".join(message.split(" ")[1:])

	spanish = ""
	if phrase.lower() in ["robokaywee", user, "@" + user, ""]:
		return False
	if phrase[0] == "@" and len(phrase.split(" ")) == 1: # parameter is really a username
		try:
			target = phrase[1:].lower()
			phrase = last_message[target]
			spanish = target + ": "
		except KeyError:
			return False

	#phrase = phrase.replace(".", ",").replace("?", ",").replace("!", ",") # for some reason it only translates the first sentence
	
	spanish += translator.translate(phrase, src="en", dest="es").text

	send_message(spanish)
	log(f"Translated \"{phrase}\" into Spanish for {user}: it says \"{spanish}\"")

@is_command("Translates a message from one language to another, powered by Google Translate. Languages are specified as a two-letter code, e.g. en/es/nl/fr. Syntax: !translate <source_lang> <dest_lang> <message>")
def translate(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	try:
		source = message.split(" ")[1]
		dest = message.split(" ")[2]
		phrase = " ".join(message.split(" ")[3:]).replace(".", ",").replace("?", ",").replace("!", ",")
	except IndexError:
		send_message("Syntax Error. Usage: !translate <source_lang> <dest_lang> <text>")
	
	output = ""
	if phrase.lower() in ["robokaywee", user, "@" + user, ""]:
		return False
	if phrase[0] == "@" and len(phrase.split(" ")) == 1: # parameter is really a username
		try:
			target = phrase[1:].lower()
			phrase = last_message[target]
			output = target + ": "
		except KeyError:
			return False
	try:
		# phrase = phrase.replace(".", ";").replace("?", ";").replace("!", ";") # for some reason it only translates the first sentence
		output += translator.translate(phrase, src=source, dest=dest).text
		send_message(output)
		log(f"Translated \"{phrase}\" into {dest} for {user}: it says \"{output}\"")
	except Exception as ex:
		send_message("Translation failed. FeelsBadMan")
		return

@is_command("Shows the user who most recently raided, and the time of the raid.")
def lastraid(message_dict):
	user = message_dict["display-name"].lower()

	raid_data = eval(get_data("last_raid"))

	name    = raid_data["raider"]
	viewers = raid_data["viewers"]
	time    = raid_data["time"]

	date_num = datetime.utcfromtimestamp(time).strftime('%d') # returns a string with date number, e.g. "19"
	if date_num in ["01", "21", "31"]:
		suffix = "st"
	elif date_num in ["02", "22"]:
		suffix = "nd"
	elif date_num in ["03", "23"]:
		suffix = "rd"
	else:
		suffix = "th"

	date_num = str(date_num).lstrip("0")
	time_str = datetime.utcfromtimestamp(time).strftime("%A " + date_num + suffix + " of %B at %H:%M UTC")

	plural = "" if viewers == 1 else "s"

	send_message(f"The latest raid was by {name}, who raided with {viewers} viewer{plural} on {time_str}!")
	log(f"Sent last raid to {user}: it was {name}, who raided with {viewers} viewer{plural} on {time_str}!")

@is_command("Changes the colour of the bot's username. Syntax: !setcolour [<colour>|random] e.g.`!setcolour HotPink` OR `!setcolour random`")
def setcolour(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	try:
		colour = message.split(" ")[1]
	except(ValueError, IndexError):
		colour = "default"

	if colour.lower() in ["random", "default", "blue","blueviolet","cadetblue","chocolate","coral","dodgerblue","firebrick","goldenrod","green","hotpink","orangered","red","seagreen","springgreen","yellowgreen"]:
		valid = True
	else:
		valid = False

		# ONLY WORKS WITH TWITCH PRIME:
		#if colour[0] == "#": 
		#	if len(colour) == 7:
		#		for c in colour[1:].lower():
		#			if c not in "0123456789abcdef":
		#				valid = False
		#				break
		#		else:
		#			valid=True

	if valid:
		if colour == "default":
			colour = "HotPink"

		if colour == "random":
			colours = ["blue","blueviolet","cadetblue","chocolate","coral","dodgerblue","firebrick","goldenrod","green","hotpink","orangered","red","seagreen","springgreen","yellowgreen"]
			new_colour = random.choice(colours)
			send_message("/color " + new_colour, False)
			sleep(0.9)
			set_data("current_colour", new_colour)
			if user != "Timed Event":
				send_message(f"The Robocolour was randomly updated to {new_colour}! kaywee1AYAYA")
			log(f"Colour was randomly updated to {new_colour} in response to {user}")
		else:
			send_message("/color " + colour, False)
			sleep(0.9)
			set_data("current_colour", colour)
			send_message(f"The Robocolour was updated to {colour}! kaywee1AYAYA")
			log(f"Colour was updated to {colour} in response to {user}")
	else:
		send_message(f"@{user} That colour isn't right. Valid colours are: random, default, blue, blueviolet, cadetblue, chocolate, coral, dodgerblue, firebrick, goldenrod, green, hotpink, orangered, red, seagreen, springgreen, yellowgreen")

@is_command("Rainbows the message into the chat. (big spam warning so 12 chars max) Syntax: `!rainbow hello`")
def rainbow(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	try:
		word = " ".join(message.split(" ")[1:])[:15] # 15 chr limit
	except IndexError:
		return False

	if word == "":
		return False

	for colour in ["red", "coral", "goldenrod", "green", "seagreen", "dodgerblue", "blue", "blueviolet", "hotpink"]:
		send_message(f"/color {colour}", False)
		sleep(0.12)
		send_message(word, False)
		sleep(0.12)

	current_colour = get_data("current_colour")
	sleep(1)
	send_message(f"/color {current_colour}")

@is_command("Shows all of the possible username colours (for non-prime users) (big spam warning)")
def allcolours(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	for colour in ['blue', 'blueviolet', 'cadetblue', 'chocolate', 'coral', 'dodgerblue', 'firebrick', 'goldenrod', 'green', 'hotpink', 'orangered', 'red', 'seagreen', 'springgreen', 'yellowgreen']:
		send_message(f"/color {colour}", False)
		sleep(0.1)
		send_message(f"This is {colour}", False)
		sleep(0.1)

	current_colour = get_data("current_colour")
	send_message(f"/color {current_colour}")

def _start_timer(user, time_in, reminder, self):
	global timers

	hours = 0
	mins  = 0
	secs  = 0 # defaults

	time_str = time_in[:]

	if "h" in time_str:
		try:
			hours = int(time_str.split("h")[0])
			time_str = time_str.split("h")[1]
		except:
			send_message(f"@{user} sorry, I don't recognise that format :(")
			timers.remove(self)
			return False

	if "m" in time_str:
		try:
			mins = int(time_str.split("m")[0])
			time_str = time_str.split("m")[1]
		except:
			send_message(f"@{user} sorry, I don't recognise that format :(")
			timers.remove(self)
			return False

	if "s" in time_str:
		try:
			secs = int(time_str.split("s")[0])
			time_str = time_str.split("s")[1]
		except:
			send_message(f"@{user} sorry, I don't recognise that format :(")
			timers.remove(self)
			return False

	if time_str != "": # or secs >= 60 or mins >= 60 or hours > 24:
		send_message("That time doesn't look right.")
		timers.remove(self)
		return False

	timer_time = 60*60*hours + 60*mins + secs

	if timer_time < 30:
		send_message("The timer must be for at least 30 seconds.")
		timers.remove(self)
		return False

	reminder_type = "reminder" if reminder != "" else "timer"
	start_type = "is set" if reminder_type == "reminder" else "has started"

	send_message(f"@{user} - your {time_in} {reminder_type} {start_type}!")

	log(f"Started {time_in} timer for {user}.")
	sleep(timer_time)

	if not self.deleted:
		if reminder_type == "reminder":
			send_message(f"@{user} Reminder! {reminder}")
		else:
			send_message(f"@{user} your {time_in} timer is up!")

		log(f"{user}'s {timer_time} timer expired.")

	with suppress(KeyError):
		timers.remove(self)

@is_command("Starts a timer, after which the bot will send a reminder message in chat. Syntax: `!timer 1h2m3s [<message>]`")
def timer(message_dict):
	global timers

	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	try:
		time_str = message.split(" ")[1]
	except:
		return False

	try:
		reminder = " ".join(message.split(" ")[2:])
	except:
		reminder = ""

	timer_thread = Thread(target=_start_timer, name=f"{time_str} timer for {user}.")
	timer_thread.deleted = False
	timer_thread._args = (user,time_str,reminder,timer_thread) # I'm not *really* supposed to access private attributes, but hey, this is python so anything goes. And Thread doesn't allow setting the args outside the initialiser.
	timer_thread.start()

	timers.add(timer_thread)

@is_command("Cancel all of your current timers.")
def canceltimer(message_dict):
	global timers

	user = message_dict["display-name"].lower()
	num_timers = 0

	for timer in set(timers):
		if f"for {user}." in timer.name:
			timer.deleted = True
			num_timers += 1
			timers.remove(timer)

	if num_timers == 0:
		send_message(f"@{user} You don't have any timers.")
		return False
	elif num_timers == 1:
		send_message(f"@{user} Your timer has been stopped.")
		log(f"Stopped {user}'s timer.")
	else:
		send_message(f"@{user} Your {num_timers} timers have been stopped.")
		log(f"Stopped {user}'s {num_timers} timers.")

@is_command("Shows how many times a command has been used. Syntax: `!uses toenglish`")
def uses(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	thing = message.split(" ")[1]

	# is `thing` a command?
	if thing in command_dict:
		times_used = command_dict[thing].get("uses", 0)
		if times_used != 1:
			send_message(f"The {thing} command has been used {times_used} times.")
			log(f"Sent uses to {user}: command {thing} has been used {times_used} times.")
		else:
			send_message(f"The {thing} command has been used {times_used} time.")
			log(f"Sent uses to {user}: command {thing} has been used {times_used} time.")
	else:
		# is `thing` an emote?
		emote_uses = _emote_uses(thing)
		if emote_uses > 0:
			send_message(f"The {thing} emote has been used {emote_uses:,} times.")
			log(f"Sent uses to {user}: emote {thing} has been used {emote_uses:,} times.")
		else:
			send_message(f"{thing} is not recognised.")

def _nochat_mode():
	global nochat_on
	nochat_on = True

	duration = 12*60 # 12 mins
	check_period = 10 # secs
	for secs in range(0, duration, check_period):
		if not nochat_on: # nochat mode gets turned off externally
			break

		sleep(check_period)
	else:
		nochat_on = False # turn nochat mode off after the duration


@is_command("Turns on nochat mode: users who mention kaywee will receive a notification that kaywee isn't looking at chat")
def nochaton(message_dict):
	user = message_dict["display-name"].lower()

	global nochat_on
	if not nochat_on:
		nochat_thread = Thread(target=_nochat_mode)
		nochat_thread.start()
		send_message("Nochat mode is now on.")
		log(f"Nochat mode is now on in response to {user}.")
	else:
		send_message("Nochat mode is already on.")

@is_command("Turns off nochat mode")
def nochatoff(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	global nochat_on
	nochat_on = False
	send_message("Nochat mode is now off.")
	log(f"{user} turned off Nochat mode.")

@is_command("View the current commands list.")
def rcommands(message_dict):
	user = message_dict["display-name"].lower()
	
	send_message("The RoboKaywee commands list is here: https://old.reddit.com/r/RoboKaywee/wiki/commands")
	log(f"Sent commands list to {user}")

@is_command("Provides either one or two definitions for an English word.")
def define(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	try:
		word = message.split(" ")[1]
		assert word != ""
	except (IndexError, AssertionError):
		return False

	definitions = dic.meaning(word)
	try:
		nouns = definitions.get("Noun", [])
		adjs = definitions.get("Adjective", [])
		vers = definitions.get("Verb", [])
		advs = definitions.get("Adverb", [])
	except AttributeError:
		send_message("I don't know that word.")
	else:
		definitions = list(adjs+vers+advs+nouns)

		if len(definitions) == 1:
			send_message(f"The definition of {word} is: {definitions[0]}")
		else:
			send_message(f"The definitions of {word} are: \"{definitions[0]}\" OR \"{definitions[1]}\"")

@is_command("Lets mods ban a user, for mobile mods.")
def rban(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	target = message.split(" ")[1]
	send_message(f"/ban {target}")
	log(f"Banned user {target} in response to {user}")

@is_command("Lets mods timeout a user, for mobile mods.")
def rtimeout(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	target = message.split(" ")[1]

	try:
		duration = int(message.split(" ")[2])
	except (ValueError, IndexError):
		duration = 600

	send_message(f"/timeout {target} {duration}")
	log(f"Timed out user {target} for {duration} seconds, in response to {user}")

@is_command("Repeats the phrase in chat.")
def echo(message_dict):
	user = message_dict["display-name"].lower()

	if user == "theonefoster":
		message = message_dict["message"]

		phrase = " ".join(message.split(" ")[1:])
		send_message(phrase, add_to_chatlog=True, suppress_colour=True)
		log(f"Echoed \"{phrase}\" for {user}.")
	else:
		return False

@is_command("Looks up the current World Day")
def worldday(message_dict):
	user = message_dict["display-name"].lower()
	
	page = requests.get("https://www.daysoftheyear.com/").text

	# flasgod don't judge me, I know this is wonky af
	# don't worry, I'm juding you enough for both of us -Moldar
	links_re = re.compile("<a.*?\/a>") # looks for <a> tags that also have a close tag
	links = [link for link in re.findall(links_re, page) if "www.daysoftheyear.com" in link and "class=\"js-link-target\"" in link] #"link" is the entire <a></a> tag

	day_re = re.compile("<.*?>([^<]*)<")# text between the tags
	world_day = re.search(day_re, links[0]).group(1).replace("&#8217;", "'") # first group of 0th match (0th group is the whole match, 1st group is between ())

	send_message(f"Happy {world_day}! (Source: https://www.daysoftheyear.com)" )
	log(f"Sent World Day ({world_day}) to {user}")

@is_command("Gamble the bot's fortunes away.")
def autogamble(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	if user == "flasgod":
		send_message("No. Make me.")
		log("Refused to gamble for flasgod KEKW")
		return

	try:
		amount = int(message.split(" ")[1])
	except (IndexError, ValueError):
		amount = 50

	if amount > 100:
		amount = 100

	send_message(f"!gamble {amount}")
	log(f"Gambled {amount} points in response to {user}.")

@is_command("Perform maths with the supreme calculation power of the bot. Syntax: !calculate [expression] e.g. `!calculate (2*3)**2-1`")
def calculate(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]
	
	try:
		calculation = " ".join(message.split(" ")[1:]) # everything after !calculate
	except (IndexError):
		return False

	calculation = calculation.replace(" ", "").replace("x", "*")

	if all(c in "0123456789+-*/()." for c in calculation): # don't allow invalid characters: unsanitised eval() is spoopy
		Thread(target=_perform_calculation, name=f"Calculation for {user}", args=(calculation,user)).start()
	else:
		send_message("That calculation doesn't look right. You can only use: 0-9 +-*/().")
		return False

def _perform_calculation(calculation,user):
	p = Process(target=_process_calculation, args=(calculation,user,bot,log))
	p.start()
	sleep(5)
	if p.is_alive():
		p.terminate() # needs to be a process so that it can be terminated
		send_message(f"@{user} That calculation timed out. Try something less complex.")
		log(f"Calculation {calculation} for {user} timed out.")

def _process_calculation(calculation, user, bot, log):
	try:
		result = eval(calculation) # make sure this is super sanitised!

		# only allow sensible calculation sizes. 100 trillion is arbitrary. This also throws TypeError if it's somehow not a number
		assert -100_000_000_000_000 < result < 100_000_000_000_000

		if int(result) != result: # result is not a numeric integer (may still be type float though, e.g. 10/2 = 5.0)
			result = round(result, 5)
		else:
			result = int(result)
	except:
		bot.send_message("That calculation didn't work.")
		return False
	else:
		prefix = random.choice([
		"The result is",
		"I make that",
		"The answer is",
		"That would be",
		"It's",
		])
		bot.send_message(f"{prefix} {result}")
		log(f"Calculated {calculation} for {user}: answer is {result}")
		return True

@is_command("Adds spaces between your letters.")
def spaces(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	phrase = "".join(message.split(" ")[1:]) # chop off the !command
	target = ""

	if phrase[0] == "@" and len(phrase.split(" ")) == 1: # parameter is really a username
		phrase = phrase[1:].lower()
		target = phrase
		phrase = last_message.get(phrase, phrase)

	spaces = " ".join(phrase)
	send_message(spaces)
	if target == "":
		log(f"Added spaces to {user}'s message: {spaces}")
	else:
		log(f"Added spaces to {target}'s message in response to {user}: {spaces}")

@is_command("Talk like that one spongebob meme.")
def spongebob(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	phrase = " ".join(message.split(" ")[1:]) # chop off the !command
	target = ""

	if phrase[0] == "@" and len(phrase.split(" ")) == 1: # parameter is really a username
		phrase = phrase[1:].lower()
		target = phrase
		phrase = last_message.get(phrase, phrase)

	if len(phrase)%2 == 1: # length is odd
		phrase += " " # make its length even, for the zip() below

	# the python-y way
	#output = "".join(a.lower()+b.upper() for a,b in zip(phrase[::2], phrase[1::2]))

	# went back to the old way bc the python-y way doesn't ignore spaces.
	
	# the old way:
	even = True
	output = ""
	for c in phrase:
		if even:
			output += c.lower()
		else:
			output += c.upper()
		if c != " ":
			even = not even
	

	send_message(output)
	if target == "":
		log(f"Spongebobbed {user}'s message: {output}")
	else:
		log(f"Spongebobbed {target}'s message in response to {user}: {output}")

@is_command("Gets the current weather at a specific place. Defaults to metric but can use imperial with the 'imperial' parameter. Syntax: !weather <place> [imperial]. E.g. `!weather London` or `!weather Austin imperial`")
def weather(message_dict):
	global weather_API_key 
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	if message.split(" ")[-1].lower() in ["metric", "imperial"]:
		place = " ".join(message.split(" ")[1:-1]).title()
		units = message.split(" ")[-1].lower() # metric or imperial
	else:
		place = " ".join(message.split(" ")[1:]).title()
		units = "metric"

	latitude, longitude = _get_place_from_name(place) # get coordinates from place name

	if latitude is None or longitude is None:
		send_message("That place name wasn't found.")
		return False

	weather_url = "https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}&exclude={exclude}&appid={APIkey}&units={unittype}"
	weather_response = requests.get(weather_url.format(lat=latitude, lon=longitude, exclude="minutely,hourly,daily,alerts", APIkey=weather_API_key, unittype=units)).json()

	weather    = weather_response["current"]
	temp       = round(weather["temp"], 1)
	feels_like = round(weather["feels_like"], 1)
	try:
		description = weather["weather"][0]["description"]
	except:
		description = ""

	unit = "C" if units == "metric" else "F"

	output = f"In {place} the current temperature is {temp}°{unit} (feels like {feels_like}{unit})."
	if description:
		output += f" Overall: {description}."

	send_message(output)
	log(f"Sent weather report to {user} for {place}")

def _get_place_from_name(place):
	# memoisation function to only call the geo api for new place names.
	# if a new place name is seen, the coordinates are looked up from the api
	# if that name is seen in future, it is recalled from the memo cache

	with open("places.txt", "r", encoding="utf-8") as f:
		places = dict(eval(f.read()))

	if place not in places:
		print(f"Looking up new place name {place}")

		geocode_url = "https://geocode.xyz/{place}?json=1"
		geo_response = requests.get(geocode_url.format(place=place)).json()

		if not ("latt" in geo_response and "longt" in geo_response):
			return (None, None)

		places[place] = geo_response["latt"], geo_response["longt"]

		with open("places.txt", "w", encoding="utf-8") as f:
			f.write(str(places))

	return places[place]

@is_command("Cancels a Toxicpoll")
def cancelpoll(message_dict):
	user = message_dict["display-name"]

	global toxic_poll

	if toxic_poll:
		global voters
		global toxic_votes
		global nottoxic_votes

		toxic_poll = False
		voters = set()
		toxic_votes = 0
		nottoxic_votes = 0

		send_message("Toxicpoll cancelled.")
		log(f"Cancelled toxicpoll in response to {user}")
	else:
		send_message("There is no toxicpoll currently active.")
		return False

@is_command("Show the Spanish Word of the Day")
def wordoftheday(message_dict):
	user = message_dict["display-name"]

	with open("spanish.txt", "r", encoding="utf-8") as f:
		words = eval(f.read())

	wotd_time = get_data("wordoftheday_time")
	word_num = get_data("wordoftheday_index")

	if wotd_time is None or wotd_time < time()-12*60*60 or word_num is None:
		set_data("wordoftheday_time", time())
		word_num = random.randint(0, len(words))
		set_data("wordoftheday_index", word_num)

	spa, eng = words[word_num]
	if user == "Timed Event":
		tag = "@kaywee "
	else:
		tag = ""

	send_message(f"{tag}The Spanish Word of the Day is \"{spa}\", which means \"{eng}\"")
	log(f"Sent word of the Day to {user}: {spa} means {eng}")

@is_command("Show the price of bitcoin")
def btc(message_dict):
	user = message_dict["display-name"].lower()
	try:
		result = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot").json()
		value = float(result["data"]["amount"])
	except Exception as ex:
		log(f"Exception in btc: {str(ex)}")
		return False
	
	if not message_dict.get("suppress_log", False):
		log(f"Sent BTC of ${value:,} to {user}")
	send_message(f"Bitcoin is currently worth ${value:,}")

@is_command("Show the price of etherium")
def eth(message_dict):
	user = message_dict["display-name"].lower()
	try:
		result = requests.get("https://api.coinbase.com/v2/prices/ETH-USD/spot").json()
		value = float(result["data"]["amount"])
	except Exception as ex:
		log(f"Exception in eth: {str(ex)}")
		return False
	
	if not message_dict.get("suppress_log", False):
		log(f"Sent ETH of ${value:,} to {user}")

	send_message(f"Ethereum is currently worth ${value:,}")

@is_command("Show the price of Dogecoin")
def doge(message_dict):
	user = message_dict["display-name"].lower()
	try:
		result = requests.get("https://sochain.com/api/v2/get_price/DOGE/USD").json()
		value = float(result["data"]["prices"][0]["price"])
	except Exception as ex:
		log(f"Exception in eth: {str(ex)}")
		return False

	value = round(value * 100, 2)
	
	if not message_dict.get("suppress_log", False):	
		log(f"Sent DOGE of {value:,} cents to {user}")

	send_message(f"Dogecoin is currently worth {value:,} cents")

@is_command("Display Kaywee's real biological age")
def age(message_dict):
	ages = list(range(19,24)) + list(range(36,43))
	true_age = random.choice(ages)
	send_message(f"Kaywee is {true_age} years old.")

@is_command("Show how long you've been following")
def followtime(message_dict):
	user = message_dict["display-name"].lower()

	try:
		target = message_dict["message"].split(" ")[1].lower().replace("@", "")
	except (KeyError, IndexError):
		target = user

	with open("followers.txt", "r", encoding="utf-8") as f:
		try:
			followers = dict(eval(f.read()))
		except Exception as ex:
			log("Exception reading followers in followtime command: " + str(ex))
			followers = {}

	if target in followers:
		follow_time = time() - datetime.strptime(followers[target], "%Y-%m-%dT%H:%M:%SZ").timestamp()
		duration = seconds_to_duration(follow_time)
		send_message(f"{target} followed Kaywee {duration} ago.")
	else:
		send_message(f"{target} is not following Kaywee. FeelsBadMan")

@is_command("Predict how OW2 will work.")
def ow2(message_dict):
	user = message_dict["display-name"].lower()

	with open("ow2.txt", "r") as f:
		lines = f.read().split("\n")

	ow2_prediction = random.choice(lines)
	send_message(ow2_prediction)
	log(f"Sent OW2 in response to {user}: {ow2_prediction}")

@is_command("Look up the top definition of a word on Urban Dictionary. Usage: !urban <word> [definition number]. e.g. `!urban twitch 2`")
def urban(message_dict):
	message = message_dict["message"]
	user = message_dict["display-name"]
	num = 0

	try:
		term = " ".join(message.split(" ")[1:])
	except:
		send_message("Syntax error.")
		log(f"Syntax error in Urban: message was {message}")
		return False

	try:
		num = int(term.split(" ")[-1]) - 1
		assert 0 < num < 100
	except:
		num = 0
	else:
		term = " ".join(term.split(" ")[:-1])

	try:
		result = requests.get(f"http://api.urbandictionary.com/v0/define?term={term}")
		definition = result.json()["list"][num]["definition"]
		assert definition != ""
	except:
		send_message("No definition found :( FeelsBadMan")
		log(f"No Urban definition found for {term} in response to {user}")
		return True

	definition = definition.replace("[", "").replace("]", "")
	if " " in term:
		url_term   = term.replace(" ", "%20")
		url_suffix = f"define.php?term={url_term}"
	else:
		url_suffix = term # it seems to accept just /word at the end as long as there are no spaces.. so this is smaller

	# url looks like https://www.urbandictionary.com/define.php?term=term
	# but this is shorter and works too: www.urbandictionary.com/term
	chat_url = f"www.urbandictionary.com/{url_suffix}"
	suffix = f" - Source: {chat_url}"
	max_len = 500-len(suffix)
	definition = definition[:max_len]

	send_message(f"{definition}{suffix}")
	log(f"Sent Urban definition of {term} to {user} - it means {definition}")

def _chatstats(key):
	# valid keys:
	assert key in ['channel', 'totalMessages', 'chatters', 'hashtags', 'commands', 'bttvEmotes', 'ffzEmotes', 'twitchEmotes']

	url = "https://api.streamelements.com/kappa/v2/chatstats/kaywee/stats"
	result = requests.get(url).json()

	return result[key]

@is_command("Show the total number of messages ever sent in Kaywee's chat")
def totalmessages(message_dict):
	user = message_dict["display-name"].lower()

	messages = int(_chatstats("totalMessages")) + 1
	send_message(f"This is message number {messages:,} to be sent in Kaywee's chat. Source: https://stats.streamelements.com/c/kaywee")
	log(f"Sent totalmessages of {messages:,} to {user}")

@is_command("Show the total number of messages sent in Kaywee's chat by a given user. Syntax: !chats [@]<user>, e.g. `!chats @kaywee`")
def chats(message_dict):
	user = message_dict["display-name"].lower()

	try:
		target = message_dict["message"].split(" ")[1].lower().replace("@", "")
	except (KeyError, IndexError):
		target = user

	chatters = _chatstats("chatters")

	for chatter in chatters:
		name, chats = chatter["name"], chatter["amount"]
		if name == target:
			break
	else: # name not found
		send_message(f"User not found in top 100 chatters - use !chatstats for full info.")
		return True

	if user == "theonefoster":
		chats += 5048 + 9920 # from AcesFullOfKings and theonefoster_

	send_message(f"{target} has sent {chats:,} messages in Kaywee's channel! Source: https://stats.streamelements.com/c/kaywee")
	log(f"Sent {target}'s chat count of {chats:,} to {user}")

@is_command("Show the current BTTV emotes.")
def bttv(message_dict):
	user = message_dict["display-name"].lower()
	bttv_emotes = _chatstats("bttvEmotes")
	emotes = [emoteinfo["emote"] for emoteinfo in bttv_emotes]
	
	first_500 = ""
	last_500 = ""

	for emote in emotes:
		# these show up in the API for some reason, but they're not valid emotes.. so exclude them here
		if emote not in ['BasedGod', 'Zappa', 'FeelsPumpkinMan', 'PedoBear', 'COGGERS', 'SillyChamp', 'monkaX', 'CCOGGERS', '5Head', 'TriDance', 'RebeccaBlack', 'peepoPANTIES']:
			if len(first_500 + " " + emote) < 500:
				if first_500:
					first_500 = first_500 + " " + emote
				else:
					first_500 = emote
			else:
				if last_500:
					last_500 = last_500 + " " + emote
				else:
					last_500 = emote

	send_message("The BTTV emotes in this channel are: ")
	send_message(first_500, suppress_colour=True)
	if last_500:
		send_message(last_500, suppress_colour=True)
	log(f"Sent BTTV emotes to {user}")

@is_command("Show the current FFZ emotes.")
def ffz(message_dict):
	user = message_dict["display-name"].lower()
	bttv_emotes = _chatstats("ffzEmotes")
	emotes = [emoteinfo["emote"] for emoteinfo in bttv_emotes]
	
	first_500 = ""
	last_500 = ""

	for emote in emotes:
		if len(first_500 + " " + emote) < 500:
			if first_500:
				first_500 = first_500 + " " + emote
			else:
				first_500 = emote
		else:
			if last_500:
				last_500 = last_500 + " " + emote
			else:
				last_500 = emote

	send_message("The FFZ emotes in this channel are: ")
	send_message(first_500, suppress_colour=True)
	if last_500:
		send_message(last_500, suppress_colour=True)
	log(f"Sent BTTV emotes to {user}")

def _get_all_emotes():
	global all_emotes
	url = "https://api.streamelements.com/kappa/v2/chatstats/kaywee/stats"
	result = requests.get(url).json()

	all_emotes = [emote_info["emote"] for emote_info in result.get("bttvEmotes", []) + result.get("ffzEmotes", []) + result.get("twitchEmotes", [])]

Thread(target=_get_all_emotes, name="Get_All_Emotes").start()

def _emote_uses(emote):
	emotes = _get_all_emotes()
	emotes_dict = {}

	for e in emotes:
		emotes_dict[e["emote"]] = e["amount"]

	return emotes_dict.get(emote, 0)

@is_command("Show the current stream title.")
def title(message_dict):
	url = "https://api.twitch.tv/helix/streams?user_id=" + kaywee_channel_id
	global authorisation_header

	bearer_token = get_data("app_access_token")
	authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + bearer_token}

	try:
		# if this call succeeds, streamer is Live. Exceptions imply streamer is offline (as no stream title exists)
		title = requests.get(url, headers=authorisation_header).json()["data"][0]["title"]
		send_message(f"The stream title is: {title}")
	except:
		send_message("There is no stream right now.")
		return True

@is_command("Look up a BattleTag's SR. Syntax: !sr <battletag> [<region>]. <Region> is one of us,eu,asia and defaults to `us`. Example usage: `!sr Kaywee#12345 us` OR `!sr Toniki#9876`")
def sr(message_dict):
	# uses https://ow-api.com/docs

	message = message_dict["message"]
	user = message_dict["display-name"].lower()

	Thread(target=_sr_thread, args=(message,user),name="SR Thread").start() # it can take up to 5s to get an API response. this way I lose the return value but oh well

def _sr_thread(message,user):
	try:
		battletag = message.split(" ")[1]
		assert "#" in battletag

		target = battletag.split("#")[0]
		number = int(battletag.split("#")[1])
	except:
		send_message("You have to provide a battletag in the format: Name#0000 (case sensitive!)")
		return True

	try:
		region = message.split(" ")[2].lower()
		assert region in ["na", "eu", "us", "asia"]
		if region == "na":
			region = "us"
	except:
		region = "us"

	battletag = battletag.replace("#", "-")

	url = f"https://ow-api.com/v1/stats/pc/{region}/{battletag}/profile"
	result = requests.get(url).json()

	if "error" in result:
		send_message(result["error"] + " (names are case sensitive!)")
		return True
	elif result["private"] is True:
		send_message("That profile is private! PepeHands")
		return True
	elif "ratings" in result:
		tank = 0
		support = 0
		dps = 0

		if not result["ratings"]:
			send_message("That account hasn't placed in Competitive yet!")
			return True

		for rating in result["ratings"]:
			if rating["role"] == "tank":
				tank = rating["level"]
			elif rating["role"] == "damage":
				dps = rating["level"]
			elif rating["role"] == "support":
				support = rating["level"]

		SRs = ""

		if tank > 0:
			SRs = "Tank: " + str(tank)

		if dps > 0:
			if SRs == "":
				SRs = "DPS: " + str(dps)
			else:
				SRs += " // DPS: " + str(dps)

		if support > 0:
			if SRs == "":
				SRs = "Support: " + str(support)
			else:
				SRs += " // Support: " + str(support)

		if SRs != "":
			send_message(f"{target}'s SRs are: {SRs}")
			log(f"Sent SR to {user}: {target}'s SRs are: {SRs}")
			return True
		else:
			send_message(f"No SRs were found.")
			return True

	elif "rating" in result:
		if result["rating"] > 0:
			send_message(f"{target}'s SR is {result['rating']}")
			log(f"Sent SR to {user}: {target}'s SR is {result['rating']}")
			return True
		else:
			send_message(f"No SR was found.")
			return True
	
	send_message(f"Unable to find {target}'s SR rating. (Player names are case-sensitive!)")
	return True

@is_command("Checks whether a channel is live. Syntax: !islive [@]<channel> e.g. `!islive kaywee`")
def islive(message_dict):
	message = message_dict["message"]
	user = message_dict["display-name"].lower()

	channel = message.split(" ")[1]
	
	if channel[0] == "@":
		channel = channel[1:]

	url = "https://api.twitch.tv/helix/streams?user_login=" + channel
	bearer_token = get_data("app_access_token")
	authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + bearer_token}

	try:
		title = requests.get(url, headers=authorisation_header).json()["data"][0]["title"]
		send_message(f"{channel} is currently Live! www.twitch.tv/{channel}")
		log(f"Sent islive to {user}: {channel} is live.")
		return True
	except:
		send_message(f"{channel} is not currently Live.")
		log(f"Sent islive to {user}: {channel} is not live.")
		return True

@is_command("Send a message to another user the next time they appear in chat.")
def message(message_dict):
	global user_messages
	global usernames

	valid_chars = "abcdefghijklmnopqrstuvwxyz0123456789!£$%^&*()-=_+[]{};'#:@~,./<>? "

	try:
		message = message_dict["message"]
		user = message_dict["display-name"].lower()

		target = message.split(" ")[1]
		user_message = "".join(chr for chr in " ".join(message.split(" ")[2:]) if chr.lower() in valid_chars)

		if target[0] == "@":
			target = target[1:]

		target = target.lower()

	except Exception as ex:
		send_message("Invalid syntax. Your message won't be sent.")
		log(f"Didn't save user message for {user}: invalid syntax.")
		return False

	if target == user:
		send_message("Don't be silly, you can't message yourself.")
		log(f"Didn't save user message for {user}: tried to message self")
		return False
	elif target in ["robokaywee", "streamelements"]:
		send_message("Don't be silly, bots can't read. (At least, that's what we want you to think..!)")
		log(f"Didn't save user message for {user}: tried to message a bot")
		return False

	if target in usernames:
		if target in user_messages:
			send_message("That user already has a message waiting for them. To avoid spam, they can only have one at a time.")
			log(f"Didn't save user message for {user}: duplicate user ({target})")
			return False
		else:
			if any(x in user_message for x in ["extended", "warranty", "vehicle", "courtesy"]):
				send_message("That mesasge is invalid.")
				return False

			else:
				for msg in user_messages:
					if user_messages[msg]["from_user"] == user:
						send_message("You've already sent someone a message. To avoid spam, you can only send one at once.")
						return False

				user_messages[target] = {"from_user": user, "user_message": user_message}
				set_data("user_messages", user_messages)
				send_message(f"Your message was saved! It'll be sent next time {target} sends a chat.")
				log(f"Saved a user message from {user} to {target}.")
				return True
	else:
		send_message("That user has never been seen in chat. Messages can only be sent to known users.")
		log(f"Didn't save user message for {user}: unknown user ({target})")
		return False

@is_command("Get the number of viewers in a game category on Twitch. Example usage: `!viewers overwatch`")
def viewers(message_dict):
	Thread(target=_get_viewers_worker, args=(message_dict,), name="Get Viewers Worker").start()

def _get_viewers_worker(message_dict):
	user = message_dict["display-name"].lower()
	viewer_thread = Thread(target=_get_viewers, args=(message_dict,), name="Get Viewers")
	viewer_thread.start()

	sleep(3.5)
	if viewer_thread.is_alive():
		send_message(f"@{user} Give me a sec - it might take some time to get the viewers...")

def _get_viewers(message_dict):
	try:
		name = " ".join(message_dict["message"].split(" ")[1:])
	except:
		send_message("You must specify which game to search for.")
		return False

	user = message_dict["display-name"].lower()

	bearer_token = get_data("app_access_token")
	authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + bearer_token}

	games_url = f"https://api.twitch.tv/helix/games?name={name.replace(' ', '%20')}"
	try:
		id = requests.get(games_url, headers=authorisation_header).json()["data"][0]["id"]
	except:
		send_message("There was a problem. Maybe that game doesn't exist.")
		return False

	viewers = 0

	cursor = ""
	viewers_url = "https://api.twitch.tv/helix/streams?game_id={id}&first=100&after={cursor}"

	page = requests.get(viewers_url.format(id=id, cursor=cursor), headers=authorisation_header).json()
	cursor = page["pagination"]["cursor"]

	while cursor != "":
		for stream in page["data"]:
			viewers += stream["viewer_count"]

		page = requests.get(viewers_url.format(id=id, cursor=cursor), headers=authorisation_header).json()
		try:
			cursor = page["pagination"]["cursor"]
		except Exception as ex:
			break

	send_message(f"@{user} There are currently {viewers:,} people watching a {name} stream.")
	log(f"Sent viewers of {viewers:,} in category {name} to {user}.")
	return

@is_command("Check whether a website or service is down. Usage: `!isitdown apex legends` or `!isitdown twitch`")
def isitdown(message_dict):
	
	user = message_dict["display-name"].lower()

	try:
		name = " ".join(message_dict["message"].split(" ")[1:])
	except:
		send_message("You must provide a name to search for, e.g. !isitdown twitch")
		return False

	url = f"https://downdetector.com/status/{name.replace(' ', '-')}"
	user_agent = {'User-agent': 'Mozilla/5.0'}
	page = requests.get(url, headers=user_agent)

	if "User reports indicate possible problems" in page.text:
		send_message(f"It looks like {name} is having possible problems! Sadge Source: {url}")
		log(f"Sent isitdown to {user}: {name} is having problems.")
	elif "User reports indicate problems" in page.text:
		send_message(f"It looks like {name} is down! Sadge Source: {url}")
		log(f"Sent isitdown to {user}: {name} is down.")		
	elif "our systems have detected unusual traffic" in page.text:
		send_message(f"Oops, I can't check downdetector at the moment. Tell Foster he sucks at coding.")
		log(f"Anti-scraping from downdetector! Can't process command.")
		return False
	elif "no current problems" in page.text:
		send_message(f"Looks like {name} is up! FeelsGoodMan Source: {url}")
		log(f"Sent isitdown to {user}: {name} is up!")
	else:
		send_message(f"I'm not sure if {name} is down. Did you type it correctly? Try checking {url}")
		log(f"Sent isitdown to {user} - service {name} not found")

@is_command("Provides a reason as to why Kaywee is playing badly")
def excuse(message_dict):
	message = message_dict["message"]
	user = message_dict["display-name"].lower()

	try:
		param = message.split(" ")[1].lower()
	except:
		param = ""

	if param == "add":
		if message_dict["user_permission"] < permissions.Mod:
			send_message("Only mods can add excuses. Try using !excuse to see why Kaywee is playing badly.")
			return False
		excuse = " ".join(message.split(" ")[2:])
		with open("excuses.txt", "r", encoding="utf-8") as f:
			excuses = list(f.read().split("\n"))

		excuses.append(excuse)

		with open("excuses.txt", "w", encoding="utf-8") as f:
			f.write("\n".join(excuses))

		responses = ["Ahh that explains a lot.",
					 "Oh. Does her duo know this?",
					 "Oh, I was wondering what was going on."]

		send_message(random.choice(responses))
		log(f"Added excuse from {user}: {excuse}")
	else:
		with open("excuses.txt", "r", encoding="utf-8") as f:
			excuses = f.read().split("\n")

		excuse = random.choice(excuses)
		send_message(excuse)
		log(f"Sent excuse to {user}: {excuse}")

@is_command("Show the colour you're currently using.")
def mycolour(message_dict):
	if "color" in message_dict:
		send_message(f"Your colour is {message_dict['color']}")
	else:
		send_message("I don't know what your colour is.")

@is_command("Show the price of etherium")
def eth(message_dict):
	new_message_dict = message_dict
	new_message_dict["message"] = "!crypto eth"
	crypto(new_message_dict)

@is_command("Show the price of bitcoin")
def btc(message_dict):
	new_message_dict = message_dict
	new_message_dict["message"] = "!crypto btc"
	crypto(new_message_dict)

@is_command("Show the price of dogecoin")
def eth(message_dict):
	new_message_dict = message_dict
	new_message_dict["message"] = "!crypto doge"
	crypto(new_message_dict)

@is_command("Check all the crypto prices.")
def crypto(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	try:
		crypto_codes = message.split(" ")[1:]
	except:
		crypto_codes = ["BTC", "ETH", "DOGE"]

	for item in crypto_codes:
		item = item.upper()
		try:
			if item == "DOGE":
				result = requests.get(f"https://sochain.com/api/v2/get_price/{item}/USD").json()
				value = float(result["data"]["prices"][0]["price"])
			else:
				result = requests.get(f"https://api.coinbase.com/v2/prices/{item}-USD/spot").json()
				value = float(result["data"]["amount"])
		except Exception as ex:
			log(f"Exception in crypto: {str(ex)}")
			send_message(f"{item} is not currently available via coinbase")
			return False

		send_message(f"{item} is currently worth ${round(value, 4):,}")
		log(f"Sent {item} of ${round(value, 4)} to {user}")

# Please, nobody copy this or use this...it's terrifying.
@is_command("Updates the RoboKaywee github with the current codebase.")
def commit(message_dict):
	user = message_dict["display-name"].lower()
	message = message_dict["message"]

	try:
		commit_message = " ".join(message.split(" ")[1:])
		assert commit_message != ""
	except:
		commit_message = "Bug Fixes and Performance Improvements"

	Thread(target=_commit_thread, args=(commit_message,)).start()
	send_message("The commit is running..")
	log(f"Commited to Git for {user}")

def _commit_thread(message):
	result = subprocess.run("commit.bat " + message, capture_output=True).returncode

	if result == 0:
		send_message(f"The commit was successful. https://github.com/theonefoster/RoboKaywee")
		log(f"The commit was successful")
	else:
		send_message(f"The commit failed with code {result}")
		log(f"The commit failed with code {result}")

@is_command("Appends a line of code to RoboKaywee's code")
def append(message_dict):
	message = message_dict["message"]
	user = message_dict["display-name"].lower()

	line = " ".join(message.split(" ")[1:])
	with open("commands.py", "a") as f:
		f.write("\n" + line)

	log(f"Appended {line} for {user}")
	send_message("Append was successful!")

# this is flasgod's comment, here forever as a sign of his contribution to the project

"""
@is_command("Restarts the bot.")
def restart(message_dict):
    #After like 15 mins of work I couldn't get this to work so for now it is undefined
    return False
    DETACHED_PROCESS = 0x00000008
    process = subprocess.Popen([sys.executable, "RoboKaywee.py"],creationflags=DETACHED_PROCESS)# .pid
    print(process)
    sleep(3) # give it time to fail if it's going to not start
    #if not process.is_alive:
    #    send_message("The restart failed.")
    #    return False
    #else:
    send_message("RoboKaywee has restarted.")
    exit()


def _start_bot():
	process = subprocess.Popen([sys.executable, "RoboKaywee.py"])
"""

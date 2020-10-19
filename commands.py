import random
import requests 

from time          import sleep, time
from datetime      import date, datetime
from fortunes      import fortunes
from threading     import Thread
from credentials   import kaywee_channel_id, robokaywee_client_id
from googletrans   import Translator

def is_command():
	def inner(func):
		func.is_command = True
		return func
	return inner

"""
Each function is a command, callable by sending "!<function_name>" in chat.
Each function returns either a string, which gets sent in chat, or None, which indicates no reply is needed.
All replies will be sent in the bot's colour, using /me.
The `bot` object and the `send_message` function will be accessible here at runtime.
"""

currencies = {'CAD', 'HKD', 'ISK', 'PHP', 'DKK', 'HUF', 'CZK', 'GBP', 'RON', 'SEK', 'IDR', 'INR', 'BRL', 'RUB', 'HRK', 'JPY', 'THB', 'CHF', 'EUR', 'MYR', 'BGN', 'TRY', 'CNY', 'NOK', 'NZD', 'ZAR', 'USD', 'MXN', 'SGD', 'AUD', 'ILS', 'KRW', 'PLN'}
bttv_global = {'PedoBear', 'RebeccaBlack', ':tf:', 'CiGrip', 'DatSauce', 'ForeverAlone', 'GabeN', 'HailHelix', 'HerbPerve', 'iDog', 'rStrike', 'ShoopDaWhoop', 'SwedSwag', 'M&Mjc', 'bttvNice', 'TopHam', 'TwaT', 'WatChuSay', 'SavageJerky', 'Zappa', 'tehPoleCat', 'AngelThump', 'HHydro', 'TaxiBro', 'BroBalt', 'ButterSauce', 'BaconEffect', 'SuchFraud', 'CandianRage', "She'llBeRight", 'D:', 'VisLaud', 'KaRappa', 'YetiZ', 'miniJulia', 'FishMoley', 'Hhhehehe', 'KKona', 'PoleDoge', 'sosGame', 'CruW', 'RarePepe', 'iamsocal', 'haHAA', 'FeelsBirthdayMan', 'RonSmug', 'KappaCool', 'FeelsBadMan', 'BasedGod', 'bUrself', 'ConcernDoge', 'FeelsGoodMan', 'FireSpeed', 'NaM', 'SourPls', 'LuL', 'SaltyCorn', 'FCreep', 'monkaS', 'VapeNation', 'ariW', 'notsquishY', 'FeelsAmazingMan', 'DuckerZ', 'SqShy', 'Wowee', 'WubTF', 'cvR', 'cvL', 'cvHazmat', 'cvMask'}
bttv_local = {'ppCircle', 'KayWeird', 'PepeHands', 'monkaS', 'POGGERS', 'PepoDance', 'HYPERS', 'BongoCat', 'RareParrot', 'BIGWOW', '5Head', 'WeirdChamp', 'PepeJam', 'KEKWHD', 'widepeepoHappyRightHeart', 'gachiHYPER', 'peepoNuggie', 'MonkaTOS', 'KKool', 'OMEGALUL', 'monkaSHAKE', 'PogUU', 'Clap', 'AYAYA', 'CuteDog', 'weSmart', 'DogePls', 'REEEE', 'BBoomer', 'HAhaa', 'FeelsLitMan', 'POGSLIDE', 'CCOGGERS', 'peepoPANTIES', 'PartyParrot', 'monkaX', 'widepeepoSadBrokenHeart', 'KoolDoge', 'TriDance', 'PepePls', 'gachiBASS', 'pepeLaugh', 'whatBlink', 'FeelsSadMan'}

with open("emotes.txt", "r", encoding="utf-8") as f:
	emote_list = set(f.read().split("\n"))

all_emotes = emote_list | bttv_local | bttv_global

toxic_poll = False
toxic_votes = 0
nottoxic_votes = 0
voters = set()

translator = Translator()

with open("subscribers.txt", "r", encoding="utf-8") as f:
	try:
		subscribers = dict(eval(f.read()))
	except Exception as ex:
		print("Exception creating subscriber dictionary: " + str(ex))
		subscribers = dict()

@is_command()
def robo(user, message):
	"""
	format:
	!robo <action> <command> [<params>]

	examples:
	* add a text command:
		!robo add helloworld Hello World!
	* edit an existing text command:
		!robo edit helloworld Hello World Again!
	* delete a command:
		!robo delete helloworld
	* change command options:
		!robo options helloworld permission 10
		!robo options helloworld cooldown 60
		!robo options helloworld usercooldown 120
	"""
	params = message.split(" ")[1:]
	try:
		action = params[0]
		command_name = params[1]
	except IndexError:
		send_message("Syntax error.")
		return

	if action == "edit":
		if command_name  in command_dict:
			if not command_dict[command_name]["coded"] and "response" in command_dict[command_name]:
				command_dict[command_name]["response"] = " ".join(params[2:])
				send_message("Command " + command_name + " has been updated.")
				write_command_data()
			else:
				send_message("The command " + command_name + " is not updatable.")
		else:
			send_message(f"No command exists with name {command_name}.")
	elif action == "options":
		try:
			option = params[2]
		except IndexError:
			send_message("Syntax error.")
			return
		if option in ["globalcooldown", "cooldown"]: #assume "cooldown" means global cooldown
			try:
				cooldown = int(params[3])
				assert 0 <= cooldown <= 300
			except (ValueError, IndexError, AssertionError):
				send_message("Cooldown must be provided as an integer between 1 and 300 seconds.")
				return

			if command_name  in command_dict:
				command_dict[command_name]["global_cooldown"] = cooldown
				write_command_data()
				log(f"{user} updated global cooldown on command {command_name} to {cooldown}")
				send_message(f"Global Cooldown upated to {cooldown} on {command_name}")
			else:
				send_message(f"No command exists with name {command_name}.")
		elif option == "usercooldown":
			try:
				cooldown = int(params[3])
				assert 0 <= cooldown <= 3600
			except (ValueError, IndexError, AssertionError):
				send_message("Cooldown must be provided as an integer between 1 and 3600 seconds.")
				return

			command_dict[command_name]["user_cooldown"] = cooldown
			write_command_data()
			log(f"{user} updated user cooldown on command {command_name} to {cooldown}")
			send_message(f"User Cooldown upated to {cooldown} on {command_name}")
		elif option == "permission":
			try:
				permission = int(params[3])
				assert 0 <= permission <= 10
			except (ValueError, IndexError, AssertionError):
				send_message("Permission must be provided as an integer: 0=All, 4=Subscriber, 6=VIP, 8=Moderator, 10=Broadcaster")
				return

			if command_name in command_dict:
				command_dict[command_name]["permission"] = permission
				write_command_data()

				send_message(f"Permission updated to {permission} on command {command_name}")
				log(f"{user} updated permission on command {command_name} to {permission}")
			else:
				send_message(f"No command exists with name {command_name}.")
		else:
			send_message("Unrecognised option: must be permission, globalcooldown, or usercooldown")
	elif action in ["add", "create"]:
		if command_name not in command_dict:
			response = " ".join(params[2:])
			if response != "":
				command_dict[command_name] = {'permission': 0, 'global_cooldown': 1, 'user_cooldown': 5, 'coded': False, 'response': response}
				write_command_data()
				send_message("Added command " + command_name)
				log(f"{user} added command {command_name}")
			else:
				send_message("Syntax error.")
		else:
			send_message("Command " + command_name + " already exists.")

	elif action in ["remove", "delete"]:
		if command_name in command_dict:
			if command_dict[command_name]["coded"] == False:
				del command_dict[command_name]
				write_command_data()
				send_message("Deleted command " + command_name)
				log(f"{user} deleted command {command_name}")
			else:
				send_message(f"You cannot delete the {command_name} command.")
		else:
			send_message(f"No command exists with name {command_name}.")
	#elif action == "alias": # ???
	#	pass
	elif action == "view":
		view_command = command_dict[command_name]

		usercooldown = view_command.get("user_cooldown", 0)
		cooldown     = view_command.get("global_cooldown", 0)
		coded        = view_command.get("coded", False)
		permission   = view_command.get("permission", 0)
		response     = view_command.get("response", "")

		permission = {0:"Pleb", 2:"Follower", 4:"Subscriber", 6:"VIP", 8:"Mod", 10:"Broadcaster"}[permission]

		if coded or response == "":
			send_message(f"{command_name}: Permission: {permission}; Global Cooldown: {cooldown}; User Cooldown: {usercooldown}")
		else:
			send_message(f"{command_name}: Permission: {permission}; Global Cooldown: {cooldown}; User Cooldown: {usercooldown}; Response: {response}")

	else:
		send_message("Unrecognised action: must be add, remove, edit, options, view")

@is_command()
def triangle(user, message, emotes=""):
	global all_emotes
	params = message.split(" ")
	try:
		emote = params[1]
	except:
		return

	if emote in all_emotes:
		pass
	else:
		if not emotes:
			send_message("You can only triangle with an emote.")
			return

		try:
			valid_emote = False

			for emoteID in emotes:
				positions = emotes[emoteID].split(",")
				for position in positions:
					start, end = position.split("-")
					if start == "10":
						valid_emote = True
						break
		except:
			send_message("You can only triangle with an emote.")
			return

		if not valid_emote:
			send_message("You can only triangle with an emote.")
			return

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

@is_command()
def toxicpoll(user, message):
	poll_thread = Thread(target=_start_toxic_poll)
	poll_thread.start()

@is_command()
def votetoxic(user, message):
	global toxic_poll
	global toxic_votes
	global voters

	if toxic_poll and user not in voters:
		toxic_votes += 1
		voters.add(user)
		send_message(f"{user} voted toxic.")
		print(f"Toxic vote from {user}!")

@is_command()
def votenice(user, message):
	global toxic_poll
	global nottoxic_votes
	global voters

	if toxic_poll and user not in voters:
		nottoxic_votes += 1
		voters.add(user)
		send_message(f"{user} voted NOT toxic.")
		print(f"NOTtoxic vote from {user}!")

def _start_toxic_poll():
	global toxic_poll
	global toxic_votes
	global nottoxic_votes
	global voters
		
	send_message("Poll starting! Type !votetoxic or !votenice to vote on whether the previous game was toxic or nice. Results in 60 seconds.")
	toxic_poll = True
	sleep(60)
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

	message = f"Results are in! Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)"
	
	if nottoxic_votes > toxic_votes:
		send_message(message + ". Chat votes that the game was NOT toxic! FeelsGoodMan ")
		send_message("!untoxic")
		log(f"Poll result: not toxic. Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)")

	elif toxic_votes > nottoxic_votes:
		send_message(message + ". Chat votes that the game was TOXIC! FeelsBadMan ")
		send_message("!toxic")
		log(f"Poll result: TOXIC. Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)")
	else:
		send_message(message + ". Poll was a draw! Chat can't make up its mind! kaywee1Wut ")
		log(f"Poll result: undecided. Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)")

	voters = set()
	toxic_votes = 0
	nottoxic_votes = 0

@is_command()
def permission(user, message):
	log(f"Sent permission to {user} - their permission is {user_permission.name}")
	send_message(f"@{user}, your maximum permission is: {user_permission.name}")

@is_command()
def hello(user, message):
	try:
		name = message.split(" ")[1]
	except (ValueError, IndexError):
		name = user

	send_message(f"Hello, {name}! kaywee1AYAYA")
	log(f"Sent Hello to {name} in response to {user}")

@is_command()
def dice(user, message):
	try:
		num = int(message.split(" ")[1])
	except (IndexError, ValueError):
		num = 1

	if num > 10:
		num = 10
			
	sum = 0
	rolls = []

	for _ in range(num):
		roll = random.choice(range(1,7))
		sum += roll
		rolls.append(roll)

	if num == 1:
		send_message(f"{user} rolled a dice and got a {str(sum)}!")
		log(f"Sent a dice roll of {sum} to {user}")
	else:
		send_message(user + f" rolled {num} dice and totalled " + str(sum) + "! " + str(tuple(rolls)))
		log(f"Sent {num} dice rolls to {name}, totalling {sum}")

@is_command()
def fortune(user, message):
	fortune = random.choice(fortunes)
	send_message(f"@{user}, your fortune is: " + fortune)
	log(f"Sent fortune to {user}")

@is_command()
def followgoal(user, message):
	goal = get_data("followgoal")
		
	url = "https://api.twitch.tv/helix/users/follows?to_id=" + kaywee_channel_id
	bearer_token = get_data("app_access_token")

	authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + bearer_token}
	try:
		data = requests.get(url, headers=authorisation_header).json()
		followers = data["total"]
		followers_left = goal - followers
		if followers_left > 0:
			send_message(f"There are only {followers_left:,} followers to go until we hit our follow goal of {goal:,}! kaywee1AYAYA")
			log(f"Sent followergoal of {followers_left} to {user}")
		else:
			send_message(f"The follower goal of {goal:,} has been met! We now have {followers:,} followers! kaywee1AYAYA")
			log(f"Sent followergoal has been met to {user}")
			while goal < followers:
				goal += 100
			set_data("followgoal", goal)
			log(f"Increased followgoal to {goal}")

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
		dlr = round(quantity * get_currencies(base=unit, convert_to="USD"), 2)
		return ("USD", dlr)
	elif unit == "ml":
		pt = round(quantity / 568.261, 3)
		return("pints", pt)

	return -1

def _unfreedom(unit, quantity):
	unit = unit.lower()

	if unit == "f":
		cel = round((quantity-32) * (5/9), 1) #C = (F − 32) × 5/9
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
		result = round(quantity * get_currencies(base="USD", convert_to="GBP"), 2)
		return ("GBP", result)
	elif unit == "pt":
		ml = round(quantity * 568.261, 1)
		return("ml", ml)

	return -1

@is_command()
def tofreedom(user, message):
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
			return

	try:
		quantity = float(input)
	except (ValueError):
		send_message("That doesn't look like a number. Try a number followed by a unit, e.g. '5cm' or '12kg'.")
		return

	try:
		free_unit, free_quantity = _tofreedom(unit, quantity)
	except (ValueError, TypeError):
		send_message("I don't recognise that metric unit. Sorry :(")

	if free_quantity == int(free_quantity): #if the float is a whole number
		free_quantity = int(free_quantity) #convert it to an int (i.e. remove the .0)

	send_message(f"{quantity}{unit} in incomprehensible Freedom Units is {free_quantity}{free_unit}.")

@is_command()
def unfreedom(user, message):
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
			return

	try:
		quantity = float(input)
	except (ValueError):
		send_message("That... doesn't look like a number. Try a number followed by a unit e.g. '5ft' or '10lb'.")
		return

	try:
		sensible_unit, sensible_quantity = _unfreedom(unit, quantity)
	except (ValueError, TypeError):
		send_message("I don't recognise that imperial unit. Sorry! :( PepeHands")

	if sensible_quantity == int(sensible_quantity): #if the float is a whole number
		sensible_quantity = int(sensible_quantity) #convert it to an int (i.e. remove the .0)

	send_message(f"{quantity}{unit} in units which actualy make sense is {sensible_quantity}{sensible_unit}.")


@is_command()
def whogifted(user, message):
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
				return
			send_message(f"@{target}'s current subscription was gifted to them by @{gifter}! Thank you! kaywee1AYAYA ")
			log(f"Sent whogifted (target={target}, gifter={gifter}) in response to user {user}.")
			return
		else:
			send_message(f"@{target} subscribed on their own this time. Thank you! kaywee1AYAYA ")
			log(f"Sent whogifted ({target} subbed on their own) in response to user {user}.")
			return
	else:
		send_message(f"@{target} is not a subscriber. FeelsBadMan")

@is_command()
def howmanygifts(user, message):
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
		if len(message) > 510: #twitch max length
			message = f"{target} has gifted {count} of the current subscriptions! Thanks for the support <3 kaywee1AYAYA"
		send_message(message)
		log(f"Sent {target} has {count} gifted subs, in response to {user}.")

@is_command()
def countdown(user, message):
	try:
		target = message.split(" ")[1]
	except IndexError: # no target specified
		target = user

	if target[0] == "@": # ignore @ tags
		target = target[1:]

	time_left = 1593712800 - time()
	if time_left < 0:
		send_message("Overwatch Season 23 has started!")
		log(f"Sent season 23 start time to {user}, targeting {target}, showing that the season has started.")
	else:
		hours = int(time_left // 3600)
		time_left = time_left % 3600
		mins = int(time_left // 60)
		secs = int(time_left % 60)
		hs = "h" if hours == 1 else "h"
		ms = "m" if mins  == 1 else "m"
		ss = "s" if secs  == 1 else "s"
				
		if hours > 0:
			send_message(f"@{target} Overwatch Season 23 will start in {hours}{hs}, {mins}{ms} and {secs}{ss}!")
		else:
			send_message(f"@{target} Overwatch Season 23 will start in {mins}{ms} and {secs}{ss}!")

		log(f"Sent season 23 start time to {user}, targeting {target}, showing {hours}{hs}, {mins}{ms} and {secs}{ss}")

@is_command()
def toenglish(user, message):
	phrase = " ".join(message.split(" ")[1:])
	if phrase.lower() in ["robokaywee", user, ""]:
		return
	if phrase[0] == "@" and len(phrase.split(" ")) == 1: #parameter is really a username
		phrase = last_message[phrase[1:].lower()]

	english = translator.translate(phrase, source="es", dest="en").text
	send_message(english)
	log(f"Translated \"{phrase}\" into English for {user}: it says \"{english}\"")

@is_command()
def tospanish(user, message):
	phrase = " ".join(message.split(" ")[1:])
	if phrase.lower() in ["robokaywee", user, ""]:
		return
	if phrase[0] == "@" and len(phrase.split(" ")) == 1: #parameter is really a username
		phrase = last_message[phrase[1:].lower()]
	spanish = translator.translate(phrase, source="en", dest="es").text
	send_message(spanish)
	log(f"Translated \"{phrase}\" into Spanish for {user}: it says \"{spanish}\"")

@is_command()
def translate(user, message):
	try:
		source = message.split(" ")[1]
		dest = message.split(" ")[2]
		phrase = " ".join(message.split(" ")[3:])
	except IndexError:
		send_message("Syntax Error. Usage: !translate <sourc_lang> <dest_lang> <text>")

	if phrase.lower() in ["robokaywee", user, ""]:
		return
	if phrase[0] == "@" and len(phrase.split(" ")) == 1: #parameter is really a username
		phrase = last_message[phrase[1:].lower()]
	try:
		output = translator.translate(phrase, source=source, dest=dest).text
		send_message(" " + output)
		log(f"Translated \"{phrase}\" into {dest} for {user}: it says \"{output}\"")
	except ValueError as ex:
		if "language" in str(ex):
			send_message(str(ex))

@is_command()
def lastraid(user, message):
	raid_data = get_data("last_raid")
	name = raid_data["raider"]
	viewers = raid_data["viewers"]
	time = raid_data["time"]

	date_num = datetime.utcfromtimestamp(time).strftime('%d')
	if date_num in [1, 21, 31]:
		suffix = "st"
	elif date_num in [2, 22]:
		suffix = "nd"
	elif date_num in [3, 23]:
		suffix = "rd"
	else:
		suffix = "th"

	date_num = str(date_num).lstrip("0")
	time_str = datetime.utcfromtimestamp(time).strftime("%A " + date_num + suffix + " of %B at %H:%M UTC")

	if viewers == 1:
		plural = ""
	else:
		plural = "s"

	send_message(f"The latest raid was by {name}, who raided with {viewers} viewer{plural} on {time_str}!")

@is_command()
def setcolour(user, message):
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
			send_message("/color HotPink", False)
			sleep(0.9)
			send_message("The Robocolour was updated to HotPink! kaywee1AYAYA")
			set_data("current_colour", "HotPink")
			log(f"Colour was updated to {colour} in response to {user}")
		elif colour == "random":
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

@is_command()
def rainbow(user, message):
	try:
		word = message.split(" ")[1][:12] # 12 chr limit
	except IndexError:
		return

	if word == "":
		return

	for colour in ["red", "coral", "goldenrod", "green", "seagreen", "dodgerblue", "blue", "blueviolet", "hotpink"]:
		send_message(f"/color {colour}", False)
		sleep(0.15)
		send_message(f"/me {word}", False)
		sleep(0.15)

	current_colour = get_data("current_colour")
	sleep(1)
	send_message(f"/color {current_colour}")

@is_command()
def allcolours(user, message):
	for colour in ['blue', 'blueviolet', 'cadetblue', 'chocolate', 'coral', 'dodgerblue', 'firebrick', 'goldenrod', 'green', 'hotpink', 'orangered', 'red', 'seagreen', 'springgreen', 'yellowgreen']:
		send_message(f"/color {colour}", False)
		sleep(0.1)
		send_message(f"/me This is {colour}", False)
		sleep(0.1)

	current_colour = get_data("current_colour")
	send_message(f"/color {current_colour}")

def start_timer(user, time_in, reminder):
	hours = 0
	mins  = 0
	secs  = 0 # defaults

	time_str = time_in[:]

	if "h" in time_str:
		try:
			hours = int(time_str.split("h")[0])
			time_str = time_str.split("h")[1]
		except:
			bot.send_message(f"/me @{user} sorry, I don't recognise that format :(")
			return

	if "m" in time_str:
		try:
			mins = int(time_str.split("m")[0])
			time_str = time_str.split("m")[1]
		except:
			bot.send_message(f"/me @{user} sorry, I don't recognise that format :(")
			return

	if "s" in time_str:
		try:
			secs = int(time_str.split("s")[0])
			time_str = time_str.split("s")[1]
		except:
			bot.send_message(f"/me @{user} sorry, I don't recognise that format :(")
			return

	if secs >= 60 or mins >= 60 or hours >= 24 or time_str!="":
		bot.send_message("/me That time doesn't look right. ")
		return

	timer_time = 60*60*hours + 60*mins + secs

	if timer_time < 30:
		bot.send_message("/me The timer must be for at least 30 seconds.")
		return
	
	bot.send_message(f"/me @{user} - your {time_in} timer has started!")

	log(f"Started {time_str} timer for {user}.")
	sleep(timer_time)

	if reminder != "":
		reminder = ' for "' + reminder + '"'

	bot.send_message(f"/me @{user} your {time_in} timer{reminder} is up! kaywee1AYAYA")

	log(f"{user}'s {timer_time} timer expired.")

@is_command()
def timer(user, message):
	try:
		time_str = message.split(" ")[1]
	except:
		return

	try:
		reminder = " ".join(message.split(" ")[2:])
	except:
		reminder = ""

	timer_thread = Thread(target=start_timer, args=(user,time_str,reminder))
	timer_thread.start()
import random
import random
import requests

from threading import Thread
from time      import sleep, time, localtime
from fortunes  import fortunes
from datetime  import date
from os        import path
from enum      import IntEnum

from chatbot       import ChatBot
from credentials   import bot_name, password, channel_name, tof_name, tof_password, kaywee_channel_id, bearer_token, robovalkia_client_id_2
from API_functions import get_subscribers


mods = {'valkia', 'a_wild_scabdog', 'rabbitsblinkity', 'zenzuwu', 'fareeha', 'theonefoster', 'owgrandma', 'kittehod', 
		'w00dtier', 'theheadspace', 'itspinot', 'dearicarus', 'ademusxp7', 'maggiphi', 'lazalu', 'streamlabs', 'icanpark', 
		'marciodasb', 'littlehummingbird', 'itswh1sp3r', 'samitofps', 'robokaywee', 'gothmom_', 'uhohisharted', 'flasgod', 
		'jabool', "kaywee"}

vips = {"raijin__ow", "cavemanpwr", "kizunaow", "cupcake_ow", "hello_anna", "moirasdamageorb", "imspacemanspiff", "drtinman7"}

currencies = {'CAD', 'HKD', 'ISK', 'PHP', 'DKK', 'HUF', 'CZK', 'GBP', 'RON', 'SEK', 'IDR', 'INR', 'BRL', 'RUB', 'HRK', 'JPY', 'THB', 'CHF', 'EUR', 'MYR', 'BGN', 'TRY', 'CNY', 'NOK', 'NZD', 'ZAR', 'USD', 'MXN', 'SGD', 'AUD', 'ILS', 'KRW', 'PLN'}

bttv_global = {'PedoBear', 'RebeccaBlack', ':tf:', 'CiGrip', 'DatSauce', 'ForeverAlone', 'GabeN', 'HailHelix', 'HerbPerve', 'iDog', 'rStrike', 'ShoopDaWhoop', 'SwedSwag', 'M&Mjc', 'bttvNice', 'TopHam', 'TwaT', 'WatChuSay', 'SavageJerky', 'Zappa', 'tehPoleCat', 'AngelThump', 'HHydro', 'TaxiBro', 'BroBalt', 'ButterSauce', 'BaconEffect', 'SuchFraud', 'CandianRage', "She'llBeRight", 'D:', 'VisLaud', 'KaRappa', 'YetiZ', 'miniJulia', 'FishMoley', 'Hhhehehe', 'KKona', 'PoleDoge', 'sosGame', 'CruW', 'RarePepe', 'iamsocal', 'haHAA', 'FeelsBirthdayMan', 'RonSmug', 'KappaCool', 'FeelsBadMan', 'BasedGod', 'bUrself', 'ConcernDoge', 'FeelsGoodMan', 'FireSpeed', 'NaM', 'SourPls', 'LuL', 'SaltyCorn', 'FCreep', 'monkaS', 'VapeNation', 'ariW', 'notsquishY', 'FeelsAmazingMan', 'DuckerZ', 'SqShy', 'Wowee', 'WubTF', 'cvR', 'cvL', 'cvHazmat', 'cvMask'}
bttv_local = {'PepeHands', 'monkaS', 'POGGERS', 'PepoDance', 'HYPERS', 'BongoCat', 'RareParrot', 'BIGWOW', '5Head', 'WeirdChamp', 'PepeJam', 'KEKWHD', 'widepeepoHappyRightHeart', 'gachiHYPER', 'peepoNuggie', 'MonkaTOS', 'KKool', 'OMEGALUL', 'monkaSHAKE', 'PogUU', 'Clap', 'AYAYA', 'CuteDog', 'weSmart', 'DogePls', 'REEEE', 'BBoomer', 'HAhaa', 'FeelsLitMan', 'POGSLIDE', 'CCOGGERS', 'peepoPANTIES', 'PartyParrot', 'monkaX', 'widepeepoSadBrokenHeart', 'KoolDoge', 'TriDance', 'PepePls', 'gachiBASS', 'pepeLaugh', 'whatBlink', 'FeelsSadMan'}

def log(s):
    """
    Takes a string, s, and logs it to a log file on disk with a timestamp. Also prints the string to console.
    """
    current_time = localtime()
    year   = str(current_time.tm_year)
    month  = str(current_time.tm_mon).zfill(2)
    day    = str(current_time.tm_mday).zfill(2)
    hour   = str(current_time.tm_hour).zfill(2)
    minute = str(current_time.tm_min).zfill(2)
    second = str(current_time.tm_sec).zfill(2)
    
    log_time = day + "/" + month + " " + hour + ":" + minute + ":" + second 

    print(s)
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(log_time + " - " + s + "\n")

class permissions(IntEnum):
	Broadcaster = 10
	Mod         = 8
	VIP         = 6
	Subscriber  = 4
	Follower    = 2
	Pleb        = 0

modwall_size      = 15
supermodwall_size = 30
ultramodwall_size = 50
hypermodwall_size = 100

toxic_poll = False
toxic_votes = 0
nottoxic_votes = 0
voters = set()

with open("subscribers.txt", "r", encoding="utf-8") as f:
	try:
		subscribers = dict(eval(f.read()))
	except Exception as ex:
		log("Exception creating subscriber dictionary: " + str(ex))
		subscribers = dict()

def commit_subscribers():
	with open("subscribers.txt", "w", encoding="utf-8") as f:
		f.write(str(subscribers))

def update_subs():
	while True:
		for sub in list(subscribers):
			if subscribers[sub]["subscribe_time"] < time() - 60*60*24*30:
				del subscribers[sub]
		commit_subscribers()
		sleep(30*60)

sub_thread = Thread(target=update_subs)
sub_thread.start()

def send_message(message):
	global bot

	bot.send_message(message)
	with open("chatlog.txt", "a", encoding="utf-8") as f:
		f.write("robokaywee: " + message + "\n")

def timer(user, time_in, reminder):
	hours = 0
	mins = 0
	secs = 0 #defaults

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
	else:
		bot.send_message(f"/me @{user} - your {time_in} timer has started!")

	sleep(timer_time)

	if reminder != "":
		reminder = ' for "' + reminder + '"'

	bot.send_message(f"/me @{user} your {time_in} timer{reminder} is up! kaywee1AYAYA")

	log(f"{user}'s {time} timer expired.")

def start_toxic_poll():
	global toxic_poll
	global toxic_votes
	global nottoxic_votes
	global voters
	global bot
		
	send_message("/me Poll starting! Type !votetoxic or !votenice to vote on whether the previous game was toxic or nice (one vote per person). Results show in 60 seconds.")
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
			nottoxic_percent = 1

	toxic_percent = round(100*toxic_percent)
	nottoxic_percent = round(100*nottoxic_percent)

	message = f"/me Results are in! Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)"
	
	if nottoxic_votes > toxic_votes:
		send_message(message + " Chat votes that the game was NOT toxic! FeelsGoodMan ")
		send_message("!untoxic")
		log(f"Poll result: not toxic. Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)")

	elif toxic_votes > nottoxic_votes:
		send_message(message + " Chat votes that the game was TOXIC! FeelsBadMan ")
		send_message("!toxic")
		log(f"Poll result: TOXIC. Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)")
	else:
		send_message(message + " Poll was a draw! Chat can't make up its mind! kaywee1Wut ")
		log(f"Poll result: undecided. Toxic: {toxic_votes} votes ({toxic_percent}%) - Nice: {nottoxic_votes} votes ({nottoxic_percent}%)")

	voters = set()
	toxic_votes = 0
	nottoxic_votes = 0

def get_subs():
	global subscribers
	while True:
		subscribers = get_subscribers()
		with open("subscribers.txt", "w", encoding="utf-8") as f:
			out = str(subscribers)
			f.write(out)
		sleep(10*60) # update every 10 mins

#subs_thread = Thread(target=get_subs)
#subs_thread.start()

def respond_message(user, message, permission, emotes=dict()):

	global toxic_poll
	global toxic_votes
	global nottoxic_votes
	global voters

	message_lower = message.lower()

	if any(phrase in message for phrase in ["faggot", "retard"]):
		send_message(f"/timeout {user} 600")
		send_message("We don't say that word here.")
		return

	if message_lower in ["hello", "hi", "hey"]:
		message = "!hello"
		
	if message[0] == "!":
		command = message[1:].split(" ")[0].lower()

		
		if command == "permission":
			send_message(f"Your maximum permission is: {permission.name}")

		if command == "hello":
			try:
				name = message.split(" ")[1]
			except (ValueError, IndexError):
				name = ""

			if name != "":
				send_message("Hello, " + name + "! kaywee1AYAYA")
				log(f"Sent Hello to {name} in response to {user}")
			else:
				send_message("Hello, " + user + "! kaywee1AYAYA")
				log(f"Sent Hello to {user}")

		elif command in ["dice", "roll"]:
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
				send_message(user + " rolled a dice and got a " + str(sum))
				log(f"Sent one dice roll to {user} (they got a {sum})")
			else:
				send_message(user + f" rolled {num} dice and totalled " + str(sum) + " " + str(tuple(rolls)))
				log(f"Sent {num} dice rolls to {name}, totalling {sum}")
		elif command == "fortune":
			fortune = random.choice(fortunes)
			send_message("/me @" + user + ", your fortune is: " + fortune)
			log(f"Sent fortune to {user}")
		elif command == "triangle" and permission >= permissions.VIP:

			try:
				emote = message.split(" ")[1]
			except:
				return

			if emote in bttv_global or emote in bttv_local:
				pass
			else:
				if not emotes:
					send_message("/me You can only triangle with an emote.")
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
					send_message("/me You can only triangle with an emote.")
					return

				if not valid_emote:
					send_message("/me You can only triangle with an emote.")
					return

			num = 3
		
			try:
				num = int(message.split(" ")[2])
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

		elif command in {"followgoal", "followergoal"}:
			goal = get_data("followgoal")
		
			url = "https://api.twitch.tv/helix/users/follows?to_id=" + kaywee_channel_id
			authorisation_header = {"Client-ID": robovalkia_client_id_2, "Authorization":"Bearer " + bearer_token}
			try:
				data = requests.get(url, headers=authorisation_header).json()
				followers = data["total"]
				followers_left = goal - followers
				if followers_left > 0:
					send_message(f"/me There are only {followers_left:,} followers to go until we hit our follow goal of {goal:,}! kaywee1AYAYA")
					log(f"Sent followergoal of {followers_left} to {user}")
				else:
					send_message(f"/me The follower goal of {goal:,} has been met! We now have {followers:,} followers! kaywee1AYAYA")
					log(f"Sent followergoal has been met to {user}")

					goal += 100
					set_data("followgoal", goal)
					log(f"Increased followgoal to {goal}")

					followers_left = goal - followers
					send_message(f"/me There are only {followers_left:,} followers to go until we hit our follow goal of {goal:,}! kaywee1AYAYA")
			except (ValueError, KeyError) as ex:
				print("Error in followgoal command: " + ex)
		elif command == "squid":
			send_message("Squid1 Squid2 Squid3 Squid2 Squid4 ")
			log(f"Sent squid to {user}")
		elif command == "mercy":
			send_message("MercyWing1 PinkMercy MercyWing2 ")
			log(f"Sent Mercy to {user}")
		elif command == "sens":
			send_message("800 DPI, 4.5 in-game")
			log(f"Sent sens to {user}")
		elif command in ["tofreedom", "infreedom"]:
			try:
				input = message.split(" ")[1]
			except (ValueError, IndexError):
				send_message("/me You have to provide something to convert..!")

			unit = ""

			if input == "monopoly":
				send_message("FeelsBadMan")
				return

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
				send_message("That... doesn't look like a number. Try a number followed by e.g. 'cm' or 'ft'.")
				return

			try:
				free_unit, free_quantity = tofreedom(unit, quantity)
			except (ValueError, TypeError):
				send_message("I don't recognise that metric unit. Sorry :(")

			if free_quantity == int(free_quantity): #if the float is a whole number
				free_quantity = int(free_quantity) #convert it to an int (i.e. remove the .0)

			send_message(f"/me {quantity}{unit} in incomprehensible Freedom Units is {free_quantity}{free_unit}.")
		elif command == "unfreedom":
			try:
				input = message.split(" ")[1]
			except (ValueError, IndexError):
				send_message("/me You have to provide something to convert..!")

			unit = ""

			if input == "monopoly":
				send_message("Jebaited")
				return

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
				send_message("That... doesn't look like a number. Try a number followed by e.g. 'cm' or 'ft'.")
				return

			try:
				sensible_unit, sensible_quantity = unfreedom(unit, quantity)
			except (ValueError, TypeError):
				send_message("I don't recognise that imperial unit. Sorry! :( PepeHands")

			if sensible_quantity == int(sensible_quantity): #if the float is a whole number
				sensible_quantity = int(sensible_quantity) #convert it to an int (i.e. remove the .0)

			send_message(f"/me {quantity}{unit} in units which actualy make sense is {sensible_quantity}{sensible_unit}.")
		elif command == "whogifted":
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
					send_message(f"/me @{target}'s current subscriprion was gifted to them by @{gifter}! Thank you! kaywee1AYAYA ")
					log(f"Sent whogifted (target={target}, gifter={gifter}) in response to user {user}.")
					return
				else:
					send_message(f"/me @{target} subscribed on their own this time. Thank you! kaywee1AYAYA ")
					log(f"Sent whogifted ({target} subbed on their own) in response to user {user}.")
					return
			else:
				send_message(f"/me @{target} is not a subscriber. FeelsBadMan")

		elif False and command == "howmanygifts":
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
				message = f"/me {target} has gifted {count} of the current subscriptions to: {recipients}. Thanks for the support <3 kaywee1AYAYA"
				if len(message) > 510: #twitch max length
					message = f"/me {target} has gifted {count} of the current subscriptions! Thanks for the support <3 kaywee1AYAYA"
				send_message(message)
				log(f"Sent {target} has {count} gifted subs, in response to {user}.")

		elif False and command in ["newseason", "season23"]:

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
				ms = "m" if mins == 1 else "m"
				ss = "s" if secs == 1 else "s"
				
				if hours > 0:
					send_message(f"/me @{target} Overwatch Season 23 will start in {hours}{hs}, {mins}{ms} and {secs}{ss}!")
				else:
					send_message(f"/me @{target} Overwatch Season 23 will start in {mins}{ms} and {secs}{ss}!")

				log(f"Sent season 23 start time to {user}, targeting {target}, showing {hours}{hs}, {mins}{ms} and {secs}{ss}")
		elif toxic_poll and user not in voters:
			if command in ["votetoxic", "toxicvote"]:
				toxic_votes += 1
				voters.add(user)
				send_message(f"{user} voted toxic.")
				print(f"Toxic vote from {user}!")
			elif command in ["votenice", "nicevote", "nottoxic", "toxicnot", "nottoxicvote", "untoxicvote", "voteuntoxic"]:
				nottoxic_votes += 1
				voters.add(user)
				send_message(f"{user} voted NOT toxic.")
				print(f"NOTtoxic vote from {user}!")
		if permission >= permissions.Mod:
			if command in ["setcolour", "setcolor"]:
				try:
					colour = message.split(" ")[1]
				except(ValueError, IndexError):
					colour = "default"

				if colour.lower() in ["default", "blue","blueviolet","cadetblue","chocolate","coral","dodgerblue","firebrick","goldenrod","green","hotpink","orangered","red","seagreen","springgreen","yellowgreen"]:
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
						send_message("/color HotPink")
					else:
						send_message("/color " + colour)
					sleep(2)
					send_message("Colour updated! kaywee1AYAYA")
				else:
					send_message("That colour isn't right.")
			elif command == "toxicpoll" and not toxic_poll:
				poll_thread = Thread(target=start_toxic_poll)
				poll_thread.start()
		if permission >= permissions.Subscriber:
			if command == "timer":
				try:
					time_str = message.split(" ")[1]
				except:
					return

				try:
					reminder = " ".join(message.split(" ")[2:])
				except:
					reminder = ""

				timer_thread = Thread(target=timer, args=(user,time_str,reminder))
				timer_thread.start()
				
				log(f"Started {time_str} timer for {user}.")

	#not a command (so message[0] != "!")
	elif message_lower in ["ayy", "ayyy", "ayyyy", "ayyyyy"]:
		send_message("lmao")
		log(f"Sent lmao to {user}")

	elif message == "KEKW":
		send_message("KEKWHD Jebaited")
		log(f"Sent KEKW to {user}")

	elif "@robokaywee" in message_lower:
		send_message("I'm a bot, so I can't reply. Maybe you can try talking to one of the helpful human mods instead.")
		log(f"Sent \"I'm a bot\" to {user}")

	elif message[0] == "^":
		send_message("^")
		log(f"Sent ^ to {user}")

	elif permission < permissions.Subscriber:
		if "bigfollows.com" in message_lower.replace(" ", ""):
			send_message(f"/ban {user}")
			log(f"Banned {user} for linking to bigfollows")

	else: 
		words = message.split(" ")
		if len(words) == 2 and words[0].lower() in ["i'm", "i’m", "im"]:
			send_message(f"/me Hi {words[1]}, I'm Dad! kaywee1AYAYA")
			log(f"Sent Dad to {user}")

def get_data(name):
	try:
		with open("config.txt", "r") as f:
			file = f.read()
			data = dict(eval(file))
	except FileNotFoundError as ex:
		log(f"Failed to get data called {name} - File Not Found.")
		return None
	except ValueError as ex:
		log(f"Failed to get data called {name} - Value Error (corrupt file??)")
		return None

	if name in data:
		return data[name]
	else:
		return None

def set_data(name, value):
	try:
		with open("config.txt", "r") as f:
			file = f.read()
			data = dict(eval(file))
	except FileNotFoundError as ex:
		log(f"Failed to set data of {name} to {value} - File Not Found.")
		return None
	except ValueError as ex:
		log(f"Failed to set data of {name} to {value} - Value Error (corrupt file??)")
		return None

	data[name] = value

	with open("config.txt", "w") as f:
		f.write(str(data))

def tofreedom(unit, quantity):
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

def unfreedom(unit, quantity):
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

def get_currencies(base="USD", convert_to="GBP"):
	base = base.upper()
	result = requests.get(f"https://api.exchangeratesapi.io/latest?base={base}").json()
	rates = result["rates"]
	if convert_to.upper() in rates:
		return rates[convert_to]

if __name__ == "__main__":
	log("Starting bot..")
	bot = ChatBot(bot_name, password, channel_name, debug=False, capabilities=["tags", "commands"])
	#tofbot = ChatBot(tof_name, tof_password, channel_name)

	modwall = 0
	modwall_mods = set()
	gothwall = 0
	vip_wall = 0
	vipwall_vips = set()

	bot_names = {"robokaywee", "streamelements", "nightbot"}

	while True:
		try:
			messages = bot.get_messages()
			for message_dict in messages:
				if message_dict["message_type"] == "privmsg":
					user    = message_dict["display-name"].lower()
					message = message_dict["message"]

					with open("chatlog.txt", "a", encoding="utf-8") as f:
						f.write(f"{user}: {message}\n")

					permission = permissions.Pleb # unless assigned otherwise below:

					if "badges" in message_dict:
						if "broadcaster" in message_dict["badges"]:
							permission = permissions.Broadcaster
						elif "moderator" in message_dict["badges"]:
							permission = permissions.Mod
						elif "vip/1" in message_dict["badges"]:
							permission = permissions.VIP
						elif "subscriber" in message_dict["badges"]:
							permission = permissions.Subscriber

					if "emotes" in message_dict:
						emotes_str = message_dict["emotes"]
						if emotes_str:
							emotes = dict()
							for emote in emotes_str.split("/"):
								id = emote.split(":")[0]
								positions = emote.split(":")[1]

								emotes[id] = positions
						else:
							emotes = dict()
					else:
						emotes = dict()

					if user not in bot_names: #ignore bots
						if message != "" and user != "": #idk why they would be blank but defensive programming I guess
							try:
								respond_message(user, message, permission, emotes)
							except Exception as ex:
								log("Exception in Respond_Message - " + str(ex) + f". Message was {message} from {user}.")

						if permission >= permissions.Mod:
							modwall_mods.add(user)

							if (    modwall <  (modwall_size-1) # few messages
								or (modwall >= (modwall_size-1) and len(modwall_mods) >= 3) #lots of messages and at least 3 mods
							   
							   ): #sadface

								if user != "robokaywee":
									modwall += 1
									if modwall == modwall_size:
										send_message("#modwall ! kaywee1AYAYA")
									elif modwall == supermodwall_size:
										send_message("/me #MEGAmodwall! SeemsGood kaywee1Wut ")
									elif modwall == ultramodwall_size:
										send_message("/me #U L T R A MODWALL TwitchLit kaywee1AYAYA kaywee1Wut")
									elif modwall == hypermodwall_size:
										send_message("/me #H Y P E R M O D W A L L gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1AYAYA kaywee1Wut")
								else:
									if modwall not in [modwall_size-1, supermodwall_size-1, ultramodwall_size-1]: #don't increase it to a modwall number
										modwall += 1
						else:
							if modwall > supermodwall_size:
								if modwall > hypermodwall_size:
									send_message(f"/me Hypermodwall has been broken by {user}! :( FeelsBadMan NotLikeThis")
								elif modwall > ultramodwall_size:
									send_message(f"/me Ultramodwall has been broken by {user}! :( FeelsBadMan NotLikeThis")
								else: # must be >supermodwall
									send_message(f"/me Megamodwall has been broken by {user}! :( FeelsBadMan")

							modwall = 0
							modwall_mods = set()

						if user == "gothmom_":
							gothwall += 1

							#print(gothwall)
						else:
							if gothwall > 6:
								log(f"Gothwall size was {gothwall}")
							gothwall = 0

						if gothwall == 6:
							send_message("/me #GothWall!")
							log("gothwall! :)")
						elif gothwall == 14:
							send_message("/me #MEGAgothwall! kaywee1Wut ")
						elif gothwall == 30:
							send_message("/me #H Y P E R GOTHWALL!! gachiHYPER ")
						elif gothwall == 64:
							send_message("/me #U L T R A G O T H W A L L!! PogChamp gachiHYPER CurseLit ")

						if permission == permissions.VIP:
							vip_wall += 1
							vipwall_vips.add(user)

							if vip_wall == 10:
								send_message("#VIPwall! kaywee1AYAYA")
							elif vip_wall == 20:
								send_message("#SUPER VIPwall! PogChamp")
							elif vip_wall == 50:
								send_message("#MEGA VIPwall! PogChamp Kreygasm CurseLit")
						else:
							vip_wall = 0
							vipwall_vips = set()

				elif message_dict["message_type"] == "notice":
					if "msg-id" in message_dict:
						id = message_dict["msg-id"]
						if "message" in message_dict:
							message = message_dict["message"]
							log(f"NOTICE: {id}: {message}")
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"NOTICE: {id}: {message}\n")
						else:
							log(f"NOTICE with msg-id but no message: {str(message_dict)}")	
					else:
						log(f"NOTICE with no msg-id: {str(message_dict)}")

				elif message_dict["message_type"] == "usernotice":
					if "msg-id" in message_dict:
						"""
						{'sofiara': {'gifter_name': 'freddykalas18', 'is_gift': True, 'tier': '1000', 'user_id': '173548094'}
						"""
						if message_dict["msg-id"] == "subgift": # GIFTED SUBSCRIPTION
							# WORKS! :D
							gifter = message_dict["display-name"].lower()
							recipient = message_dict["msg-param-recipient-display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {gifter} has gifted a subscription to {recipient}\n")
							subscribers[recipient] = {"gifter_name":gifter, "is_gift":True, "subscribe_time":int(time())}
							commit_subscribers()

						elif message_dict["msg-id"] == "sub": # USER SUBSCRIPTION
							# WORKS! :D
							user = message_dict["display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {user} has subscribed!\n")
							subscribers[user] = {"gifter_name":"", "is_gift":False, "subscribe_time":int(time())}
							commit_subscribers()

						elif message_dict["msg-id"] == "resub": # USER RESUBSCRIPTION
							# WORKS! :D
							user = message_dict["display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {user} has resubscribed!\n")
							subscribers[user] = {"gifter_name":"", "is_gift":False, "subscribe_time":int(time())}
							commit_subscribers()

						elif message_dict["msg-id"] == "anonsubgift": # ANONYMOUS GIFTED SUBSCRIPTION
							#comes through as a gifted sub from AnAnonymousGifter ? So might not need this
							recipient = message_dict["msg-param-recipient-display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: Anon has gifted a subscription to {recipient}!\n")
							subscribers[recipient] = {"gifter_name":"AnAnonymousGifter", "is_gift":True, "subscribe_time":int(time())}
							commit_subscribers()

						elif message_dict["msg-id"] == "raid": # RAID
							# WORKS! :D
							raider = message_dict["msg-param-displayName"]
							viewers = message_dict["msg-param-viewerCount"]
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {raider} is raiding with {viewers} viewers!\n")
							send_message(f"/me Wow! {raider} is raiding us with {viewers} new friends! Thank you! kaywee1AYAYA")

						elif message_dict["msg-id"] == "submysterygift":
							gifter = message_dict["login"] # comes as lowercase
							gifts = message_dict["msg-param-mass-gift-count"]

							if gifts != "1":
								log(f"{gifter} has gifted {gifts} subscriptions to the community.")
							else:
								log(f"{gifter} has gifted a subscription to the community.")
							#doesn't tell me who the recipient is
						# other sub msg-ids: sub, resub, subgift, anonsubgift, submysterygift, giftpaidupgrade, rewardgift, anongiftpaidupgrade
					else:
						with open("verbose log.txt", "a", encoding="utf-8") as f:
							f.write("(no msg-id?) - " + str(message_dict) + "\n\n")
				else:
					with open("verbose log.txt", "a", encoding="utf-8") as f:
						f.write(str(message_dict) + "\n\n")
		except Exception as ex:
			log("Exception: " + str(ex))

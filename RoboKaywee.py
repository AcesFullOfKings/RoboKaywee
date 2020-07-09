import random
import requests

from threading     import Thread
from time          import sleep, time, localtime
from fortunes      import fortunes
from datetime      import date
from os            import path

from chatbot       import ChatBot
from credentials   import bot_name, password, channel_name, tof_name, tof_password
from API_functions import get_subscribers


mods = {'valkia', 'a_wild_scabdog', 'rabbitsblinkity', 'zenzuwu', 'fareeha', 'theonefoster', 'owgrandma', 'kittehod', 
		'w00dtier', 'theheadspace', 'itspinot', 'dearicarus', 'ademusxp7', 'maggiphi', 'lazalu', 'streamlabs', 'icanpark', 
		'marciodasb', 'littlehummingbird', 'itswh1sp3r', 'samitofps', 'robokaywee', 'gothmom_', 'uhohisharted', 'flasgod', 
		'jabool', "kaywee"}

currencies = {'CAD', 'HKD', 'ISK', 'PHP', 'DKK', 'HUF', 'CZK', 'GBP', 'RON', 'SEK', 'IDR', 'INR', 'BRL', 'RUB', 'HRK', 'JPY', 'THB', 'CHF', 'EUR', 'MYR', 'BGN', 'TRY', 'CNY', 'NOK', 'NZD', 'ZAR', 'USD', 'MXN', 'SGD', 'AUD', 'ILS', 'KRW', 'PLN'}

modwall_size      = 15
supermodwall_size = 30
ultramodwall_size = 50
hypermodwall_size = 100

# Create subscribers object from disk if available:
#if path.exists("subscribers.txt"):
#	with open("subscribers.txt", "r", encoding="utf-8") as f:
#		try:
#			raw = f.read()
#			d = eval(raw)
#			subscribers = dict(d)
#		except:
#			subscribers = dict()
#else:
#	subscribers = dict()

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

def respond_message(user, message):

	if any(phrase in message for phrase in ["faggot", "retard"]):
		bot.send_message(f"/timeout {user} 600")
		bot.send_message("We don't say that word here.")
		return

	if message in ["hello", "hi", "hey"]:
		message = "!hello"
		
	if message[0] == "!":
		command = message[1:].split(" ")[0].lower()

		if command == "hello":
			try:
				name = message.split(" ")[1]
			except (ValueError, IndexError):
				name = ""

			if name != "":
				bot.send_message("Hello, " + name + "! kaywee1AYAYA")
				log(f"Sent Hello to {name} in response to {user}")
			else:
				bot.send_message("Hello, " + user + "! kaywee1AYAYA")
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
				bot.send_message(user + " rolled a dice and got a " + str(sum))
				log(f"Sent one dice roll to {user} (they got a {sum})")
			else:
				bot.send_message(user + f" rolled {num} dice and totalled " + str(sum) + " " + str(tuple(rolls)))
				log(f"Sent {num} dice rolls to {name}, totalling {sum}")
		elif command == "fortune":
			fortune = random.choice(fortunes)
			bot.send_message(user + ", your fortune is: " + fortune)
			log(f"Sent fortune to {user}")
		elif command == "triangle" and user in mods:
			try:
				emote = message.split(" ")[1]
			except:
				return
			
			num = 3
		
			try:
				num = int(message.split(" ")[2])
			except IndexError:
				pass #leave it at 3
			except ValueError: #if conversion to int fails, e.g. int("hello")
				num = 3
			
			if emote != "":
				if num > 12:
					num = 12
		
				counts = list(range(1,num+1)) + list(range(1,num)[::-1])
				for count in counts:
					bot.send_message((emote + " ") * count)
				log(f"Send triangle of {emote} of size {num} to {user}")

		elif command in {"followgoal", "followergoal"}:
			goal = get_data("followgoal")
		
			url = "https://api.twitch.tv/helix/users/follows?to_id=136108665"
			robovalkia_client_id_2 = "q6batx0epp608isickayubi39itsckt" 
			authorisation_header = {"Client-ID": robovalkia_client_id_2, "Authorization":"Bearer o5mqm459duhiodt1s7vyd27zfgq2ys"}
			try:
				data = requests.get(url, headers=authorisation_header).json()
				followers = data["total"]
				followers_left = goal - followers
				if followers_left > 0:
					bot.send_message("/me There are only {f} followers to go until we hit our follow goal of {g}! kaywee1AYAYA".format(f=f'{followers_left:,}', g=f'{goal:,}'))
					log(f"Sent followergoal of {followers_left} to {user}")
				else:
					bot.send_message("/me The follower goal of {g} has been met! We now have {f} followers! kaywee1AYAYA".format(f=f'{followers:,}',g=f'{goal:,}'))
					log(f"Sent followergoal has been met to {user}")
			except (ValueError, KeyError) as ex:
				print("Error in followgoal command: " + ex)
		elif command == "squid":
			bot.send_message("Squid1 Squid2 Squid3 Squid2 Squid4 ")
			log(f"Sent squid to {user}")
		elif command == "mercy":
			bot.send_message("MercyWing1 PinkMercy MercyWing2 ")
			log(f"Sent Mercy to {user}")
		elif command == "sens":
			bot.send_message("800 DPI, 4.5 in-game")
			log(f"Sent sens to {user}")
		elif command in ["tofreedom", "infreedom"]:
			try:
				input = message.split(" ")[1]
			except (ValueError, IndexError):
				bot.send_message("/me You have to tell me what you want me to convert..!")

			unit = ""

			if input == "monopoly":
				bot.send_message("FeelsBadMan")
				return

			while input[-1] not in "0123456789": 
				if input[-1] != " ":
					unit = input[-1] + unit  # e.g. cm or kg
				input = input[:-1]
				if len(input) == 0:
					bot.send_message("You have to give me a quantity to convert.")
					return

			try:
				quantity = float(input)
			except (ValueError):
				bot.send_message("That... doesn't look like a number to me. Try a number followed by 'cm' or 'c'.")
				return

			try:
				free_unit, free_quantity = tofreedom(unit, quantity)
			except (ValueError, TypeError):
				bot.send_message("I don't recognise that metric unit. Sorry :(")

			bot.send_message(f"/me {quantity}{unit} in incomprehensible Freedom Units is {free_quantity}{free_unit}.")
		elif command == "unfreedom":
			try:
				input = message.split(" ")[1]
			except (ValueError, IndexError):
				bot.send_message("/me You have to tell me what you want me to convert..!")

			unit = ""

			if input == "monopoly":
				bot.send_message("Jebaited")
				return

			while input[-1] not in "0123456789": 
				if input[-1] != " ":
					unit = input[-1] + unit  # e.g. cm or kg
				input = input[:-1]
				if len(input) == 0:
					bot.send_message("You have to give me a quantity to convert.")
					return

			try:
				quantity = float(input)
			except (ValueError):
				bot.send_message("That... doesn't look like a number to me. Try a number followed by 'cm' or 'c'.")
				return

			try:
				sensible_unit, sensible_quantity = unfreedom(unit, quantity)
			except (ValueError, TypeError):
				bot.send_message("I don't recognise that imperial unit. Sorry :(")

			bot.send_message(f"/me {quantity}{unit} in units which actualy make sense is {sensible_quantity}{sensible_unit}.")
		elif False and command == "whogifted":
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
					bot.send_message("/me @{target}'s current subscriprion was gifted to them by @{gifter}! Thank you! kaywee1AYAYA ".format(target=target, gifter=gifter))
					log("Sent whogifted (target={t}, gifter={g}) in response to user {u}.".format(t=target, g=gifter, u=user))
					return
				else:
					bot.send_message("/me @{target} subscribed on their own this time. Thank you! kaywee1AYAYA ".format(target=target))
					log("Sent whogifted (target {t} subbed on their own) in response to user {u}.".format(u=user, t=target))
					return
			else:
				bot.send_message("/me @{target} is not a subscriber. FeelsBadMan".format(target=target))
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
				gifter = subscribers[sub]["gifter_name"].lower()
				if gifter == target:
					recipients += sub + ", "
					count += 1
		
			if count == 0:
				bot.send_message("None of the current subscribers were gifted by {t}.".format(t=target))
				log(f"Sent {target} has no gifted subs, in response to {user}.")
			else:
				recipients = recipients[:-2]
				message = "/me {t} has gifted subscriptions to: {recipients}. That's {c} gifts! Thanks for the support <3 kaywee1AYAYA".format(c=count, t=target, recipients=recipients)
				if len(message) > 510: #twitch max length
					message = "/me {t} has gifted subscriptions to {c} of the current subscribers! Thanks for the support <3 kaywee1AYAYA".format(c=count, t=target)
				bot.send_message(message)
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
				bot.send_message("Overwatch Season 23 has started!")
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
					bot.send_message(f"/me @{target} Overwatch Season 23 will start in {hours}{hs}, {mins}{ms} and {secs}{ss}!")
				else:
					bot.send_message(f"/me @{target} Overwatch Season 23 will start in {mins}{ms} and {secs}{ss}!")

				log(f"Sent season 23 start time to {user}, targeting {target}, showing {hours}{hs}, {mins}{ms} and {secs}{ss}")
		elif user in mods:
			if command == "addpoints":
				try:
					target = message.split(" ")[1]
					points = int(message.split(" ")[2])
				except(ValueError, IndexError):
					return

				bot.send_message(f"/me {user} has gifted {points} points to {target}!")
				return
			elif command in ["setcolour", "setcolor"]:
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
						bot.send_message("/color HotPink")
					else:
						bot.send_message("/color " + colour)
					sleep(2)
					bot.send_message("Colour updated! kaywee1AYAYA")
				else:
					bot.send_message("That colour isn't right.")


	elif message.lower() in ["ayy", "ayyy", "ayyyy", "ayyyyy"]:
		bot.send_message("lmao")
		log(f"Sent lmao to {user}")

	elif "@robokaywee" in message.lower():
		bot.send_message("I'm a bot, so I can't help you. Maybe you can try talking to one of the helpful human mods instead.")

	else: #not a command (so message[0] != "!")
		words = message.split(" ")
		if len(words) == 2 and words[0].lower() == "i'm":
			bot.send_message("/me Hi {word}, I'm Dad! kaywee1AYAYA".format(word=words[1]))
			log(f"Sent Dad to {user}")



def get_data(name):
	try:
		with open("config.txt", "r") as f:
			file = f.read()
			data = dict(eval(file))
	except FileNotFoundError as ex:
		return None
	except ValueError as ex:
		return None

	if name in data:
		return data[name]
	else:
		return None

def set_data(name, value):
	with suppress(FileNotFoundError, ValueError):
		with open("config.txt", "r") as f:
			file = f.read()
			data = dict(eval(file))
	#except FileNotFoundError as ex:
	#	return None
	#except ValueError as ex:
	#	return None

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
		dlr = round(quantity * get_currencies(base=unit, convert_to="USD"), 3)
		return ("USD", dlr)


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
		result = round(quantity * get_currencies(base="USD", convert_to="GBP"), 3)
		return ("GBP", result)

	return -1

def get_currencies(base="USD", convert_to="GBP"):
	base = base.upper()
	result = requests.get(f"https://api.exchangeratesapi.io/latest?base={base}").json()
	rates = result["rates"]
	if convert_to.upper() in rates:
		return rates[convert_to]

if __name__ == "__main__":
	log("Starting bot..")
	bot = ChatBot(bot_name, password, channel_name, debug=False)
	#tofbot = ChatBot(tof_name, tof_password, channel_name)

	#respond_message("theonefoster", "!unfreedom 90USD")

	msg_count = 0
	modwall = 0
	modwall_mods = set()
	gothwall = 0

	while True:
		messages = bot.get_messages()
		for user, message in messages:
			if user not in ["robokaywee", "streamelements"]: #ignore bots
				if message != "" and user != "": #idk why they would be blank but defensive programming I guess
					try:
						respond_message(user, message)
					except Exception as ex:
						log("Exception in Respond_Message - " + str(ex) + f". Message was {message} from {user}.")
					msg_count+=1

				if user in mods:
					modwall_mods.add(user)

					if (    modwall <  (modwall_size-1) # few messages
						or (modwall >= (modwall_size-1) and len(modwall_mods) >= 3) #lots of messages and at least 3 mods
					   ):
						
						if user != "robokaywee":
							modwall += 1
							if modwall == modwall_size:
								bot.send_message("#modwall ! kaywee1AYAYA")
							elif modwall == supermodwall_size:
								bot.send_message("/me #MEGAmodwall! SeemsGood kaywee1Wut ")
							elif modwall == ultramodwall_size:
								bot.send_message("/me #U L T R A MODWALL TwitchLit kaywee1AYAYA kaywee1Wut")
							elif modwall == hypermodwall_size:
								bot.send_message("/me #H Y P E R M O D W A L L gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1AYAYA kaywee1Wut")
						else:
							if modwall not in [modwall_size-1, supermodwall_size-1, ultramodwall_size-1]: #don't increase it to a modwall number
								modwall += 1
				else:
					if modwall > hypermodwall_size:
						bot.send_message(f"/me Hypermodwall has been broken by {user}! :( FeelsBadMan NotLikeThis")
					elif modwall > ultramodwall_size:
						bot.send_message(f"/me Ultramodwall has been broken by {user}! :( FeelsBadMan NotLikeThis")
					elif modwall > supermodwall_size:
						bot.send_message(f"/me Megamodwall has been brokenby {user}! :( FeelsBadMan")

					modwall = 0
					modwall_mods = set()

				if user == "gothmom_":
					gothwall += 1
					#print(gothwall)
				elif user not in ["robokaywee", "streamelements"]:
					gothwall = 0

				if gothwall == 6:
					bot.send_message("/me #GothWall!")
					log("gothwall! :)")
				elif gothwall == 12:
					bot.send_message("/me #MEGAgothwall! kaywee1Wut ")
				elif gothwall == 20:
					bot.send_message("/me #H Y P E R GOTHWALL!! gachiHYPER ")
				elif gothwall == 40:
					bot.send_message("/me #H Y P E R G O T H W A L L!! PogChamp gachiHYPER CurseLit ")

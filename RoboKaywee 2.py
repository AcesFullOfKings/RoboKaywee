#import sqlite3 # one day maybe I'll use an actual database LOL
import praw
import random
import requests

from time        import time, sleep, localtime
from enum        import IntEnum
from math        import ceil
from chatbot     import ChatBot # see https://github.com/theonefoster/pyTwitchChatBot
from datetime    import date, datetime
from threading   import Thread, Lock
from credentials import bot_name, password, channel_name, kaywee_channel_id, bearer_token, robokaywee_client_id

import commands as commands_file
from API_functions import get_app_access_token

"""
TODO:

should be able to add counters and variables to text commands
should be able to give any command multiple names via aliases

"""

command_lock = Lock()
config_lock = Lock()
subs_lock = Lock()
usernames_lock = Lock()

bots = {"robokaywee", "streamelements", "nightbot"}
channel_emotes = {"kaywee1AYAYA", "kaywee1Wut", "kaywee1Dale", "kaywee1Imout", "kaywee1GASM"}

modwalls = {
	15:  {"name": "Modwall",                 "emotes": "kaywee1AYAYA"},
	30:  {"name": "MEGAmodwall",             "emotes": "SeemsGood kaywee1Wut"},
	50:  {"name": "HYPER MODWALL",           "emotes": "TwitchLit kaywee1AYAYA kaywee1Wut"},
	100: {"name": "U L T R A MODWALL",       "emotes": "kaywee1AYAYA PogChamp Kreygasm CurseLit"},
	250: {"name": "G I G A M O D W A L L",   "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut"},
	500: {"name": "T E R R A M O D W A L L", "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut"},
	# I guarantee none of these will ever be reached naturally, but..
	1000:{"name": "PETAMODWALL",             "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut"},
	2000:{"name": "EXAMODWALL",              "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut"},
	3000:{"name": "ZETTAMODWALL",            "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut"},
	4000:{"name": "YOTTAMODWALL",            "emotes": "kaywee1AYAYA gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1Wut"},
	# also I know that the SI prefixes don't make sense with the numbers but whatever, I needed increasing prefixes
}

with open("usernames.txt", "r", encoding="utf-8") as f:
	usernames = set(f.read().split("\n"))

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
	
	log_time = f"{day}/{month} {hour}:{minute}:{second}"

	print(s)
	with open("log.txt", "a", encoding="utf-8") as f:
		f.write(log_time + " - " + s + "\n")

with open("commands.txt", "r", encoding="utf-8") as f:
	commands_dict = dict(eval(f.read()))

with open("subscribers.txt", "r", encoding="utf-8") as f:
	try:
		subscribers = dict(eval(f.read()))
	except Exception as ex:
		log("Exception creating subscriber dictionary: " + str(ex))
		subscribers = {}

last_wiki_update = 0
def update_commands_wiki(force_update_reddit=False):
	global last_wiki_update
	
	if force_update_reddit or last_wiki_update < time() - 60*30: # don't update more often than 30 mins unless forced
		permissions = {0:"Pleb", 2:"Follower", 4:"Subscriber", 6:"VIP", 8:"Mod", 10:"Broadcaster", 12:"Disabled"}

		r = praw.Reddit("RoboKaywee")
		subreddit = r.subreddit("RoboKaywee")

		if command_lock.acquire(timeout=10):
			with open("commands.txt", "r", encoding="utf-8") as f:
				commands = dict(eval(f.read()))

			command_lock.release()

			table = "**Note: all commands are now sent with /me so will display in the bot's colour.**\n\n\n**Command**|**Level**|**Response/Description**|**Uses**\n---|---|---|---\n"

			for command in sorted(commands):
				if "permission" in commands[command]:
					try:
						level = permissions[commands[command]["permission"]]
					except KeyError:
						level = "Pleb"
				else:
					level = "Pleb"

				if "uses" in commands[command]:
					uses = commands[command]["uses"]
				else:
					uses = "-"

				if commands[command]["coded"]:
					if "description" in commands[command]:
						description = commands[command]['description'].replace("|", "/") # pipes break the formatting on the reddit wiki
						table += f"{command}|{level}|Coded: {description}|{uses}\n"
					else:
						table += f"{command}|{level}|Coded command with no description.|{uses}\n"
				else:
					if "response" in commands[command]:
						response = commands[command]['response'].replace("|", "/") # pipes break the formatting on the reddit wiki
						table += f"{command}|{level}|Response: {response}|{uses}\n"
					else:
						table += f"{command}|{level}|Text command with no response.|{uses}\n"

			subreddit.wiki["commands"].edit(table)
			last_wiki_update = time()
		else:
			log("Warning: Command Lock timed out on update_commands_wiki() !!")

def write_command_data(force_update_reddit=False):
	global commands_dict

	if command_lock.acquire(timeout=3):
		with open("commands.txt", "w", encoding="utf-8") as f:
			f.write(str(commands_dict).replace("},", "},\n"))
		command_lock.release()

		update_thread = Thread(target=update_commands_wiki, args=(force_update_reddit,))
		update_thread.start()
	else:
		log("Warning: Command Lock timed out on write_command_data() !!")

def commit_subscribers():
	if command_lock.acquire(timeout=3):
		with open("subscribers.txt", "w", encoding="utf-8") as f:
			f.write(str(subscribers))
		command_lock.release()
	else:
		log("Warning: Subs Lock timed out in commit_subscribers() !!")

def add_new_username(username):
	send_message(f"Welcome to Kaywee's channel {username}! Get cosy and enjoy your stay kaywee1AYAYA  <3")
	log(f"Welcomed new user {username}")

	global usernames	
	usernames.add(username)

	with open("usernames.txt", "w", encoding="utf-8") as f:
		f.write("\n".join(usernames))

def get_title():
	url = "https://api.twitch.tv/helix/streams?user_id=" + kaywee_channel_id
	authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + get_data("app_access_token")}
	
	while True:
		try:
			title = requests.get(url, headers=authorisation_header).json()["data"][0]["title"]

		except (IndexError, KeyError): # streamer isn't live
			pass
		else:
			with open("titles.txt", "r", encoding="utf-8") as f:
				titles = f.read().split("\n")

			if title not in titles: # only unique titles
				titles.append(title)
				with open("titles.txt", "w", encoding="utf-8") as f:
					f.write("\n".join(titles))

		sleep(60*60) # once per hour

def set_random_colour():
	days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
	
	while True:
		today_name = days[date.today().weekday()]
		lastday = get_data("lastday")
		
		if lastday is None or lastday != today_name:
			set_data("lastday", today_name)
			if today_name == "Wednesday":
				send_message("/color HotPink", False)
				set_data("current_colour", "HotPink")
				log(f"Colour was updated to HotPink in response to Timed Event")
			else:
				colours = ["blue","blueviolet","cadetblue","chocolate","coral","dodgerblue","firebrick","goldenrod","green","hotpink","orangered","red","seagreen","springgreen","yellowgreen"]
				new_colour = random.choice(colours)
				send_message("/color " + new_colour, False)
				set_data("current_colour", new_colour)
				log(f"Colour was updated to {new_colour} in response to Timed Event")

		sleep(60*60)

def it_is_wednesday_my_dudes():
	sleep(20*60) # wait 20 mins into the stream
	while True:
		if date.today().weekday() == 2: # if it's stil wednesday
			url = "https://api.twitch.tv/helix/streams?user_id=" + kaywee_channel_id
			authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + get_data("app_access_token")}

			try:
				# try getting the title of the stream to test if streamer is live:
				title = requests.get(url, headers=authorisation_header).json()["data"][0]["title"]
			except (IndexError, KeyError): # streamer isn't live
				pass
			else:
				send_message("On Wednesdays we wear pink. If you want to sit with us type /color HotPink to update your username colour.")
				log("Sent Pink reminder.")
		sleep(60*60)

def it_is_Thursday_my_dudes():
	sleep(20*60) # wait 20 mins into the stream
	send_message("On Thursdays we wear whatever colour we want. Set your username colour by using /color and sit with us.")
	log("Sent UnPink reminder.")

def it_is_worldday_my_dudes():
	sleep(5*60) # wait 5 mins into stream
	commands_file.worldday({"display-name":"Timed Event"}) #have to include a message dict param

def update_subs():
	while True:
		for sub in list(subscribers):
			if subscribers[sub]["subscribe_time"] < time() - 60*60*24*30:
				del subscribers[sub]
		commit_subscribers()
		sleep(30*60)

def get_data(name):
	try:
		if config_lock.acquire(timeout=3):
			with open("config.txt", "r") as f:
				file = f.read()
				data = dict(eval(file))
				config_lock.release()
		else:
			log("WARNING: config_lock timed out in get_data() !!")
			return None
	except FileNotFoundError as ex:
		log(f"Failed to get data called {name} - File Not Found.")
		return None
	except ValueError as ex:
		log(f"Failed to get data called {name} - Value Error (corrupt file??)")
		return None

	return data[name] # -> intentionally doesn't handle KeyError

def set_data(name, value):
	try:
		if config_lock.acquire(timeout=3):
			with open("config.txt", "r") as f:
				file = f.read()
				data = dict(eval(file))
				config_lock.release()
		else:
			log("WARNING: config_lock timed out (while reading) in set_data() !!")
			return
	except FileNotFoundError as ex:
		log(f"Failed to set data of {name} to {value} - File Not Found.")
		return
	except ValueError as ex:
		log(f"Failed to set data of {name} to {value} - Value Error (corrupt file?)")
		return

	data[name] = value

	if config_lock.acquire(timeout=3):
		with open("config.txt", "w") as f:
			f.write(str(data).replace(", ", ",\n"))
		config_lock.release()
	else:
		log("WARNING: config_lock timed out (while writing) in set_data() !!")
		return

def update_app_access_token():
	while True:
		url = "https://id.twitch.tv/oauth2/validate"

		try:
			current_token = get_data("app_access_token")
			assert current_token is not None

			authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + current_token}
			
			response = requests.get(url, headers=authorisation_header).json()
			expires_in = response["expires_in"]
		except AssertionError:
			log("No Access Token was found in config.txt. Fetching a new one..")
			expires_in = 0
		except Exception as ex:
			log("Exception when fetching App Access Token: " + str(ex))
			expires_in = 0

		if expires_in < 48*60*60: #if token expires in the next 48h
			set_data("app_access_token", get_app_access_token()) # get a new one

		sleep(23*60*60) # wait 23 hours

def send_message(message, add_to_chatlog=True, suppress_colour=False):
	"""
	Will also be accessible from the commands file.
	"""

	#if False: # -> allows me to run the bot silently during testing
	#	print("SEND_MESASGE FUNCTION IS DISABLED!")
	#	return

	if message.startswith("/") or suppress_colour:
		bot.send_message(message)
	else:
		bot.send_message("/me " + message)
	if add_to_chatlog:
		with open("chatlog.txt", "a", encoding="utf-8") as f:
			f.write("robokaywee: " + message + "\n")

def check_cooldown(command_name, user):
	command_time = ceil(time())
	cmd_data = commands_dict[command_name]

	def check_user_cooldown():
		if "user_cooldown" in cmd_data:
			if user in user_cooldowns:
				if command_name in user_cooldowns[user]:
					if user_cooldowns[user][command_name] < command_time - cmd_data["user_cooldown"]:
						user_cooldowns[user][command_name] = command_time
						return True
					else:
						return False
				else:
					user_cooldowns[user][command_name] = command_time
					return True
			else:
				user_cooldowns[user] = {command_name:command_time}
				return True
		else:
			cmd_data["last_used"] = command_time
			return True

	if "global_cooldown" in cmd_data:
		if "last_used" in cmd_data:
			if cmd_data["last_used"] < command_time - cmd_data["global_cooldown"]:
				return check_user_cooldown()
			else:
				return False
		else:
			return check_user_cooldown()
	else:
		return check_user_cooldown()

class permissions(IntEnum):
	Disabled    = 12
	Broadcaster = 10
	Mod	        = 8
	VIP	        = 6
	Subscriber  = 4
	Follower    = 2
	Pleb        = 0

def respond_message(message_dict):
	# For random non-command responses/rules
	global pink_reminder_sent

	user       = message_dict["display-name"].lower()
	message    = message_dict["message"]
	permission = message_dict["user_permission"]

	message_lower = message.lower()

	if "@robokaywee" in message_lower:
		send_message(f"@{user} I'm a bot, so I can't reply. Try talking to one of the helpful human mods instead.")
		log(f"Sent \"I'm a bot\" to {user}")

	elif commands_file.nochat_on and "kaywee" in message_lower and user not in bots and all(emote not in message for emote in channel_emotes):
		if "nochat" in commands_dict and "response" in commands_dict["nochat"]:
			send_message(f"@{user} {commands_dict['nochat']['response']}")
			log(f"Sent nochat to {user} in response to @kaywee during nochat mode.")

	elif permission < permissions.Subscriber: #works in 2.0
		msg_without_spaces = message_lower.replace(" ", "")
		if any(x in msg_without_spaces for x in ["bigfollows.com", "bigfollows*com", "bigfollowsdotcom"]):
			send_message(f"/ban {user}")
			log(f"Banned {user} for linking to bigfollows")

	# EASTER EGGS:
	
	elif message[0] == "^":
		send_message("^", suppress_colour=True)
		log(f"Sent ^ to {user}")

	elif message_lower in ["ayy", "ayyy", "ayyyy", "ayyyyy"]:
		send_message("lmao")
		log(f"Sent lmao to {user}")

	elif message == "KEKW":
		send_message("KEKWHD Jebaited")
		log(f"Sent KEKW to {user}")

	elif message_lower in ["hewwo", "hewwo?", "hewwo??"]:
		send_message("HEWWO! UwU kaywee1AYAYA")
		log(f"Sent hewwo to {user}")

	elif message_lower == "hello there":
		send_message("General Keboni")
		log(f"Sent Kenobi to {user}")
	elif "romper" in message_lower:
		send_message("!romper")
		log(f"Sent romper to {user}")

	# Scheduled Messages:

	elif user == "streamelements" and "kaywee is now live!" in message:
		worldday_thread = Thread(target=it_is_worldday_my_dudes)
		worldday_thread.start()

		send_message("!resetrecord", suppress_colour=True)

		if date.today().weekday() == 2: # and not pink_reminder_sent
			wednesday_thread = Thread(target=it_is_wednesday_my_dudes)
			wednesday_thread.start()
			pink_reminder_sent = True
			set_data("pink_reminder_sent", True)

update_command_data = False

#check for new commands and add to database:
for command_name in [o for o in dir(commands_file) if not(o.startswith("_") or o.endswith("_"))]:
	try:
		if getattr(commands_file, command_name).is_command:
			if command_name not in commands_dict:
				commands_dict[command_name] = {'permission': 0, 'global_cooldown': 1, 'user_cooldown': 0, 'coded': True, 'uses': 0, "description": getattr(commands_file, command_name).description}
				update_command_data = True
			else:
				if commands_dict[command_name]["description"] != getattr(commands_file, command_name).description:
					commands_dict[command_name]["description"] = getattr(commands_file, command_name).description # update description
					update_command_data = True
	except AttributeError:
		pass

if update_command_data:
	write_command_data(False)

del update_command_data

if __name__ == "__main__":
	log("Starting bot..")
	bot = ChatBot(bot_name, password, channel_name, debug=False, capabilities=["tags", "commands"])

	user_cooldowns = {}

	app_token_thread = Thread(target=update_app_access_token)
	app_token_thread.start()

	sub_thread = Thread(target=update_subs)
	sub_thread.start()

	randcolour_thread = Thread(target=set_random_colour)
	randcolour_thread.start()

	titles_thread = Thread(target=get_title)
	titles_thread.start()

	modwall_mods      = set()
	modwall           = 0
	current_modwall   = None
	#modwall_size      = 15
	#supermodwall_size = 30
	#ultramodwall_size = 50
	#hypermodwall_size = 100

	if date.today().weekday() == 2: # if it's Wednesday (my dudes)
		pink_reminder_sent = get_data("pink_reminder_sent")		
	else: # if it's not wednesday
		set_data("pink_reminder_sent", False)
		pink_reminder_sent = False

	vip_wall = 0
	vipwall_vips = set()

	last_message = {}

	wednesday_thread = Thread(target=it_is_wednesday_my_dudes)
	wednesday_thread.start()
	
	# let commands file access key data:
	commands_file.bot                = bot
	commands_file.send_message       = send_message
	commands_file.log                = log
	commands_file.command_dict       = commands_dict
	commands_file.write_command_data = write_command_data
	commands_file.get_data           = get_data
	commands_file.set_data           = set_data
	commands_file.last_message       = last_message
	commands_file.nochat_on          = False
	commands_file.permissions        = permissions

	while True:
		try:
			messages = bot.get_messages()
			for message_dict in messages:
				if message_dict["message_type"] == "privmsg":
					user	= message_dict["display-name"].lower()
					message = message_dict["message"]

					with open("chatlog.txt", "a", encoding="utf-8") as f:
						f.write(f"{user}: {message}\n")

					if user not in usernames:
						Thread(target=add_new_username,args=(user,)).start() # probably saves like.. idk 10ms? over just calling it. lol. trims reaction time though

					message_lower = message.lower()

					if message_lower in ["hello", "hi", "hey", "hola"]:
						message = "!hello"

					last_message[user] = message
					user_permission = permissions.Pleb # unless assigned otherwise below:
						
					if "badges" in message_dict:
						if "broadcaster" in message_dict["badges"]:
							user_permission = permissions.Broadcaster
						elif "moderator" in message_dict["badges"]:
							user_permission = permissions.Mod
						elif "vip/1" in message_dict["badges"]:
							user_permission = permissions.VIP
						elif "subscriber" in message_dict["badges"]:
							user_permission = permissions.Subscriber

					message_dict["user_permission"] = user_permission

					if message.startswith("!"):
						command = message[1:].split(" ")[0].lower()
						if command in ["win", "loss", "draw"]:
							command = "toxicpoll"
						if command in commands_dict:
							command_obj = commands_dict[command]

							if user_permission >= command_obj["permission"] and check_cooldown(command, user):
								if command_obj["coded"]:
									if command in dir(commands_file):
										func = getattr(commands_file, command)
										if func.is_command:
											if func(message_dict) != False: # None != False in case anything returns None
												if "uses" in command_obj:
													command_obj["uses"] += 1
												else:
													command_obj["uses"] = 1

												command_obj["last_used"] = time()
												write_command_data(False)
												
										else:
											log(f"WARNING: tried to call non-command function: {command}")
									else:
										log(f"WARNING: Stored coded command with no function: {command}")
								else:
									if "response" in command_obj:
										words = message.split(" ")
										if len(words) == 2 and words[1].startswith("@"):
											msg_to_send = words[1] + " " + command_obj["response"]
										else:
											msg_to_send = command_obj["response"]
										send_message(msg_to_send)
										log(f"Sent {command} in response to {user}.")
										if "uses" in command_obj:
											command_obj["uses"] += 1
										else:
											command_obj["uses"] = 1

										command_obj["last_used"] = time()
										write_command_data(False)
									else:
										log(f"WARNING: Stored text command with no response: {command}")

					else:
						respond_message(message_dict)

					if user_permission >= permissions.Mod:
						modwall_mods.add(user)

						# don't send modwall unless there are at least 3 mods in the wall
						if (    modwall <  14 # few messages
							or (modwall >= 14 and len(modwall_mods) >= 3) # lots of messages and at least 3 mods
							   
							): # sadface

							modwall += 1
							if modwall in modwalls:
								modwall_data = modwalls[modwall]
								current_modwall = modwall_data["name"] 

								send_message(f"#{current_modwall}! {modwall_data['emotes']}")
								log(f"{current_modwall}!")

							#if modwall == modwall_size:
							#	send_message("#Modwall! kaywee1AYAYA")
							#elif modwall == supermodwall_size:
							#	send_message("#MEGAmodwall! SeemsGood kaywee1Wut")
							#elif modwall == ultramodwall_size:
							#	send_message("#U L T R A MODWALL TwitchLit kaywee1AYAYA kaywee1Wut")
							#elif modwall == hypermodwall_size:
							#	send_message("#H Y P E R M O D W A L L gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1AYAYA kaywee1Wut")
					else:
						if modwall > 30:
							send_message(f"{current_modwall} has been broken by {user}! :( FeelsBadMan NotLikeThis PepeHands")

						modwall = 0
						modwall_mods = set()
						current_modwall = None

					# future me: don't indent this (otherwise mods can't interrupt vipwalls)
					if user_permission == permissions.VIP:
						vip_wall += 1

						if vip_wall == 10:
							send_message("#VIPwall! kaywee1AYAYA")
							log("VIPwall!")
						elif vip_wall == 20:
							send_message("#SUPER VIPwall! PogChamp")
							log("SUPER VIPwall!")
						elif vip_wall == 50:
							send_message("#MEGA VIPwall! PogChamp Kreygasm CurseLit")
							log("MEGA VIPwall!")
					else:
						vip_wall = 0
						vipwall_vips = set()
				elif message_dict["message_type"] == "notice":
					if "msg_id" in message_dict: # yes.. it's msg_id here but msg-id everywhere else. Why? Who knows. Why be consistent?
						id = message_dict["msg_id"]
						if "message" in message_dict:
							message = message_dict["message"]
							log(f"NOTICE: {id}: {message}")
							if id != "color_changed": # gets spammy with daily colour changes and rainbows etc
								with open("chatlog.txt", "a", encoding="utf-8") as f:
									f.write(f"NOTICE: (msg_id {id}): {message}\n")
						else:
							log(f"NOTICE with msg_id but no message: {str(message_dict)}")
					else:
						log(f"NOTICE with no msg_id: {str(message_dict)}")

				elif message_dict["message_type"] == "usernotice":
					if "msg-id" in message_dict:
						if message_dict["msg-id"] == "subgift": # GIFTED SUBSCRIPTION
							gifter = message_dict["display-name"].lower()
							recipient = message_dict["msg-param-recipient-display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {gifter} has gifted a subscription to {recipient}\n")
							subscribers[recipient] = {"gifter_name":gifter, "is_gift":True, "subscribe_time":int(time())}
							commit_subscribers()
							log(f"{gifter} has gifted a sub to {recipient}!")

							if commands_file.nochat_on:
								send_message(f"@{gifter} thank you so much for gifting a subscription to {recipient}! Kaywee isn't looking at chat right now (!nochat) but she'll see your sub after the current game.")
								log(f"Sent nochat to {user} for gifting a sub")

						elif message_dict["msg-id"] == "sub": # USER SUBSCRIPTION
							user = message_dict["display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {user} has subscribed!\n")
							subscribers[user] = {"gifter_name":"", "is_gift":False, "subscribe_time":int(time())}
							commit_subscribers()
							log(f"{user} has subscribed!")

							if commands_file.nochat_on:
								send_message(f"@{user} thank you so much for subscribing! Kaywee isn't looking at chat right now (!nochat) but she'll see your sub after the current game.")
								log(f"Sent nochat to {user} for subscribing")

						elif message_dict["msg-id"] == "resub": # USER RESUBSCRIPTION
							user = message_dict["display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {user} has resubscribed!\n")
							subscribers[user] = {"gifter_name":"", "is_gift":False, "subscribe_time":int(time())}
							commit_subscribers()
							log(f"{user} has resubscribed!")

							if commands_file.nochat_on:
								send_message(f"@{user} thank you so much for resubscribing! Kaywee isn't looking at chat right now (!nochat) but she'll see your sub after the current game.")
								log(f"Sent nochat to {user} for resubscribing")


						elif message_dict["msg-id"] == "anonsubgift": # ANONYMOUS GIFTED SUBSCRIPTION
							# comes through as a gifted sub from AnAnonymousGifter ? So might not need this
							recipient = message_dict["msg-param-recipient-display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: Anon has gifted a subscription to {recipient}!\n")
							subscribers[recipient] = {"gifter_name":"AnAnonymousGifter", "is_gift":True, "subscribe_time":int(time())}
							commit_subscribers()

						elif message_dict["msg-id"] == "raid": # RAID
							raider = message_dict["msg-param-displayName"]
							viewers = message_dict["msg-param-viewerCount"]
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {raider} is raiding with {viewers} viewers!\n")
							send_message(f"Wow! {raider} is raiding us with {viewers} new friends! Thank you! kaywee1AYAYA")
							log(f"{raider} is raiding with {viewers} viewers.")
							raid_data = {"raider": raider, "viewers": viewers, "time": time()}
							set_data("last_raid", raid_data)

							if commands_file.nochat_on:
								sleep(2) # sleeps on the main thread cause message processing to be delayed..
								send_message(f"@{raider} thank you so much for raiding! Kaywee isn't looking at chat right now (!nochat) but she'll see the raid after the current game.")
								log(f"Sent nochat to {raider} for raiding")

						elif message_dict["msg-id"] == "submysterygift":
							gifter = message_dict["login"] # comes as lowercase
							gifts = message_dict["msg-param-mass-gift-count"]

							if gifts != "1":
								log(f"{gifter} has gifted {gifts} subscriptions to the community.")
							else:
								log(f"{gifter} has gifted a subscription to the community.")

						elif message_dict["msg-id"] == "giftpaidupgrade":
							subscriber = message_dict["msg-param-sender-login"] 

							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {subscriber} has continued their gifted sub.\n")
							log(f"{subscriber} has continued their gifted sub.")

							subscribers[subscriber] = {"gifter_name":"", "is_gift":False, "subscribe_time":int(time())}
							commit_subscribers()

							if commands_file.nochat_on:
								send_message(f"@{user} thank you so much for continuing your gifted sub! Kaywee isn't looking at chat right now (!nochat) but she'll see your sub after the current game.")
								log(f"Sent nochat to {user} for subscribing")
						elif message_dict["msg-id"] == "rewardgift":
							pass # for when gifted subs produce extra rewards (emotes) for other chat members

						elif message_dict["msg-id"] == "communitypayforward":
							pass # e.g. <user> is paying forward their gifted sub!
						else:
							with open("verbose log.txt", "a", encoding="utf-8") as f:
								f.write("(unknown msg-id?) - " + str(message_dict) + "\n\n")
						 # other sub msg-ids: sub, resub, subgift, anonsubgift, submysterygift, giftpaidupgrade, rewardgift, anongiftpaidupgrade
					else:
						with open("verbose log.txt", "a", encoding="utf-8") as f:
							f.write("(no msg-id?) - " + str(message_dict) + "\n\n")

				# does hosttarget not come through? why not?
				elif message_dict["message_type"] == "hosttarget":
					# OUTGOING HOST
					host_name = message_dict["host_name"] # the user we're now hosting
					viewers = message_dict["viewers"] # num viewers we've sent to them
					with open("chatlog.txt", "a", encoding="utf-8") as f:
						f.write(f"HOSTTARGET: now hosting {host_name} with {viewers} viewers.\n")
					log(f"Now hosting {host_name} with {viewers} viewers.")
					send_message(f"Now hosting {host_name} with {viewers} viewers.")
					
				elif message_dict["message_type"] == "reconnect":
					send_message("Stream is back online!")
					log(f"Stream is back online!")

				elif message_dict["message_type"] == "userstate":
					# Mostly just for colour changes which I don't care about
					pass

				else:
					with open("verbose log.txt", "a", encoding="utf-8") as f:
						f.write("unknown message type: " + str(message_dict) + "\n\n")
		except Exception as ex:
			log("Exception in main loop: " + str(ex)) # generic catch-all (literally) to make sure bot doesn't crash


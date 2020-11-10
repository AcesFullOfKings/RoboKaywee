#import sqlite3 # one day maybe I'll use an actual database LOL
import requests
import random
import praw

from time        import time, sleep, localtime
from enum        import IntEnum
from math        import ceil
from chatbot     import ChatBot # see https://github.com/theonefoster/pyTwitchChatBot
from datetime    import date, datetime
from threading   import Thread, Lock
from credentials import bot_name, password, channel_name, kaywee_channel_id, bearer_token, robokaywee_client_id

from API_functions import get_app_access_token

import commands as commands_file

"""
TODO:

should be able to add counters and variables to text commands

"""

command_lock = Lock()
config_lock = Lock()
subs_lock = Lock()

bots = {"robokaywee", "streamelements", "nightbot"}

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
		permissions = {0:"Pleb", 2:"Follower", 4:"Subscriber", 6:"VIP", 8:"Mod", 10:"Broadcaster"}

		r = praw.Reddit("RoboKaywee")
		subreddit = r.subreddit("RoboKaywee")

		if command_lock.acquire(timeout=10):
			with open("commands.txt", "r", encoding="utf-8") as f:
				commands = dict(eval(f.read()))

			command_lock.release()

			table = "Note: all commands are now sent with /me so will display in the bot's colour.\n\n\n**Command**|**Level**|**Response/Description**|**Uses**\n---|---|---|---\n"

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
						table += f"{command}|{level}|Coded: {commands[command]['description']}|{uses}\n"
					else:
						table += f"{command}|{level}|Coded command with no description.|{uses}\n"
				else:
					if "response" in commands[command]:
						table += f"{command}|{level}|Response: {commands[command]['response']}|{uses}\n"
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
def get_title():
	url = "https://api.twitch.tv/helix/streams?user_id=" + kaywee_channel_id
	authorisation_header = {"Client-ID": robokaywee_client_id, "Authorization":"Bearer " + get_data("app_access_token")}
	
	while True:
		try:
			title = requests.get(url, headers=authorisation_header).json()["data"][0]["title"]

		except IndexError: # streamer isn't live
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
	lastday = get_data("lastday")
	days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
	today_name = days[date.today().weekday()]

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
	send_message("On Wednesdays we wear pink. If you want to sit with us type /color HotPink to update your username colour.")
	log("Sent Pink reminder.")

def it_is_Thursday_my_dudes():
	sleep(20*60) # wait 20 mins into the stream
	send_message("On Thursdays we wear whatever colour we want. Set your username colour by using /color and come and sit with us.")
	log("Sent UnPink reminder.")

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
		log(f"Failed to set data of {name} to {value} - Value Error (corrupt file??)")
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

		if expires_in < 24*60*60: #if token expires in the next 24h
			set_data("app_access_token", get_app_access_token()) # get a new one

		sleep(23*60*60) # wait 23 hours

def send_message(message, add_to_chatlog=False, suppress_colour=False):
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
	Broadcaster = 10
	Mod	        = 8
	VIP	        = 6
	Subscriber  = 4
	Follower    = 2
	Pleb        = 0

def respond_message(user, message, permission):
	#for random non-command responses/rules
	global pink_reminder_sent
	message_lower = message.lower()

	if message_lower in ["ayy", "ayyy", "ayyyy", "ayyyyy"]:
		send_message("lmao")
		log(f"Sent lmao to {user}")

	elif message == "KEKW":
		send_message("KEKWHD Jebaited")
		log(f"Sent KEKW to {user}")

	elif "@robokaywee" in message_lower:
		send_message(f"@{user} I'm a bot, so I can't reply. Try talking to one of the helpful human mods instead.")
		log(f"Sent \"I'm a bot\" to {user}")

	elif message[0] == "^":
		send_message("^", suppress_colour=True)
		log(f"Sent ^ to {user}")

	elif commands_file.nochat_on and "kaywee" in message_lower and user not in bots:
		if "nochat" in commands_dict and "response" in commands_dict["nochat"]:
			send_message(f"@{user} {commands_dict['nochat']['response']}")
			log(f"Sent nochat to {user} in response to @kaywee during nochat mode.")

	elif permission < permissions.Subscriber: #works in 2.0
		msg_without_spaces = message_lower.replace(" ", "")
		if any(x in msg_without_spaces for x in ["bigfollows.com", "bigfollows*com", "bigfollowsdotcom"]):
			send_message(f"/ban {user}")
			log(f"Banned {user} for linking to bigfollows")

	elif message_lower in ["hewwo", "hewwo?", "hewwo??"]:
		send_message("HEWWO! UwU kaywee1AYAYA")
		log(f"Sent hewwo to {user}")

	if user == "streamelements" and not pink_reminder_sent and date.today().weekday() == 2:
		wednesday_thread = Thread(target=it_is_wednesday_my_dudes)
		wednesday_thread.start()
		pink_reminder_sent = True
		set_data("pink_reminder_sent", True)

#check for new commands and add to database:
for command_name in [o for o in dir(commands_file) if not(o.startswith("_") or o.endswith("_"))]:
	try:
		if getattr(commands_file, command_name).is_command:
			if command_name not in commands_dict:
				commands_dict[command_name] = {'permission': 0, 'global_cooldown': 1, 'user_cooldown': 0, 'coded': True, 'uses': 0, "description": getattr(commands_file, command_name).description}
				write_command_data(False)
			else:
				if commands_dict[command_name]["description"] != getattr(commands_file, command_name).description:
					commands_dict[command_name]["description"] = getattr(commands_file, command_name).description # update description
					write_command_data(False)
	except AttributeError:
		pass

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
	modwall_size      = 15
	supermodwall_size = 30
	ultramodwall_size = 50
	hypermodwall_size = 100

	if date.today().weekday() == 2: #if it's Wednesday (my dudes)
		pink_reminder_sent = get_data("pink_reminder_sent")		
	else: #if it's not wednesday
		set_data("pink_reminder_sent", False)
		pink_reminder_sent = False

	vip_wall = 0
	vipwall_vips = set()

	last_message = {}
	

	#let commands file access key data:
	commands_file.bot                = bot
	commands_file.send_message       = send_message
	commands_file.log                = log
	commands_file.command_dict       = commands_dict
	commands_file.write_command_data = write_command_data
	commands_file.get_data           = get_data
	commands_file.set_data           = set_data
	commands_file.last_message       = last_message
	commands_file.nochat_on          = False

	while True:
		try:
			messages = bot.get_messages()
			for message_dict in messages:
				if message_dict["message_type"] == "privmsg":
					user	= message_dict["display-name"].lower()
					message = message_dict["message"]
					message_lower = message.lower()

					with open("chatlog.txt", "a", encoding="utf-8") as f:
						f.write(f"{user}: {message}\n")

					if message_lower in ["hello", "hi", "hey", "hola"]:
						message = "!hello"

					last_message[user] = message

					user_permission = permissions.Pleb # unless assigned otherwise below:

					if "badges" in message_dict:
						if "broadcaster" in message_dict["badges"]:
							user_permission = permissions.Broadcaster
						elif "moderator" in message_dict["badges"] or user == "acesfullofkings_":
							user_permission = permissions.Mod
						elif "vip/1" in message_dict["badges"]:
							user_permission = permissions.VIP
						elif "subscriber" in message_dict["badges"]:
							user_permission = permissions.Subscriber

					if message.startswith("!"):
						command = message[1:].split(" ")[0].lower()
						if command in commands_dict:
							command_obj = commands_dict[command]

							if user_permission >= command_obj["permission"] and check_cooldown(command, user):
								if command_obj["coded"]:
									if command in dir(commands_file):
										func = getattr(commands_file, command)
										if func.is_command:
											if func(user, message) != False:
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
										send_message(command_obj["response"])
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
						respond_message(user, message, user_permission)

					if user_permission >= permissions.Mod:
						modwall_mods.add(user)

						# don't send modwall unless there are at least 3 mods in the wall
						if (    modwall <  (modwall_size-1) # few messages
							or (modwall >= (modwall_size-1) and len(modwall_mods) >= 3) #lots of messages and at least 3 mods
							   
							): #sadface

							modwall += 1
							if modwall == modwall_size:
								send_message("#modwall ! kaywee1AYAYA")
							elif modwall == supermodwall_size:
								send_message("#MEGAmodwall! SeemsGood kaywee1Wut ")
							elif modwall == ultramodwall_size:
								send_message("#U L T R A MODWALL TwitchLit kaywee1AYAYA kaywee1Wut")
							elif modwall == hypermodwall_size:
								send_message("#H Y P E R M O D W A L L gachiHYPER PogChamp Kreygasm CurseLit FootGoal kaywee1AYAYA kaywee1Wut")
					else:
						modwall = 0
						modwall_mods = set()
						if modwall > supermodwall_size:
							if modwall > hypermodwall_size:
								send_message(f"Hypermodwall has been broken by {user}! :( FeelsBadMan NotLikeThis PepeHands")
							elif modwall > ultramodwall_size:
								send_message(f"Ultramodwall has been broken by {user}! :( FeelsBadMan NotLikeThis")
							else: # must be >supermodwall
								send_message(f"Megamodwall has been broken by {user}! :( FeelsBadMan")

					#future me: don't indent this (otherwise mods can't interrupt vipwalls)
					if user_permission == permissions.VIP:
						vip_wall += 1

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
					if "msg_id" in message_dict: # yes.. it's msg_id here but msg-id everywhere else. Why? Who knows. Why be consistent?
						id = message_dict["msg_id"]
						if "message" in message_dict:
							message = message_dict["message"]
							log(f"NOTICE: {id}: {message}")
							if id != "color_changed": #gets spammy with daily colour changes and rainbows etc
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

						elif message_dict["msg-id"] == "sub": # USER SUBSCRIPTION
							user = message_dict["display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {user} has subscribed!\n")
							subscribers[user] = {"gifter_name":"", "is_gift":False, "subscribe_time":int(time())}
							commit_subscribers()
							log(f"{user} has subscribed!")

						elif message_dict["msg-id"] == "resub": # USER RESUBSCRIPTION
							user = message_dict["display-name"].lower()
							with open("chatlog.txt", "a", encoding="utf-8") as f:
								f.write(f"USERNOTICE: {user} has resubscribed!\n")
							subscribers[user] = {"gifter_name":"", "is_gift":False, "subscribe_time":int(time())}
							commit_subscribers()
							log(f"{user} has resubscribed!")

						elif message_dict["msg-id"] == "anonsubgift": # ANONYMOUS GIFTED SUBSCRIPTION
							#comes through as a gifted sub from AnAnonymousGifter ? So might not need this
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
						else:
							with open("verbose log.txt", "a", encoding="utf-8") as f:
								f.write("(unknown msg-id?) - " + str(message_dict) + "\n\n")
						 #other sub msg-ids: sub, resub, subgift, anonsubgift, submysterygift, giftpaidupgrade, rewardgift, anongiftpaidupgrade
					else:
						with open("verbose log.txt", "a", encoding="utf-8") as f:
							f.write("(no msg-id?) - " + str(message_dict) + "\n\n")

				#does hosttarget not work? why not?
				elif message_dict["message_type"] == "hosttarget":
					#OUTGOING HOST
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
					#Motly just for colour changes which I don't care about
					pass

				else:
					with open("verbose log.txt", "a", encoding="utf-8") as f:
						f.write("unknown message type: " + str(message_dict) + "\n\n")
		except Exception as ex:
			log("Exception in main loop: " + str(ex)) # generic catch-all (literally) to make sure bot doesn't crash


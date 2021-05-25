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
All replies will be sent in the bots colour, using /me unless specified otherwise.
"""
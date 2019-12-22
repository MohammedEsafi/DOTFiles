import github
import os
import re
import sys
from signal import signal, SIGINT
import datetime
import json

usage = '''baCkup. keep your settings files in sync

usage: python baCkup.py backup              sync your config files to your gist.
       python baCkup.py [options] restore   restore the config files to your system.
       python baCkup.py -h --help           show this help message.
       python baCkup.py --version           show version.

options:
       -f --force   force every question asked to be answered with "Yes".
'''

class formats: 
	reset='\033[0m'
	bold='\033[01m'
	disable='\033[02m'
	italic='\033[03m'
	underline='\033[04m'
	red='\033[31m'
	green='\033[32m'
	yellow='\033[33m'
	light_yellow='\033[93m'

def opt(argv):
	options = ['backup', 'restore', '--help', '--version', '--force', '-h']
	args = dict()
	for item in options:
		if item in argv:
			args[item] = True
		else:
			args[item] = False
	return (args)

def handler(msg, type, exit):
	print(formats.bold, "%s " % (type), formats.reset, msg, sep="")
	if exit:
		sys.exit(0)

def signal_handler(signal_received, frame):
	handler("SIGINT or CTRL-C detected. Exiting gracefully.", "{}i".format(formats.green), True)

def main():
	# Tell Python to run the signal_handler() function when SIGINT is recieved
	signal(SIGINT, signal_handler)

	# Get the command line args
	argv = sys.argv
	args = opt(argv)

	# usage
	if args["--help"] or args["-h"] or (len(argv) - 1 == 0):
		print(usage, end='')
		sys.exit(0)

	# --version opt
	if args["--version"]:
		print('v1.0.0')
		sys.exit(0)

	# If we want to answer baCkup with "yes" for each question
	if args["--force"]:
		__FORCE = True
	else:
		__FORCE = False

	# Read config files
        with open(os.path.expanduser('~/.baCkupconfig.ini'), 'r') as file:
            baCkupconfig = file.splitlines()
	    GIST_ID = re.search('%s(.*)%s' % ("\"", "\""), baCkupconfig[1]).group(1)
	    ACCESS_TOKEN = re.search('%s(.*)%s' % ("\"", "\""), baCkupconfig[2]).group(1)

	# Create a github instance
	git = github.Github(ACCESS_TOKEN)

	# Error handling
	try:
		git.get_user().login
	except:
		handler("invalid token. Exiting.", "{}!".format(formats.red), True)

	# Get all files paths and save it into dict (filename, path)
	paths = {}
	with open('.config.ini') as file:
		content = file.readlines()
		for line in content[2:]:
			paths[os.path.basename(line)] = line.strip()
	if len(paths) == 0 and args["backup"]:
		handler("please add the files names to backup / restore in {}{}.config.ini{} file!".format(formats.italic, formats.yellow, formats.reset), "{}i".format(formats.green), True)

	# Backup
	if args["backup"]:
		cloudSettings = dict()
		files = dict()
		cloudSettings["lastUpload"] = str(datetime.datetime.now())
		with open('cloudSettings', 'r+') as file:
			cloudSize = os.stat("cloudSettings").st_size
			if cloudSize != 0:
				cloudSettings = json.load(file)
				cloudSettings["files"] = {**cloudSettings["files"], **paths}
			else:
				cloudSettings["files"] = paths
		with open('cloudSettings', 'r') as file:
			filename = 'cloudSettings'
			files[filename] = github.InputFileContent(file.read(), filename)
		user = git.get_user()
		for (filename, path) in paths.items():
			try:
				with open(os.path.expanduser(path), 'r') as file:
					files[filename] = github.InputFileContent(file.read(), filename)
			except:
				cloudSettings['files'].pop(filename)
				if os.path.isdir(path):
					handler("the directory {}{}{}{} is ignored, Gist does not support directories.".format(formats.italic, formats.yellow, path, formats.reset), "{}i".format(formats.light_yellow), False)
				else:
					handler("the filename {}{}{}{} does not exist, or is not readable.".format(formats.italic, formats.yellow, path, formats.reset), "{}i".format(formats.light_yellow), False)
		with open('cloudSettings', 'w+') as file:
			json.dump(cloudSettings, file, indent=4)
		if not GIST_ID:
			try:
				gist = user.create_gist(False, files, "baCkup")
			except:
				handler("problem when creating a gist.", "{}!".format(formats.red), True)
			with open(os.path.expanduser('~/.baCkupconfig.ini'), 'r') as file:
				lines = file.readlines()
			lines[2] = lines[2].replace("\"\"", "\"{}\"".format(gist.id))
			with open(os.path.expanduser('~/.baCkupconfig.ini'), 'w') as file:
				file.writelines(lines)
		else:
			try:
				gist = git.get_gist(GIST_ID)
			except:
				handler("invalid gist ID. Exiting.", "{}!".format(formats.red), True)
			try:
				gist.edit("baCkup", files)
			except:
				handler("problem when editing a gist.", "{}!".format(formats.red), True)
		handler("baCkup done right!", "{}i".format(formats.green), True)

	# Restore
	elif args["restore"]:
		try:
			gist = git.get_gist(GIST_ID)
		except:
			if not GIST_ID:
				handler("gist ID not found. Exiting.", "{}!".format(formats.red), True)
			else:
				handler("invalid gist ID. Exiting.", "{}!".format(formats.red), True)
		files = gist.files
		with open('cloudSettings', 'w+') as file:
			file.write(files['cloudSettings'].content)
		with open('cloudSettings') as file:
			cloudSettings = json.load(file)
		for item in files.values():
			if item.filename != 'cloudSettings':
				if not __FORCE:
					print("{}{}?{} do you want to replace {}{}{}{} with the newer one you're restart? {}(Y/N){} ".format(formats.green, formats.bold, formats.reset, formats.italic, formats.yellow, cloudSettings['files'][item.filename], formats.reset, formats.disable, formats.reset), end="")
					try:
						answer = input()
					except EOFError:
						handler("EOF. Exiting gracefully.", "{}i".format(formats.green), True)
				if __FORCE or answer == 'Y' or answer == 'y':
					with open(os.path.expanduser(cloudSettings['files'][item.filename]), 'w+') as file:
						file.write(item.content)
		diff = set(paths) - set(files)
		if diff:
			print("{}{}i{} the filename{} {}{}{}{} do not backup. run backup command to Keep files in sync!".format(formats.green, formats.bold, formats.reset, 's' if len(diff) >= 2 else '', formats.italic, formats.yellow, ', '.join(diff), formats.reset))
		handler("reStore done right!", "{}i".format(formats.green), True)

if __name__ == "__main__":
	main()

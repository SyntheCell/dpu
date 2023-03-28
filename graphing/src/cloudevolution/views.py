from django.shortcuts import render
from django.http import HttpResponse
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.models import LinearAxis, Range1d
from bokeh.io import gridplot, vplot
import numpy as np
import itertools
import os
import time
import math
import pickle
import requests
from bs4 import BeautifulSoup

# Create your views here.
def home(request):
	sidebar_links, subdir_log = file_scan('expt')

	context = {
		"sidebar_links": sidebar_links,
	}

	return render(request, "home.html", context)


# Create your views here.
def simple_chart(request):
	sidebar_links, subdir_log = file_scan('expt')

	context = {
		"sidebar_links": sidebar_links,
	}

	return render(request, "simple_chart.html", context)


def vial_num(request, experiment, vial):
	sidebar_links, subdir_log = file_scan('expt')
	vial_count = range(0, 16)
	expt_dir, expt_subdir = file_scan(experiment)
	rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
	evolver_dir = os.path.join(rootdir, 'experiment')
	OD_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "OD", "vial{0}_OD.txt".format(vial))
	gr_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "growthrate", "vial{0}_gr.txt".format(vial))
	temp_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "temp", "vial{0}_temp.txt".format(vial))

	"""
	OD PLOT
	"""

	with open(OD_dir) as f_in:
		data = np.genfromtxt(itertools.islice(f_in, 0, None, 5), delimiter=',')
	if len(data) < 1000:
		data = np.genfromtxt(OD_dir, delimiter=',')

	last_OD_update = time.ctime(os.path.getmtime(OD_dir))

	p = figure(plot_width=700, plot_height=400)
	p.y_range = Range1d(-0.05, 0.5)
	p.xaxis.axis_label = 'Hours'
	p.yaxis.axis_label = 'Optical Density'
	p.line(data[:,0], data[:,1], line_width=1)
	OD_script, OD_div = components(p)
	od_x_range = p.x_range  # Save plot size for later

	"""
	GROWTH RATE PLOT
	"""

	gr_data = np.genfromtxt(gr_dir, delimiter=',', skip_header=2)

	last_grate_update = time.ctime(os.path.getmtime(gr_dir))

	# Quick patch when there's not enough growth rate values
	if gr_data.ndim < 2 or len(gr_data) <= 2:
		gr_data = np.asarray([[0, 0]])  # Avoids exception in p.line(gr.data ...)
		last_grate_update = "Not enough OD data yet!"  # Change time for a warning
	else:
		# Chop out first gr value, biased by the diff between the initial OD and the lower_thresh
		gr_data = gr_data[1:]

	p = figure(plot_width=700, plot_height=400)
	p.y_range = Range1d(1, 7)  # Customize here y-axis range
	p.x_range = od_x_range  # Set same size as the OD plot
	p.xaxis.axis_label = 'Hours'
	p.yaxis.axis_label = 'Generation time (h)'
	# p.line(gr_data[:, 0], gr_data[:, 1], legend="growth rate")  # NOTE: Uncomment to plot Growth rate
	p.line(gr_data[:, 0], math.log(2) / gr_data[:, 1], legend="Generation time")  # NOTE: Uncomment to plot Generation time

	# Sliding window for average growth rate calculation
	slide_mean = []
	wsize = 10  # NOTE: Customize window size to calculate the mean
	for i in range(0, len(gr_data[:, 1])):
		if i - wsize < 0:
			j = 0  # Allows plotting first incomplete windows
		else:
			j = i - wsize

		# slide_mean.append(np.nanmean(gr_data[j:i+1, 1]))  # NOTE: Uncomment to plot Growth rate
		slide_mean.append(np.nanmean(math.log(2) / gr_data[j:i+1, 1]))  # NOTE: Uncomment to plot Generation time

	p.line(gr_data[:, 0], slide_mean, legend="{0} values mean".format(wsize), line_width=1, line_color="red")

	p.legend.orientation = "top_right"

	grate_script, grate_div = components(p)

	"""
	TEMPERATURE PLOT
	"""

	with open(temp_dir) as f_in:
		data = np.genfromtxt(itertools.islice(f_in, 0, None, 10), delimiter=',')
	if len(data) < 1000:
		data = np.genfromtxt(temp_dir, delimiter=',')

	last_temp_update = time.ctime(os.path.getmtime(temp_dir))

	p = figure(plot_width=700, plot_height=400)
	p.y_range = Range1d(25, 45)
	p.x_range = od_x_range  # Set same size as the OD plot
	p.xaxis.axis_label = 'Hours'
	p.yaxis.axis_label = 'Temp (C)'
	p.line(data[:,0], data[:,1], line_width=1)
	temp_script, temp_div = components(p)

	context = {
		"sidebar_links": sidebar_links,
		"experiment": experiment,
		"vial_count": vial_count,
		"vial": vial,
		"OD_script": OD_script,
		"OD_div": OD_div,
		"grate_script": grate_script,
		"grate_div": grate_div,
		"temp_script": temp_script,
		"temp_div": temp_div,
		"last_OD_update": last_OD_update,
		"last_grate_update": last_grate_update,
		"last_temp_update": last_temp_update,
	}

	return render(request, "vial.html", context)


def expt_name(request, experiment):
	sidebar_links, subdir_log = file_scan('expt')
	vial_count = range(0, 16)
	expt_dir, expt_subdir = file_scan(experiment)
	rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
	evolver_dir = os.path.join(rootdir, 'experiment')

	plts = [] # Plot list

	for vial in vial_count:
		gr_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "growthrate", "vial{0}_gr.txt".format(vial))
		gr_data = np.genfromtxt(gr_dir, delimiter=',', skip_header=2)

		last_grate_update = time.ctime(os.path.getmtime(gr_dir))

		# Quick patch when there's not enough growth rate values
		if gr_data.ndim < 2 or len(gr_data) <= 2:
			gr_data = np.asarray([[0, 0]])  # Avoids exception in p.line(gr.data ...)
			last_grate_update = "Not enough OD data yet!"  # Change time for a warning
		else:
			# Chop out first gr value, biased by the diff between the initial OD and the lower_thresh
			gr_data = gr_data[1:]

		p = figure(plot_width=400, plot_height=300)  # NOTE: Customize here the size of summary plots (default: 400x300)
		p.y_range = Range1d(1, 7)  # NOTE: Customize here y-axis range
		p.xaxis.axis_label = 'Hours'

		# NOTE: Uncomment following lines to plot Growth rate
		# p.yaxis.axis_label = 'Growth rate (1/h)'
		# p.line(gr_data[:, 0], gr_data[:, 1], legend="growth rate")  # Growth rate

		# NOTE: Uncomment following lines to plot Generation time
		p.yaxis.axis_label = 'Generation time (h)'
		p.line(gr_data[:, 0], math.log(2) / gr_data[:, 1], legend="Generation time")  # Generation time

		# Sliding window for average growth rate calculation
		slide_mean = []
		wsize = 10  # NOTE: Customize window size to calculate the mean
		for i in range(0, len(gr_data[:, 1])):
			if i - wsize < 0:
				j = 0  # Allows plotting first incomplete windows
			else:
				j = i - wsize

			# slide_mean.append(np.nanmean(gr_data[j:i+1, 1]))  # NOTE: Uncomment to plot Growth rate
			slide_mean.append(np.nanmean(math.log(2) / gr_data[j:i+1, 1]))  # NOTE: Uncomment to plot Generation time

		p.line(gr_data[:, 0], slide_mean, legend="{0} values mean".format(wsize), line_width=1, line_color="red")
		p.title = f"Vial {vial}"

		p.legend.orientation = "top_right"

		plts.append(p)


	# NOTE: Organise grid layout of summary plots
	plot_grid = [[12,13,14,15], [8,9,10,11], [4,5,6,7], [0,1,2,3]]

	# Convert indexes to Bokeh gridplot
	x = []
	for i in plot_grid:
		y = []
		for j in i:
			if j != None:
				y.append(plts[j])
			else:
				y.append(None)
		x.append(y)

	plots = gridplot(x)
	

	summary_script, summary_div = components(plots)


	context = {
		"sidebar_links": sidebar_links,
		"experiment": experiment,
		"vial_count": vial_count,
		"summary_script": summary_script,
		"summary_div": summary_div,
	}

	return render(request, "experiment.html", context)


def dilutions(request, experiment):
	sidebar_links, subdir_log = file_scan('expt')
	vial_count = range(0, 16)
	expt_dir, expt_subdir = file_scan(experiment)
	rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
	evolver_dir = os.path.join(rootdir, 'experiment')
	pump_cal = os.path.join(evolver_dir, expt_subdir[0], "pump_cal.txt")
	bottle_file = os.path.join(evolver_dir, expt_subdir[0], "bottles.txt")
	expt_pickle = os.path.join(evolver_dir, expt_subdir[0], expt_dir[0], expt_dir[0] + ".pickle")

	if not os.path.isfile(bottle_file):
		open(bottle_file, 'w')

	# Update bottle stuff
	if request.POST.get('save-bottle'):
		# Get time and data from request
		timestamp = time.strftime("%d/%m/%Y %H:%M")
		volume = request.POST.getlist("volume")
		vials = request.POST.getlist("vials")

		# Compile info of new bottle file
		header = "# bottle\tvials\tvolume (L)\n"
		for i in range(len(volume)):
			header += f"bottle{i}\t{vials[i]}\t{volume[i]}\t{timestamp}\n"

		# Backup previous configuration file
		backup_tstamp = time.strftime("%Y%m%d_%H%M", time.localtime(os.path.getmtime(bottle_file)))
		os.rename(bottle_file, os.path.join(evolver_dir, expt_subdir[0], "bottles_"+backup_tstamp+".txt"))

		# Save new file
		F = open(bottle_file, "w")
		F.write(header)
		F.close()

	elif request.POST.get('change-bottle'):
		# Get time and data from request
		timestamp = time.strftime("%d/%m/%Y %H:%M")
		change = request.POST.getlist("change")
		change = [int(x) for x in change]
		volume = request.POST.getlist("volume")

		# Read bottle file and update data (without backup)
		old_data = open(bottle_file).readlines()
		new_data = old_data[0]
		for c, data in enumerate(old_data[1:]):
			# variable data has the shape "bottleID	vials	volume0	timestamp0 ... volumeN	timestampN"
			if c in change:
				new_vol = volume[change.index(c)]
				new_data += data.strip('\n') + "\t" + new_vol + "\t" + timestamp + "\n"
			else:
				new_data += data

		F = open(bottle_file, "w")
		F.write(new_data)
		F.close()

	cal = np.genfromtxt(pump_cal, delimiter="\t")
	diluted = []
	efficiency = []
	last = []

	# Calculate total media consumption per vial
	for vial in vial_count:
		pump_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "pump_log", "vial{0}_pump_log.txt".format(vial))
		ODset_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "ODset", "vial{0}_ODset.txt".format(vial))
		data = np.genfromtxt(pump_dir, delimiter=',', skip_header=2)

		dil_triggered = len(data)

		if dil_triggered != 0:
			if data.ndim < 2:
				data = np.asarray([[data[0],data[1]]])
			volume = str(round(sum(data[:, 1]) * cal[0, vial] / 1000, 2))

			dil_intervals = (len(np.genfromtxt(ODset_dir, delimiter=",", skip_header=2)) - 1) / 2 
			if dil_intervals != 0:
				extra_dils = dil_triggered - dil_intervals
				vial_eff = (dil_intervals - extra_dils) / dil_intervals * 100
			else:
				# Experiment is chemostat or vial is not used
				vial_eff = 0

		else:
			volume = 0
			vial_eff = 0

		diluted.append(volume)
		efficiency.append(str(round(vial_eff, 1)))
		last.append(time.ctime(os.path.getmtime(pump_dir)))

	last_dilution = max(last)

	if efficiency == ['0']*16:
		# All vials were chemostats or not used
		efficiency = None

	# Calculate consumption of last bottle
	bottles = []
	bottle_info = []  # Stores info displayed in "See bottle setup"
	bottle_data = open(bottle_file).readlines()[1:]

	# Get experiment start time
	with open(expt_pickle, 'rb') as f:
		expt_start = pickle.load(f)[0]

	if not bottle_data:
		bottle_info = None
	else:
		# bottleID	vials	volume0	timestamp0 ... volumeN	timestampN
		for c, bot in enumerate(bottle_data):
			# Extract data and store as lists for Django
			bot = bot.strip("\n").split("\t")
			bottle_info.append(bot[:2] + bot[-2:])   # ID	vials	volumeN	timestampN
			# Sum media consumption of vials connected to each bottle
			media = 0
			bottle_consumption = 0
			for v in bot[1].split(","):
				if v:
					# get bottle timestamp
					tstamp = time.mktime(time.strptime(bot[-1], "%d/%m/%Y %H:%M"))  # Timestamp in seconds since epoch
					tstamp -= expt_start  # Timestamp in seconds since start of experiment
					tstamp = tstamp / 3600  # Timestamp in hours since start of experiment
					# get data slice from timestamp to present
					pump_dir = os.path.join(evolver_dir, expt_subdir[0], experiment, "pump_log", f"vial{v}_pump_log.txt")
					data = np.genfromtxt(pump_dir, delimiter=',', skip_header=2)
					try:
						if len(data) == 0:
							data = np.asarray([[0,0]])
						elif data.ndim < 2:
							data = np.asarray([[data[0],data[1]]])
							print(data)
						bottle_consumption += sum(sum(data[np.where(data[:, 0] > tstamp), 1])) * cal[0, int(v)] / 1000
					except IndexError as e:
						print(e)
						print(data)
						bottle_consumption = -1  # Error when slicing the data
				else:
					bottle_consumption = -2  # Bottle has no vials assigned

			bottles.append("%.2f / %sL" % (bottle_consumption, bot[-2]))

	context = {
	"sidebar_links": sidebar_links,
	"experiment": experiment,
	"vial_count": vial_count,
	"diluted": diluted,
	"efficiency": efficiency,
	"bottle_info": bottle_info,
	"bottles": bottles,
	"last_dilution": last_dilution
	}

	return render(request, "dilutions.html", context)


def scales(request, experiment):
	sidebar_links, subdir_log = file_scan('expt')
	vial_count = range(0, 16)
	expt_dir, expt_subdir = file_scan(experiment)
	rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
	evolver_dir = os.path.join(rootdir, 'experiment')
	pump_cal = os.path.join(evolver_dir, expt_subdir[0], "pump_cal.txt")
	bottle_file = os.path.join(evolver_dir, expt_subdir[0], "bottles.txt")
	scales_dir = os.path.join(evolver_dir, expt_subdir[0], "scales")
	expt_pickle = os.path.join(evolver_dir, expt_subdir[0], expt_dir[0], expt_dir[0] + ".pickle")
	creds_file = os.path.join(evolver_dir, expt_subdir[0], 'creds.json')
	conf_file = os.path.join(evolver_dir, expt_subdir[0], 'scales_config.json')

	if not os.path.isdir(scales_dir):
		os.mkdir(scales_dir)

	url = "https://bker.io/profil/probeDetail/"

	with open(conf_file) as f:
		graph_conf = eval(f.read())

	probes = graph_conf["probes"]
	conditions = graph_conf["conditions"]

	if not os.path.isfile(creds_file):
		print("creds.json not found. Please provide login credentials for bker.io")
		return HttpResponse("<h2>creds.json not found.<br>Please provide login credentials for bker.io</h2>")

	with open(creds_file) as f:
		creds = eval(f.read())

	if "bker_user" not in creds or "bker_pass" not in creds:
		print("One or more credentials are missing in the creds.json file. Please provide login credentials for bker.io")
		return HttpResponse("<h2>One or more credentials are missing in the creds.json file.<br>Please provide login credentials for bker.io</h2>")

	payload = {
		"Email": creds["bker_user"],
		"Password": creds["bker_pass"],
		"RememberMe": "false"
	}

	try:
		with requests.Session() as s:
			login_page = s.get("https://bker.io/compte/login").text
			Token = BeautifulSoup(login_page, features='html.parser').find("input", {"name": "__RequestVerificationToken"})['value']

			payload["__RequestVerificationToken"] = Token

			login = s.post("https://bker.io/compte/login?ReturnUrl=%2Fprofil", data=payload)

			scales = []
			plots = []
			for probe in probes:
				scale = [probe]

				r = s.get(url + str(probe))

				# Parse html
				soup = BeautifulSoup(r.text, "html.parser")
				value_div = soup.find("div", {"class": "value"})

				scale.append(value_div.text.strip('\t\n\r'))

				scales.append(scale)

				if request.POST.get('get-data'):
					# Get data files

					# Get input of start time and end time -> Needs correct ISO 8601 formatting
					# Get experiment start time
					with open(expt_pickle, 'rb') as f:
						dtStart = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(pickle.load(f)[0]))
					dtEnd = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime(time.time()))
					headers = {
						"exportprobedatatocsvfilters": f'{{"idProbe":{probe},"dtStart":"{dtStart}","dtEnd":"{dtEnd}"}}',
					}

					p = s.post("https://bker.io/api/p/exportProbeDataToCsv", headers=headers)

					if p.status_code != 200:
						print(f"Error when trying to request scale history data for probe {probe}")
						print(p.status_code)
						print(p.text)
						continue

					scale_file = os.path.join(scales_dir, f"weight{probe}.csv")
					with open(scale_file, "w") as f:
						f.write(eval(p.text))
	except Exception as e:
		print("There was an exception when trying to get Bker scale data:")
		print(e)

		scales = [[probe, 'ConnectionError'] for probe in probes]

	plots = []
	for probe in probes:
		scale_file = os.path.join(scales_dir, f"weight{probe}.csv")

		if os.path.isfile(scale_file):

			with open(scale_file, 'r') as f:
				data = []
				start = None
				for line in f.readlines()[1:]:
					line = line.strip("\n").split("\t")
					line[1] = time.mktime(time.strptime(line[1], "%d/%m/%Y %H:%M:%S"))  # Time in seconds since epoch
					line[1] = line[1] / 3600
					line[2] = float(".".join(line[2].split(",")))  # Weight
					data.append(line[1:])
			if not data:
				print("Empty local file for probe " + str(probe))
				plots.append(None)
				continue
			
			data = np.array(data)
			data = data[data[:, 0].argsort()]  # Sort data using time and maintaining 'key' : 'value' structure

			data[:, 0] -= data[0, 0]

			p = figure(plot_width=600, plot_height=400, title=conditions[probe])
			p.y_range = Range1d(-.05, 2300)  # NOTE: Set y range depending on the size of your bottles
			p.xaxis.axis_label = 'Time (h)'
			p.yaxis.axis_label = 'Weight (g)'
			p.line(data[:, 0], data[:, 1], line_width=1)

			# Sliding window for average growth rate calculation
			#data = np.delete(data, np.argwhere(data[:,1] < 0), axis = 0)
			slide_mean = []
			wsize = 250  # NOTE: Customize window size to calculate the mean
			for i in range(0, len(data[:, 1])):
				if i - wsize < 0:
					j = 0  # Allows plotting first incomplete windows
				else:
					j = i - wsize
				# This is a workaround for when a weight without bottle is taken
				if data[i, 1] < 0:
					data[i, 1] = 0 # Not sure if it works to find the breakpoint later

				if data[j,1] - data[i, 1] > 0:
					# Last point is lower than the first
					# Potentially data from same bottle
					slide_mean.append((data[j, 1] - data[i, 1]) / (data[i, 0] - data[j, 0]))
				else:
					# We have to find the bottle change, and average consumption before and after
					for x in range(j+1, i+1):
						if data[x, 1] > data[x-1, 1] * 1.2:
							# This seems like a breakpoint
							consumption = data[j, 1] - data[x-1, 1] + data[x, 1] - data[i, 1]
							slide_mean.append(consumption / (data[i, 0] - data[j, 0]))
							break
					else:
						# Breakpoint not found
						#print("Breakpoint not found")
						slide_mean.append(None)
						pass

			p.extra_y_ranges = {"rate": Range1d(start=0, end=40)}
			p.line(y=slide_mean, x=data[:,0], color="red", y_range_name="rate", line_width=0.4)
			p.add_layout(LinearAxis(y_range_name="rate"), 'right')


			# Consumption estimation
			rate = slide_mean[-1]
			if rate:
				p.text(x=0, y=0, text=["%.1f mL/h - %.2f h remaining" % (rate, data[-1, 1]/rate)], text_font_style="bold", text_font_size="12pt")
			else:
				p.text(x=0, y=0, text=["Could not calculate consumption rate"], text_font_style="bold", text_font_size="12pt")

			plots.append(p)

	# show the results
	plot_script, plot_div = components(vplot(*plots))

	if not plots:
		plot_div = None

	last_updated = time.strftime("%a %d %b %Y %H:%M:%S", time.localtime())

	context = {
	"sidebar_links": sidebar_links,
	"experiment": experiment,
	"vial_count": vial_count,
	"scales": scales,
	"last_updated": last_updated,
	"plot_script": plot_script,
	"plot_div": plot_div
	}
	return render(request, "scales.html", context)


def file_scan(tag):
	rootdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
	evolver_dir = os.path.join(rootdir, "experiment")
	url_string = '{%s url "home" %s}' % ('%','%')

	sidebar_links =[]
	subdir_log = []

	for subdir in next(os.walk(evolver_dir))[1]:
		subdirname = os.path.join(next(os.walk(evolver_dir))[0], subdir)

		for subsubdir in next(os.walk(subdirname))[1]:
			if tag in subsubdir:
				#add_string = "<li><a href='%s'>%s</a></li>" % (url_string,subsubdir)
				sidebar_links.append(subsubdir)
				subdir_log.append(subdir)
				subdir_log.append(subdir)

	return sidebar_links,subdir_log

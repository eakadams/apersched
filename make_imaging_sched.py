# make_imaging_sched: Make a schedule for Apertif imaging
# K.M.Hess 19/02/2019 (hess@astro.rug.nl)
__author__ = "Kelley M. Hess"
__date__ = "$21-feb-2019 16:00:00$"
__version__ = "0.4"

import csv
import datetime

from argparse import ArgumentParser, RawTextHelpFormatter
from astropy.coordinates import Longitude, SkyCoord
from astropy.io import ascii
from astropy.table import Table
from astropy.time import Time
from astropy import units as u
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap
import numpy as np

from atdbquery import atdbquery
from modules.calc_slewtime import calc_slewtime  # Wants [ra,dec] start/end positions in radians; outputs seconds.
from modules.calibrators import *
from modules.functions import *
from modules.telescope_params import westerbork

###################################################################
# Survey specific functions for doing observations and calibration

# class telescope_status:
#     def __init__(self):
#         self.data = []

def do_calibration_40b(i, obstime_utc, telescope_position, csvfile, total_wait, next_cal):
    current_lst = Time(obstime_utc).sidereal_time('apparent', westerbork().lon)
    if next_cal == names[1]:
        n = 1
    if next_cal == names[0]:
        n = 0
    is_cal_up = (current_lst.hour - calibrators[n].ra.hour > -5.0) and (current_lst.hour - calibrators[n].ra.hour < 2.0)

    # calib_ha = [c.ra.hour - current_lst.hour for c in calibrators]
    # calib_choice = (calib_ha > -5.0) and (calib_ha < 2.0)
    # if calib_choice[1]:
    # elif: calib_choice[4]:
    # elif: cali_choice[0]:
    # elif: calib_choice[3]:

    calib_wait = 0

    new_obstime_utc = obstime_utc
    # Wait for calibrator to be at least an hour above the horizon.
    while not is_cal_up:  # and (calib_wait < 6. * 60.): # and (not is3c286):
        calib_wait += dowait
        new_obstime_utc = wait_for_rise(new_obstime_utc, waittime=dowait)
        new_lst = Time(new_obstime_utc).sidereal_time('apparent', westerbork().lon)
        is_cal_up = (new_lst.hour - calibrators[n].ra.hour > -5.0) and (new_lst.hour - calibrators[n].ra.hour < 2.0)
    if calib_wait != 0 and calib_wait < 6. * 60:
        total_wait += calib_wait
        obstime_utc = new_obstime_utc
        current_lst = new_lst
        print("Calibrator not up, waiting {} minutes until LST: {}.".format(calib_wait, str(current_lst)))
    elif calib_wait >= 6. * 60:
        n = 3
        calib_wait = 0
        new_obstime_utc = obstime_utc
        is_3c286_up = (current_lst.hour - calibrators[n].ra.hour > -5.0) and (
                    current_lst.hour - calibrators[n].ra.hour < 2.0)
        while not is_3c286_up:
            calib_wait += dowait
            new_obstime_utc = wait_for_rise(new_obstime_utc, waittime=dowait)
            new_lst = Time(new_obstime_utc).sidereal_time('apparent', westerbork().lon)
            is_3c286_up = (new_lst.hour - calibrators[n].ra.hour > -5.0) and (new_lst.hour - calibrators[n].ra.hour < 2.0)
        if calib_wait != 0:
            total_wait += calib_wait
            obstime_utc = new_obstime_utc
            current_lst = new_lst
            print("Calibrator not up, waiting {} minutes until LST: {}.".format(calib_wait, str(current_lst)))

    slew_seconds = calc_slewtime([telescope_position.ra.radian, telescope_position.dec.radian],
                                 [calibrators[n].ra.radian, calibrators[n].dec.radian])
    if slew_seconds < calib_wait * 60.:
        new_obstime_utc = obstime_utc + datetime.timedelta(minutes=calib_wait)
    else:
        new_obstime_utc = obstime_utc + datetime.timedelta(seconds=slew_seconds)
    after_cal = observe_calibrator(new_obstime_utc, obstime=2. * 60. + 58.)
    write_to_csv(csvfile, names[n], calibrators[n], new_obstime_utc, after_cal)

    type_cal = 'Polarization'
    if n == 1:
        type_cal = 'Flux'
    print("Scan {} observed {} calibrator {}.".format(i, type_cal, names[n]))

    if n == 3:
        next_cal = names[n]
    elif next_cal == names[0]:
        next_cal = names[1]
    else:
        next_cal = names[0]

    return i, after_cal, calibrators[n], total_wait, next_cal


# Need to add a check to do_calib at the beginning of an observation (I think)
def do_calibration(i, obstime_utc, telescope_position, csvfile, total_wait):
    current_lst = Time(obstime_utc).sidereal_time('apparent', westerbork().lon)
    is3c147 = np.abs(current_lst.hour - calibrators[0].ra.hour < 5.0)
    is_ctd93 = np.abs(current_lst.hour - calibrators[2].ra.hour < 5.0)

    calib_wait = 0
    # Wait for calibrator to be at least an hour above the horizon.
    while (not is3c147) and (not is_ctd93):
        calib_wait += dowait
        total_wait += dowait
        new_obstime_utc = wait_for_rise(obstime_utc, waittime=dowait)
        obstime_utc = new_obstime_utc
        current_lst = Time(obstime_utc).sidereal_time('apparent', westerbork().lon)
        is3c147 = np.abs(current_lst.hour - calibrators[0].ra.hour) < 5.0
        is_ctd93 = np.abs(current_lst.hour - calibrators[1].ra.hour) < 5.0
    if calib_wait != 0:
        print("Calibrator not up, waiting {} minutes until LST: {}.".format(calib_wait, str(current_lst)))

    # Observe the calibrator(s) that is (are) up:
    if is3c147:
        slew_seconds = calc_slewtime([telescope_position.ra.radian, telescope_position.dec.radian],
                                     [calibrators[0].ra.radian, calibrators[0].dec.radian])
        new_obstime_utc = obstime_utc + datetime.timedelta(seconds=slew_seconds)
        after_3c147 = observe_calibrator(new_obstime_utc, obstime=15)
        write_to_csv(csvfile, names[0], calibrators[0], new_obstime_utc, after_3c147)
        print("Scan {} observed {}.".format(i, names[0]))

        i += 1
        slew_seconds = calc_slewtime([calibrators[0].ra.radian, calibrators[0].dec.radian],
                                     [calibrators[1].ra.radian, calibrators[1].dec.radian])
        new_obstime_utc = after_3c147 + datetime.timedelta(seconds=slew_seconds)
        after_3c138 = observe_calibrator(new_obstime_utc, obstime=15)
        write_to_csv(csvfile, names[1], calibrators[1], new_obstime_utc, after_3c138)
        print("Scan {} observed {}.".format(i, names[1]))
        return i, after_3c138, calibrators[1], total_wait

    else:
        slew_seconds = calc_slewtime([telescope_position.ra.radian, telescope_position.dec.radian],
                                     [calibrators[2].ra.radian, calibrators[2].dec.radian])
        new_obstime_utc = obstime_utc + datetime.timedelta(seconds=slew_seconds)
        after_ctd93 = observe_calibrator(new_obstime_utc, obstime=15)
        write_to_csv(csvfile, names[2], calibrators[2], new_obstime_utc, after_ctd93)
        print("Scan {} observed {}.".format(i, names[2]))
        return i, after_ctd93, calibrators[2], total_wait


def do_target_observation(i, obstime_utc, telescope_position, csvfile, total_wait): #, closest_field):
    # Get first position or objects that are close to current observing horizon:
    current_lst = Time(obstime_utc).sidereal_time('apparent', westerbork().lon)
    proposed_ra = (current_lst + Longitude('6h')).wrap_at(360 * u.deg)

    avail_fields = apertif_fields[apertif_fields['weights'] > 0]
    # if closest_field:
    #     availability = SkyCoord(apertif_fields['hmsdms'][closest_field]).ra.hour - proposed_ra.hour
    # else:
    availability = SkyCoord(np.array(avail_fields['hmsdms'])).ra.hour - proposed_ra.hour
    availability[availability < -12] += 24

    targ_wait = 0

    new_obstime_utc = obstime_utc
    while not np.any((availability < 0.0) & (availability > -0.5)):
        targ_wait += dowait
        new_obstime_utc = wait_for_rise(new_obstime_utc, waittime=dowait)
        current_lst = Time(new_obstime_utc).sidereal_time('apparent', westerbork().lon)
        proposed_ra = (current_lst + Longitude('6h')).wrap_at(360 * u.deg)
        # if closest_field:
        #     availability = SkyCoord(apertif_fields['hmsdms'][closest_field]).ra.hour - proposed_ra.hour
        # else:
        availability = SkyCoord(np.array(avail_fields['hmsdms'])).ra.hour - proposed_ra.hour
        availability[availability < -12] += 24
    if (targ_wait != 0) and (targ_wait < 6. * 60):
        total_wait += targ_wait
        print("Target not up, waiting {} minutes until LST: {}".format(targ_wait, str(current_lst)))
    # if closest_field:
    #     first_field = apertif_fields[closest_field][0]
    # else:

    if targ_wait <= 6. * 60:
        first_field = avail_fields[(availability < 0.0) & (availability > -0.5)][0]

        # NOTE SLEW TIME IS CALCULATED TO THE *OBSERVING* HORIZON, NOT TO THE NEW RA!
        # TELESCOPE SHOULD MOVE TO HORIZON AND WAIT!!!
        slew_seconds = calc_slewtime([telescope_position.ra.radian, telescope_position.dec.radian],
                                     [SkyCoord(first_field['hmsdms']).ra.radian,
                                      SkyCoord(first_field['hmsdms']).dec.radian])
        if slew_seconds < targ_wait * 60.:
            new_obstime_utc = obstime_utc + datetime.timedelta(minutes=targ_wait)
        else:
            new_obstime_utc = obstime_utc + datetime.timedelta(seconds=slew_seconds)
        after_target = observe_target(apertif_fields, new_obstime_utc, first_field['name'], obstime=11.5)
        write_to_csv(csvfile, first_field['name'], SkyCoord(first_field['hmsdms']), new_obstime_utc, after_target)
        print("Scan {} observed {}.".format(i, first_field['hmsdms']))
        return i, after_target, SkyCoord(first_field['hmsdms']), total_wait
    else:
        print("No target for {} hours. Go to a calibrator instead.".format(targ_wait/60.))
        return i, obstime_utc, telescope_position, total_wait

###################################################################

parser = ArgumentParser(description="Make observing schedule for the Apertif imaging surveys. Saves schedule in CSV file to be parsed by atdbspec. "
                                    "Outputs a png of the completed and scheduled pointings.",
                        formatter_class=RawTextHelpFormatter)

parser.add_argument('-f', '--filename', default='./ancillary_data/all_pointings.v4.13dec18.txt',
                    help='Specify the input file of pointings to choose from (default: %(default)s).')
parser.add_argument('-o', '--output', default='temp',
                    help='Specify the root of output csv and png files (default: imaging_sched_%(default)s).csv.')
parser.add_argument('-s', "--starttime_utc", default="2019-03-25 20:00:00",
                    help="The start time in ** UTC ** ! - format 'YYYY-MM-DD HH:MM:SS' (default: '%(default)s').",
                    type=datetime.datetime.fromisoformat)
parser.add_argument('-l', "--schedule_length", default=7.0,
                    help="Number of days to schedule (can be float; default: %(default)s).",
                    type=float)
# parser.add_argument('-p', '--startposition',
#                     default = 'input/atdbpointing_example.csv',
#                     help = 'Specify the input file location (default: %(default)s)')
parser.add_argument('-b', "--all_beam_calib",
                    help="Default behavior is 15 minutes on a calibrator in the central beam. If option is included, run 40 beam calibration.",
                    action='store_true')
parser.add_argument('-a', "--check_atdb",
                    help="If option is included, *DO NOT* check ATDB for previous observations.",
                    action='store_false')
parser.add_argument('-v', "--verbose",
                    help="If option is included, print updated UTC times after each scan.",
                    action='store_true')

# Parse the arguments above
args = parser.parse_args()

# This functionality needs more testing
# User supplied field (will choose nearest survey pointing from file later):
# start_pos = SkyCoord.from_name('Abell 262')
start_pos = None

# Filename for the csv file of observed fields:
csv_filename = 'imaging_sched_{}.csv'.format(args.output)

# Filename for the map of observed fields:
filename = 'imaging_map_{}.png'.format(args.output)

# Number of minutes to wait before checking source availability
dowait = 5

# Load all-sky pointing file and select the pointings with the label for the appropriate survey:

# labels: l=lofar; m=medium-deep; s=shallow; t=timing; g=Milky Way +/-5 in galactic latitude
#         h=NCP that will be covered with hexagonal compound beam arrangement
fields = Table(ascii.read(args.filename, format='fixed_width'))
apertif_fields = fields[(fields['label'] == 'm') | (fields['label'] == 's')]
# apertif_fields = fields[(fields['label'] == 'l') | (fields['label'] == 'm') | (fields['label'] == 's')]
# apertif_fields = fields[(fields['label'] == 'm')]
weights = np.zeros(len(apertif_fields))
weights[apertif_fields['label'] == 's'] = 1
weights[apertif_fields['label'] == 'm'] = 10
weights[apertif_fields['label'] == 'l'] = 4
apertif_fields['weights'] = weights  # Add "weights" column to table.

# Get rid of very beginning of Fall sky (unstable to current algorithm)
apertif_fields=apertif_fields[(apertif_fields['ra'] < 20.*15.) | (apertif_fields['ra'] > 21.75*15.)]

# Get rid of all but HETDEX in Spring sky (for 4 week operations rehearsal)
apertif_fields=apertif_fields[(apertif_fields['ra'] < 6*15.) | (apertif_fields['ra'] > 20.*15.) |
                              ((apertif_fields['ra'] > 6.*15.) & (apertif_fields['ra'] < 20.*15.) & (apertif_fields['dec'] > 50.))]

print("\n##################################################################")
print("Number of all-sky fields are: {}".format(len(fields)))
print("Number of Apertif imaging fields are: {}".format(len(apertif_fields)))

# Retrieve names of observations from ATDB (excludes calibrator scans)
if args.check_atdb:
    observations = atdbquery.atdbquery(obs_mode='imaging')
    imaging_obs = [dict(observations[i])['name'] for i in range(len(observations))
                   if (dict(observations[i])['name'][0:2] != '3c') and (dict(observations[i])['name'][0:2] != '3C')
                   and (dict(observations[i])['name'][0:2] != 'CT')]
    # Adjust 'weights' field for objects that have been previously observed:
    for obs in imaging_obs:
        if obs in fields['name']:
            i = np.where(apertif_fields['name'] == obs)
            apertif_fields['weights'][i] -= 1
else:
    print("Not querying ATDB for previous observations.")

# Estimate the telescope starting position as on the meridian (approximately parked)
telescope_position = SkyCoord(ra=Time(args.starttime_utc).sidereal_time('apparent', westerbork().lon), dec='50d00m00s')
current_lst = Time(args.starttime_utc).sidereal_time('apparent', westerbork().lon)
next_cal = names[1]

# Create a record of the positions planned to be observed so we can plot later.
observed_pointings = []

print("\nStarting observations! UTC: " + str(args.starttime_utc))
print("Calculating schedule for the following " + str(args.schedule_length) + " days.\n")

# if start_pos:
#     sep = start_pos.separation(SkyCoord(np.array(apertif_fields['hmsdms'])))
#     closest_field = np.where((sep == min(sep)) & (apertif_fields['weights'] != 0))[0]
# else:
#     closest_field = None

# Keep track of observing efficiency
total_wait = 0

# Open & prepare CSV file to write parset parameters to, in format given by V.M. Moss.
# (This could probably be done better because write_to_parset is in modules/function.py)
header = ['source', 'ra', 'dec', 'date1', 'time1', 'date2', 'time2', 'int', 'type', 'weight', 'beam', 'switch_type']

# Do the observations: select calibrators and target fields, and write the output to a CSV file.
# Also, writes out a record of what is observed, when, and if the telescope has to wait for objects to rise.
with open(csv_filename, 'w') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(header)

    # Always start on a calibrator
    i = 1
    if args.all_beam_calib:
        i, new_obstime_utc, new_position, total_wait, next_cal = \
            do_calibration_40b(i, args.starttime_utc, telescope_position, writer, total_wait, next_cal)
    else:
        i, new_obstime_utc, new_position, total_wait = \
            do_calibration(i, args.starttime_utc, telescope_position, writer, total_wait)
    obstime_utc = new_obstime_utc
    telescope_position = new_position
    if args.verbose:
        print("\tUTC: " + str(obstime_utc) + ",  LST: " + str(
            Time(obstime_utc).sidereal_time('apparent', westerbork().lon)) + " at end of scan.")

    # Iterate between target and calibrators for the specified amount of time & write to CSV file:
    while obstime_utc < args.starttime_utc + datetime.timedelta(days=args.schedule_length):
        i += 1
        i, new_obstime_utc, new_position, total_wait = do_target_observation(i, obstime_utc, telescope_position, writer,
                                                                             total_wait)
        if args.verbose:
            print("\tUTC: " + str(new_obstime_utc) + ",  LST: " + str(
                Time(new_obstime_utc).sidereal_time('apparent', westerbork().lon)) + " at end of scan.", end="")
            print("\tTotal time between end of scans: {:0.4} hours".format(
                (new_obstime_utc - obstime_utc).seconds / 3600.))
        obstime_utc = new_obstime_utc
        telescope_position = new_position
        observed_pointings.append(new_position)

        # If doing a 40 beam calibration and the cycle is stuck in a rut, observe 3C286 and then go back to the beginning of loop
        if args.all_beam_calib and (next_cal == names[3]):
            i += 1
            next_cal = names[1]
            print("NEXT CALIBRATOR IS {}".format(next_cal))
            i, new_obstime_utc, new_position, total_wait, next_cal = do_calibration_40b(i, obstime_utc,
                                                                                        telescope_position, writer,
                                                                                        total_wait, next_cal)
            if args.verbose:
                print("\tUTC: " + str(new_obstime_utc) + ",  LST: " + str(
                    Time(new_obstime_utc).sidereal_time('apparent', westerbork().lon)) + " at end of scan.", end="")
                print("\tTotal time between end of scans: {:0.4} hours".format(
                    (new_obstime_utc - obstime_utc).seconds / 3600.))
            obstime_utc = new_obstime_utc
            telescope_position = new_position
            continue

        # If doing a 40 beam calibration, do two targets in a row
        if args.all_beam_calib:
            i += 1
            i, new_obstime_utc, new_position, total_wait = do_target_observation(i, obstime_utc, telescope_position,
                                                                                 writer, total_wait)
            if args.verbose:
                print("\tUTC: " + str(new_obstime_utc) + ",  LST: " + str(
                    Time(new_obstime_utc).sidereal_time('apparent', westerbork().lon)) + " at end of scan.", end="")
                print("\tTotal time between end of scans: {:0.4} hours".format(
                    (new_obstime_utc - obstime_utc).seconds / 3600.))
            obstime_utc = new_obstime_utc
            telescope_position = new_position
            observed_pointings.append(new_position)

        # Always finish on a calibrator
        i += 1
        if args.all_beam_calib:
            i, new_obstime_utc, new_position, total_wait, next_cal = \
                do_calibration_40b(i, obstime_utc, telescope_position, writer, total_wait, next_cal)
        else:
            i, new_obstime_utc, new_position, total_wait = \
                do_calibration(i, obstime_utc, telescope_position, writer, total_wait)
        if args.verbose:
            print("\tUTC: " + str(new_obstime_utc) + ",  LST: " + str(
                Time(new_obstime_utc).sidereal_time('apparent', westerbork().lon)) + " at end of scan.", end="")
            print("\tTotal time between end of scans: {:0.4} hours".format(
                (new_obstime_utc - obstime_utc).seconds / 3600.))
        obstime_utc = new_obstime_utc
        telescope_position = new_position

print("Ending observations! UTC: " + str(obstime_utc))
print("Total wait time: {} mins is {:3.1f}% of total.".format(total_wait,
                                                              total_wait * 60. / (obstime_utc - args.starttime_utc).total_seconds() * 100))
print("\nThe schedule has been written to " + csv_filename)
print("A map of the observed fields has been written to " + filename)
print("IF THIS IS NOT A REAL SURVEY OBSERVATION BUT WILL BE OBSERVED, EDIT THE TARGET NAMES IN THE csv FILE!")
print("##################################################################\n")

# Create and save a figure of all pointings selected for this survey, and which have been observed.
plt.figure(figsize=[8, 8])
m = Basemap(projection='nplaea', boundinglat=20, lon_0=310, resolution='l', celestial=True)
m.drawparallels(np.arange(30, 90, 15), labels=[False, False, False, False], color='darkgray')
m.drawmeridians(np.arange(0, 360, 15), labels=[True, True, False, True], color='darkgray', latmax=90)
xpt_ncp, ypt_ncp = m(SkyCoord(np.array(apertif_fields['hmsdms'])).ra.deg,
                     SkyCoord(np.array(apertif_fields['hmsdms'])).dec.deg)
m.plot(xpt_ncp, ypt_ncp, 'o', markersize=7, label='SNS', mfc='none', color='0.1')
for i, f in enumerate(apertif_fields):
    if (f['label'] == 'm') & (f['weights'] != 10):
        m.plot(xpt_ncp[i], ypt_ncp[i], 'o', markersize=7, mfc='red', color='0.8', alpha=f['weights'] / 10)
        # print(f, 'red')
    elif (f['label'] == 's') & (f['weights'] == 0):
        m.plot(xpt_ncp[i], ypt_ncp[i], 'o', markersize=7, mfc='red', color='0.8', alpha=f['weights'] / 10)
    elif (f['label'] == 'l') & (f['weights'] != 4):
        m.plot(xpt_ncp[i], ypt_ncp[i], 'o', markersize=7, mfc='red', color='0.8', alpha=f['weights'] / 10)
m.plot(0, 0, 'o', markersize=7, label='Already in ATDB', mfc='red', color='0.8')
for o in observed_pointings:
    xpt_ncp, ypt_ncp = m(o.ra.deg, o.dec.deg)
    m.plot(xpt_ncp, ypt_ncp, 'o', markersize=7, mfc='blue')
    # print(o, 'blue')
m.plot(xpt_ncp, ypt_ncp, 'o', markersize=7, label='To be observed', mfc='blue', color='0.8')
# xcal_ncp, ycal_ncp = m(SkyCoord(np.array(calibrators.ra.deg, SkyCoord(np.array(calibrators.dec.deg)
# for i, f in enumerate(names):
#     m.plot(xcal_ncp[i], ycal_ncp[i], 'o', markersize=7, mfc='purple', color='0.8', alpha=f['weights'] / 10)
plt.legend(loc=1)
plt.savefig(filename)

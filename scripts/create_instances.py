#!python3
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 et

# Copyright © 2018 The Board of Trustees of the Leland Stanford Junior University.

# The contents of this file are licensed under the
# GNU General Public License, Version 3.
# In addition, documentation in this file is licensed under the
# Creative Commons Attribution-ShareAlike 3.0 Unported.
# See the files `LICENSE` and `LICENSE.cc-by-sa-3` for full license text.

# First, import modules from the standard library
import configparser
import os
from os import environ
import random
import signal
import sys
from sys import exit
import time

# Try importing other stuff
try:
    import boto3
    from progress.bar import Bar
    from progress.spinner import Spinner
except ModuleNotFoundError as e:
    print('Failed to import module %s' % (e.name,))
    print('Run `finish_install`')
    exit()

print('Welcome to Instance Launcher!')

# Worker timeout is in seconds
worker_timeout = 600

# Look for our config file
spinner = Spinner('Checking Configuration ')
for var in (
    'AWS_CONFIG_FILE',
    'AWS_SHARED_CREDENTIALS_FILE',
    'CREATE_INSTANCES_CONFIG',
):
    spinner.next()
    if var not in environ:
        print('Environment variable %s is missing.  Re-run `finish_install`.' % (
            var,
        ))
        exit()
    if not os.path.isfile(environ[var]):
        print('The %s file appears to be missing.  Re-run `finish_install`.' % (
            var,
        ))
        exit()
        
# Try loading our config
spinner.next()
config = configparser.ConfigParser()
try:
    config.read(environ['CREATE_INSTANCES_CONFIG'])
    spinner.next()
except Exception as e:
    print('ERROR')
    print('The instance configuration file could not be read.')
    print('Here is the error: ', e)
    print('Re-run `finish_install`')
    exit()
print(' Complete')

# Check for connectivity and permissions
spinner = Spinner('Talking to AWS ')

# Our EC2 client uses the default region for this check.
try:
    ec2_client = boto3.client('ec2')
    ec2_client.describe_instances(MaxResults=5)
    spinner.next()
except Exception as e:
    print('ERROR!')
    print('We were unable to get a list of running EC2 instances.')
    print('The exact error we got:', e)
    print('Re-run `finish_install`')
    exit()
print(' Complete')

# Prepare to build an indexed list of configs
config_names_as_list = list()
config_names_as_list.append('(Quit)')
spinner = Spinner('Checking %s workshop(s) ' % (
    len(config.sections()),
))

# Build our list of usable workshops
for workshop in config.sections():
    # Make sure the required keys are in each workshop.
    for var in (
        'template',
        'region',
        'instructions',
        'maximum',
    ):
        # Skip if we're missing a var
        if var not in config[workshop]:
            print(' WARNING')
            print('Workshop "%s" missing config item \'%s\'.' % (
                workshop,
                var
            ))
            print('Skipping this entry for now.  Re-run `finish_install` to fix.')
            next

        # For maximum, do number tests
        if var == 'maximum':
            try:
                config[workshop].getint('maximum')
            except ValueError:
                config[workshop]['maximum'] = -1
            if config[workshop].getint('maximum') <= 0:
                print(' WARNING')
                print('Workworkshop "%s" has invalid item \'maximum\'.' % (
                    workshop,
                ))
                print('Skipping this entry for now.  Re-run `finish_install` to fix.')
                next

    # Done checking over individual vars.

    # Change ec2_client to this workshop's region
    ec2_client = boto3.client('ec2',
        region_name=config[workshop]['region'],
    )

    # Make sure we can access the launch template
    try:
        ec2_client.describe_launch_templates(LaunchTemplateIds=[config[workshop]['template']])
    except Exception as e:
        print(' WARNING')
        print('Unable to pull up the launch template for workworkshop "%s"' % (
            workshop,
        ))
        print('Skipping this entry for now.  Re-run `finish_install` to fix.')
        next

    # Done checking this workshop!
    config_names_as_list.append(workshop)
    spinner.next()

# Done checking configuration
print(' Complete')

# We now have a list of instance types to launch, and a working Boto3 client.
# What does the user wish to launch?

print('')
print('The following workshops are available to launch:')
for i in range(0, len(config_names_as_list)):
    print('%3d: %s' % (i, config_names_as_list[i]))
choice_index = -1
while choice_index == -1:
    try:
        choice_index = input('Please choose a number from 0 to %d: ' % (len(config_names_as_list)-1,))
    except (EOFError, KeyboardInterrupt):
        choice_index = 0
    try:
        choice_index = int(choice_index)
    # Make sure we have an integer in the range [0, len(config_names_as_list))
    except ValueError:
        print('Please enter a valid base 10 integer')
        choice_index = -1
        continue
    if choice_index < 0:
        print('Please enter a non-negative integer')
        choice_index = -1
    if choice_index >= len(config_names_as_list):
        print('Please enter an integer less than %d' % (len(config_names_as_list),))
        choice_index = -1

# Report the selection, or exit
if choice_index == 0:
    print('Goodbye')
    exit()
chosen_config = config_names_as_list[choice_index]
print('')
print("Selected template:  %s\nAWS Region:         %s\nAWS Template ID:    %s\nUsage Instructions: %s" %
      (chosen_config, config[chosen_config]['region'], config[chosen_config]['template'], config[chosen_config]['instructions'])
)
del choice_index
del config_names_as_list

# Do our final ec2_client re-creation
ec2_client = boto3.client('ec2',
    region_name = config[chosen_config]['region'],
)

# How many instances should be launched?
instance_count = -1
print('')
while instance_count == -1:
    try:
        instance_count = input('How many instances should be created (or enter 0 to cancel)? ')
    except (EOFError, KeyboardInterrupt):
        instance_count = 0
    try:
        instance_count = int(instance_count)
    # Make sure we have a valid integer
    except ValueError:
        print('Please enter a valid base 10 integer')
        instance_count = -1
        continue
    if instance_count < 0:
        print('Please enter a non-negative integer')
        instance_count = -1
    if instance_count > config[chosen_config].getint('maximum'):
        print('Please enter a number less than or equal to %d (the type-specific max)' %
              (config[chosen_config].getint('maximum'))
        )
        instance_count = -1

# Our task has been set!!!
if instance_count == 0:
    print('Goodbye')
    exit()
print('Requesting %d instances of `%s`… ' % (instance_count, chosen_config), end='')

instance_template = config[chosen_config]['template']
instance_instructions = config[chosen_config]['instructions']
del config

# Block the user from unintentionally doing Control-C after this point.
control_c_count = 0
def control_c(signal, frame):
    if control_c_count < 1:
        print('The instance creation operation has started, and cannot be rolled back.')
        print('If you exit now, you will not get any instance status information or IPs.')
        print('To exit anyway, press <Control-C> again.')
        control_c_count = control_c_count + 1
    else:
        print('OK...')
        exit()
signal.signal(signal.SIGINT, control_c)

# Let's launch our instances.  This will be done synchronously, as a single call.
try:
    # Flush stdout, and then do the call
    sys.stdout.flush()
    launched_instances = ec2_client.run_instances(
        LaunchTemplate={
            'LaunchTemplateId': instance_template,
        },
        MinCount=instance_count,
        MaxCount=instance_count,
        TagSpecifications=({
            'ResourceType': 'instance',
            'Tags': [
               {
                    'Key': 'LaunchDate',
                    'Value': 'x',
                },
                {
                    'Key': 'LaunchDateTime',
                    'Value': 'x',
                },
            ],
        },),
    )
except Exception as e:
    print('ERROR')
    print('Something went wrong in the call to run the instances')
    print('Here are the details: ', e)
    exit()

# Do some manipulation: We want a dict of instance IDs to dicts
launched_instances = launched_instances['Instances']
launched_instances = dict(
    (instance['InstanceId'], instance) for instance in launched_instances
)

# Make sure the count of instances matches what we requested
if len(launched_instances) == instance_count:
    print('Done')
else:
    print('WARNING')
    print('Out of the %d instances requested, only %d were launched.' % (instance_count, len(launched_instances)))
    print('Since some instances were launched, we will continue.')

# Our instances have been launched!
print('')
print('The following instances were launched:')
for instance_id in launched_instances:
    print(instance_id)

# Wait for all of the instances to transition to `running` state.

progress_bar = Bar(
    'Waiting for instances to "power on"…',
    max=len(launched_instances),
)
print('')
progress_bar.start()
sys.stdout.flush()

# Build the list of instances not yet checked
instances_to_check = list(launched_instances.keys())

# We just kicked off the launch, so wait three seconds before checking.
time.sleep(3)

# We'll be governed by worker_timeout for giving up on updates.
wait_starttime = time.monotonic()

# Loop through calling out to AWS
while (
    (len(instances_to_check) > 0) and
    (time.monotonic() - wait_starttime <= worker_timeout)
):
    paginator_client = ec2_client.get_paginator('describe_instances')
    page_iterator = paginator_client.paginate(InstanceIds=instances_to_check)
    for page in page_iterator:
        for reservation in page['Reservations']:
            for instance in reservation['Instances']:
                # Here we have a dict of information about the instance.
                # Update the launched_instances dict
                launched_instances[instance['InstanceId']] = instance

                # Is the instance state no longer 'pending'?
                # If so, remove it from the pending list, and update the status bar
                if instance['State']['Code'] != 0:
                    instances_to_check.remove(instance['InstanceId'])
                    progress_bar.next()
            # Done with the instance
        # Done with a reservation
    # Done with a page

    # If we have any items left to check, wait zero to 15 seconds before trying again
    if len(instances_to_check) > 0:
        time.sleep(random.randrange(0, 1500, 1) / 100)

# We have either run out of time, or have checked everything
progress_bar.finish()
if len(instances_to_check) > 0:
    for bad_instance in instances_to_check:
        print('WARNING: Instance %s never finished powering on' % (bad_instance,))
        del launched_instances[bad_instance]
    print('Since the instance(s) is/are not running, we will not use it/them.')
    print('If needed, please re-run this program to launch more instances.')
    print('Please also remember to clean up failed instances.')

# Our instances are now powered on!
# (If any are in a non-pending non-running state, we'll catch that later.)
del wait_starttime
del paginator_client
del page_iterator
del instances_to_check

# Do we have any instances left?  If not, then exit
if len(launched_instances) == 0:
    print('ERROR!  No instances survived.  Exiting.')
    print('Goodbye')
    exit()

# Wait for instances to pass status checks

progress_bar = Bar(
    'Waiting for instances to be ready…',
    max=len(launched_instances),
)
print('')
print('(This next step will take several minutes.)')
progress_bar.start()
sys.stdout.flush()

# Build the list of instances not yet checked
instances_to_check = list(launched_instances.keys())
failed_instances = list()

# We'll be governed by worker_timeout for giving up on updates.
wait_starttime = time.monotonic()

# Loop through calling out to AWS
while (
    (len(instances_to_check) > 0) and
    (time.monotonic() - wait_starttime <= worker_timeout)
):
    paginator_client = ec2_client.get_paginator('describe_instance_status')
    page_iterator = paginator_client.paginate(
        InstanceIds=instances_to_check,
        IncludeAllInstances=True,
    )
    for page in page_iterator:
        for instance in page['InstanceStatuses']:
            # Is the instance state no longer running?
            # Is the instance impaired or railed?
            # Then we're done with it for now.
            if (
                (instance['InstanceState']['Name'] != 'running') or
                (instance['InstanceStatus']['Status'] == 'impaired') or
                (instance['SystemStatus']['Status'] == 'failed')
            ):
                failed_instances.append(instance['InstanceId'])
                instances_to_check.remove(instance['InstanceId'])
                progress_bar.next()

            # If the instance and system status are good, then awesome!
            if (
                (instance['InstanceStatus']['Status'] == 'ok') and
                (instance['SystemStatus']['Status'] == 'ok')
            ):
                instances_to_check.remove(instance['InstanceId'])
                progress_bar.next()

            # For all other statuses, we'll need to check again.
        # Done with the instance
    # Done with a page

    # If we have any items left to check, wait zero to 5 seconds before trying again
    if len(instances_to_check) > 0:
        time.sleep(random.randrange(0, 500, 1) / 100)

# We have either run out of time, or have checked everything
progress_bar.finish()

# Did any instances either fail to go OK in time, or go bad?
for bad_instance in instances_to_check:
    print('WARNING: Instance %s never finished starting up.' % (bad_instance,))
    del launched_instances[bad_instance]
for bad_instance in failed_instances:
    print('WARNING: Instance %s failed to boot properly.' % (bad_instance,))
    del launched_instances[bad_instance]
if (len(instances_to_check) + len(failed_instances)) > 0:
    print('Since the instance(s) is/are not working, we will not use it/them.')
    print('If needed, please re-run this program to launch more instances.')
    print('Please also remember to clean up failed instances.')

# Our instances are now running!
del wait_starttime
del paginator_client
del page_iterator
del failed_instances
del instances_to_check

# Do we have any instances left?  If not, then exit
if len(launched_instances) == 0:
    print('ERROR!  No instances survived.  Exiting.')
    print('Goodbye')
    exit()
else:
    print('You requested %d instance(s); %d survived' % (instance_count, len(launched_instances)))

# Instances are now ready to use!

# Print the IP addresses of the instances
print('')
print('Here are the IP addresses of the running instances:')
for instance_id in launched_instances:
    public_ip = launched_instances[instance_id]['PublicIpAddress']
    if public_ip is not None:
        print(public_ip)

# Print the instructions, and we're done!
print('')
print('As a reminder, here are the instructions for these instances:')
print(instance_instructions)
print('')
print('Goodbye!')

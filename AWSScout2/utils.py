# Import future print
from __future__ import print_function

# Import opinel
from opinel.utils import *

# Import stock packages
import argparse
import datetime
from distutils import dir_util
import copy
import json
import os
import re
import shutil
import sys
import traceback

# Python2 vs Python3
try:
    import urllib2
except ImportError:
    import urllib.request as urllib2

# Import third-party packages
import requests

########################################
# Globals
########################################

supported_services = []
re_service_utils = re.compile(r'^utils_(.*?).py$')
scout2_utils_dir, foo = os.path.split(__file__)
for filename in os.listdir(scout2_utils_dir):
    service = re_service_utils.match(filename)
    if service and service.groups()[0] != 'vpc':
        supported_services.append(service.groups()[0])

ec2_classic = 'EC2-Classic'

########################################
##### Argument parser
########################################

#
# Add a shared argument to a Scout2 utility
#
def add_scout2_argument(parser, default_args, argument_name):
    if argument_name == 'ruleset-name':
        parser.add_argument('--ruleset-name',
                            dest='ruleset_name',
                            default='default',
                            nargs='+',
                            help='Customized set of rules')
    elif argument_name == 'services':
        parser.add_argument('--services',
                            dest='services',
                            default=supported_services,
                            nargs='+',
                            help='Name of the Amazon Web Services you want to work with')
    elif argument_name == 'skip':
        parser.add_argument('--skip',
                            dest='skipped_services',
                            default=[],
                            nargs='+',
                            help='Name of services you want to ignore')
    elif argument_name == 'env':
        parser.add_argument('--env',
                            dest='environment_name',
                            default=[],
                            nargs='+',
                            help='AWS environment name (used when working with multiple reports)')
    else:
        raise Exception('Invalid parameter name %s' % argument_name)


########################################
# Common functions
########################################

#
# Return the list of services to iterate over
#
def build_services_list(services = supported_services, skipped_services = []):
    enabled_services = []
    for s in services:
        if s in supported_services and s not in skipped_services:
            enabled_services.append(s)
    return enabled_services

#
# Return attribute value at a given path
#
def get_attribute_at(config, target_path, key, default_value = None):
    for target in target_path:
        config = config[target]
    return config[key] if key in config else default_value

#
# Get arbitrary object given a dictionary and path (list of keys)
#
def get_object_at(dictionary, path, attribute_name = None):
    o = dictionary
    for p in path:
        o = o[p]
    if attribute_name:
        return o[attribute_name]
    else:
        return o

#
# Recursively go to a target and execute a callback
#
def go_to_and_do(aws_config, current_config, path, current_path, callback, callback_args):
    key = path.pop(0)
    if not current_config:
        current_config = aws_config
    if not current_path:
        current_path = []
    if key in current_config:
        current_path.append(key)
        for value in current_config[key]:
            if len(path) == 0:
                if type(current_config[key] == dict) and type(value) != dict and type(value) != list:
                    callback(aws_config, current_config[key][value], path, current_path, value, callback_args)
                else:
                    # TODO: the current_config value passed here is not correct...
                    callback(aws_config, current_config, path, current_path, value, callback_args)
            else:
                # keep track of where we are...
                tmp = copy.deepcopy(current_path)
                tmp.append(value)
                go_to_and_do(aws_config, current_config[key][value], copy.deepcopy(path), tmp, callback, callback_args)

#
# JSON encoder class
#
class Scout2Encoder(json.JSONEncoder):
    def default(self, o):
        if type(o) == datetime.datetime:
            return str(o)
        else:
            return o.__dict__


########################################
# Violations search functions
########################################

def analyze_config(finding_dictionary, filter_dictionary, config, keyword, force_write = False):
    # Filters
    try:
        for key in filter_dictionary:
            f = filter_dictionary[key]
            entity_path = f.entity.split('.')
            process_finding(config, f)
        config['filters'] = filter_dictionary
    except Exception as e:
        printException(e)
        pass
    # Violations
    try:
        for key in finding_dictionary:
            finding = finding_dictionary[key]
            entity_path = finding.entity.split('.')
            process_finding(config, finding)
        config['violations'] = finding_dictionary
    except Exception as e:
        printException(e)
        pass

def has_instances(ec2_region):
    count = 0
    for v in ec2_region['vpcs']:
        if 'instances' in ec2_region['vpcs'][v]:
            count = count + len(ec2_region['vpcs'][v]['instances'])
    return False if count == 0 else True

def match_instances_and_roles(ec2_config, iam_config):
    role_instances = {}
    for r in ec2_config['regions']:
        for v in ec2_config['regions'][r]['vpcs']:
            if 'instances' in ec2_config['regions'][r]['vpcs'][v]:
                for i in ec2_config['regions'][r]['vpcs'][v]['instances']:
                    arn = ec2_config['regions'][r]['vpcs'][v]['instances'][i]['IAMInstanceProfile']['Arn'] if 'IAMInstanceProfile' in ec2_config['regions'][r]['vpcs'][v]['instances'][i] else None
                    if arn:
                        manage_dictionary(role_instances, arn, [])
                        role_instances[arn].append(i)
    for role in iam_config['Roles']:
        for arn in iam_config['Roles'][role]['InstanceProfiles']:
            if arn in role_instances:
                iam_config['Roles'][role]['InstanceProfiles'][arn]['instances'] = role_instances[arn]

def process_entities(config, finding, entity_path):
    if len(entity_path) == 1:
        entities = entity_path.pop(0)
        if entities in config or entities == '':
            if finding.callback:
                callback = getattr(finding, finding.callback)
                if entities in config:
                    for key in config[entities]:
                        # Dashboard: count the number of processed entities here
                        finding.checked_items = finding.checked_items + 1
                        callback(key, config[entities][key])
                else:
                    # Special case when performing a check that requires access to the whole config, leave entities empty
                    callback('foo', config)
            else:
                return
    elif len(entity_path) != 0:
        entities = entity_path.pop(0)
        for key in config[entities]:
            process_entities(config[entities][key], finding, copy.deepcopy(entity_path))
    else:
        printError('Unknown error.')

def process_finding(config, finding):
    entity_path = finding.entity.split('.')
    process_entities(config, finding, entity_path)


########################################
# File read/write functions
########################################

AWSCONFIG_DIR = 'inc-awsconfig'
AWSCONFIG_FILE = 'aws_config.js'
REPORT_TITLE  = 'AWS Scout2 Report'

def create_scout_report(environment_name, aws_config, force_write, debug):
    # Save data
    save_config_to_file(environment_name, aws_config, force_write, debug)
    # If needed, create a a new report named after environment's name
    if environment_name != 'default':
        def_report_filename, def_config_filename = get_scout2_paths('default')
        new_report_filename, new_config_filename = get_scout2_paths(environment_name)
        new_file = 'report-' + environment_name + '.html'
        printInfo('Creating %s ...' % new_file)
        if prompt_4_overwrite(new_file, force_write):
            if os.path.exists(new_file):
                os.remove(new_file)
            with open('report.html') as f:
                with open(new_file, 'wt') as nf:
                    for line in f:
                        newline = line.replace(REPORT_TITLE, REPORT_TITLE + ' [' + environment_name + ']')
                        newline = newline.replace(def_config_filename, new_config_filename)
                        nf.write(newline)

#
# Return the filename of the Scout2 report and config
#
def get_scout2_paths(environment_name):
    if environment_name == 'default':
        report_filename = 'report.html'
        config_filename = AWSCONFIG_DIR + '/' + AWSCONFIG_FILE
    else:
        report_filename = ('report-%s.html' % environment_name)
        config_filename = ('%s-%s/%s' % (AWSCONFIG_DIR, environment_name, AWSCONFIG_FILE))
    return report_filename, config_filename

def load_info_from_json(service, environment_name):
    report_filename, config_filename = get_scout2_paths(environment_name)
    try:
        if os.path.isfile(config_filename):
            with open(config_filename) as f:
                json_payload = f.readlines()
                json_payload.pop(0)
                json_payload = ''.join(json_payload)
                aws_config = json.loads(json_payload)
        else:
            aws_config = {}
    except Exception as e:
        printException(e)
        return {}
    return aws_config['services'][service] if 'services' in aws_config and service in aws_config['services'] else {}

def load_from_json(environment_name, var):
    report_filename, config_filename = get_scout2_paths(environment_name)
    with open(report_filename) as f:
        json_payload = f.readlines()
        json_payload.pop(0)
        json_payload = ''.join(json_payload)
        return json.loads(json_payload)

def open_file(environment_name, force_write):
    printInfo('Saving AWS config...')
    report_filename, config_filename = get_scout2_paths(environment_name)
    if prompt_4_overwrite(config_filename, force_write):
       try:
           config_dirname = os.path.dirname(config_filename)
           if not os.path.isdir(config_dirname):
               os.makedirs(config_dirname)
           return open(config_filename, 'wt')
       except Exception as e:
           printException(e)
    else:
        return None

def prompt_4_yes_no(question):
    while True:
        sys.stdout.write(question + ' (y/n)? ')
        try:
            choice = raw_input().lower()
        except:
            choice = input().lower()
        if choice == 'yes' or choice == 'y':
            return True
        elif choice == 'no' or choice == 'n':
            return False
        else:
            printError('\'%s\' is not a valid answer. Enter \'yes\'(y) or \'no\'(n).' % choice)

#
# Save AWS configuration (python dictionary) as JSON
#
def save_config_to_file(environment_name, aws_config, force_write, debug):
    try:
        with open_file(environment_name, force_write) as f:
            print('aws_info =', file = f)
            write_data_to_file(f, aws_config, force_write, debug)
    except Exception as e:
        printException(e)
        pass

########################################
# Status update functions
########################################

def init_status(items, keyword=None, fetched=0):
    count = fetched
    total = 0
    if items:
        total = len(items)
    update_status(0, total, keyword)
    return count, total

def update_status(current, total, keyword=None):
    if keyword:
        keyword = keyword + ':'
    else:
        keyword = ''
    if total != 0:
        sys.stdout.write("\r%s %d/%d" % (keyword , current, total))
    else:
        sys.stdout.write("\r%s %d" % (keyword, current))
    sys.stdout.flush()
    return current + 1

def close_status(current, total, keyword=None):
    update_status(current, total, keyword)
    sys.stdout.write('\n')

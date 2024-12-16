import os
import csv

#Read a file with config settings from the users home dir. The format 
# of the file must be like:
# <variable1>,<value1>
# <variable2>,<value2>
#
# The number of variables is 'unlimited'
#
# The function returns a dictionary with key,value pairs as you specified\
#  in the config file.

def read_csv_from_home_to_dict(filename):

    
    # Get the home directory of the user
    home_directory = os.path.expanduser('~')
    
    # Construct the full path to the file
    file_path = os.path.join(home_directory, filename)

    config_dict = {}
    with open(file_path, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            if row:  # Ensure the row is not empty
                key, value = row[0].strip(), row[1].strip()
                config_dict[key] = value
    return config_dict
